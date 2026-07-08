import re
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.core.exceptions import (
    BusinessRuleException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
)
from app.core.responses import ApiResponse
from app.modules.auth.models import User
from app.modules.workspaces.models import Workspace, WorkspaceMember, WorkspaceRole
from app.modules.workspaces.repository import WorkspaceRepository
from app.modules.workspaces.schemas import (
    AddWorkspaceMemberRequest,
    CreateWorkspaceRequest,
    UpdateWorkspaceMemberRoleRequest,
    UpdateWorkspaceRequest,
    WorkspaceListItemResponse,
    WorkspaceMemberListItemResponse,
    WorkspaceMemberResponse,
    WorkspaceResponse,
)

WORKSPACE_NOT_FOUND_MESSAGE = "Workspace not found."
WORKSPACE_NAME_EXISTS_MESSAGE = "A workspace with this name already exists."
WORKSPACE_MANAGE_DENIED_MESSAGE = "You do not have permission to manage this workspace."
WORKSPACE_MEMBER_EXISTS_MESSAGE = "User is already a workspace member."
WORKSPACE_MEMBER_NOT_FOUND_MESSAGE = "Workspace member not found."
WORKSPACE_LAST_OWNER_MESSAGE = "Workspace must have at least one owner."
USER_NOT_FOUND_MESSAGE = "User not found."
MANAGE_WORKSPACE_ROLES = {WorkspaceRole.OWNER, WorkspaceRole.ADMIN}


class WorkspaceService:
    def __init__(self, workspace_repository: WorkspaceRepository) -> None:
        self.workspace_repository = workspace_repository

    async def create_async(
        self,
        request: CreateWorkspaceRequest,
        current_user: User,
    ) -> ApiResponse[WorkspaceResponse]:
        _require_active_user(current_user)
        slug = _slugify(request.name)
        if await self.workspace_repository.get_workspace_by_slug(slug) is not None:
            raise ConflictException(WORKSPACE_NAME_EXISTS_MESSAGE)

        try:
            workspace = await self.workspace_repository.create_workspace(
                Workspace(
                    name=request.name,
                    slug=slug,
                    description=request.description,
                    is_active=True,
                    created_by_user_id=current_user.id,
                )
            )
            member = await self.workspace_repository.create_member(
                WorkspaceMember(
                    workspace_id=workspace.id,
                    user_id=current_user.id,
                    role=WorkspaceRole.OWNER,
                )
            )
        except IntegrityError as exc:
            raise ConflictException(WORKSPACE_NAME_EXISTS_MESSAGE) from exc

        return ApiResponse.success_response(
            message="Workspace created successfully.",
            data=_workspace_response(workspace, member.role),
        )

    async def list_async(self, current_user: User) -> ApiResponse[list[WorkspaceListItemResponse]]:
        _require_active_user(current_user)
        rows = await self.workspace_repository.list_workspaces_for_user(current_user.id)

        return ApiResponse.success_response(
            message="Workspaces retrieved successfully.",
            data=[
                WorkspaceListItemResponse(
                    workspaceId=workspace.id,
                    name=workspace.name,
                    slug=workspace.slug,
                    currentUserRole=member.role,
                    isActive=workspace.is_active,
                    createdAt=workspace.created_at,
                )
                for workspace, member in rows
            ],
        )

    async def get_by_id_async(
        self,
        workspace_id: UUID,
        current_user: User,
    ) -> ApiResponse[WorkspaceResponse]:
        workspace, member = await self._get_active_workspace_for_user(workspace_id, current_user)

        return ApiResponse.success_response(
            message="Workspace retrieved successfully.",
            data=_workspace_response(workspace, member.role),
        )

    async def update_async(
        self,
        workspace_id: UUID,
        request: UpdateWorkspaceRequest,
        current_user: User,
    ) -> ApiResponse[WorkspaceResponse]:
        workspace, member = await self._get_active_workspace_for_user(workspace_id, current_user)
        _require_manage_role(member)

        slug = _slugify(request.name) if request.name is not None else None
        if slug is not None:
            existing = await self.workspace_repository.get_workspace_by_slug(slug)
            if existing is not None and existing.id != workspace.id:
                raise ConflictException(WORKSPACE_NAME_EXISTS_MESSAGE)

        try:
            workspace = await self.workspace_repository.update_workspace(
                workspace,
                name=request.name,
                slug=slug,
                description=(
                    request.description
                    if "description" in request.model_fields_set
                    else workspace.description
                ),
            )
        except IntegrityError as exc:
            raise ConflictException(WORKSPACE_NAME_EXISTS_MESSAGE) from exc

        return ApiResponse.success_response(
            message="Workspace updated successfully.",
            data=_workspace_response(workspace, member.role),
        )

    async def archive_async(self, workspace_id: UUID, current_user: User) -> ApiResponse[None]:
        workspace, member = await self._get_active_workspace_for_user(workspace_id, current_user)
        _require_manage_role(member)

        await self.workspace_repository.archive_workspace(workspace)

        return ApiResponse.success_response(
            message="Workspace archived successfully.",
            data=None,
        )

    async def list_members_async(
        self,
        workspace_id: UUID,
        current_user: User,
    ) -> ApiResponse[list[WorkspaceMemberListItemResponse]]:
        await self._get_active_workspace_for_user(workspace_id, current_user)
        rows = await self.workspace_repository.list_members(workspace_id)

        return ApiResponse.success_response(
            message="Workspace members retrieved successfully.",
            data=[_member_list_item_response(member, user) for member, user in rows],
        )

    async def add_member_async(
        self,
        workspace_id: UUID,
        request: AddWorkspaceMemberRequest,
        current_user: User,
    ) -> ApiResponse[WorkspaceMemberResponse]:
        _, actor_member = await self._get_active_workspace_for_user(workspace_id, current_user)
        _require_manage_role(actor_member)
        if request.role == WorkspaceRole.OWNER:
            _require_owner(actor_member)

        user = await self.workspace_repository.get_user_by_email(str(request.email))
        if user is None or not user.is_active:
            raise NotFoundException(USER_NOT_FOUND_MESSAGE)

        if await self.workspace_repository.get_member(workspace_id, user.id) is not None:
            raise ConflictException(WORKSPACE_MEMBER_EXISTS_MESSAGE)

        try:
            member = await self.workspace_repository.create_member(
                WorkspaceMember(
                    workspace_id=workspace_id,
                    user_id=user.id,
                    role=request.role,
                )
            )
        except IntegrityError as exc:
            raise ConflictException(WORKSPACE_MEMBER_EXISTS_MESSAGE) from exc

        return ApiResponse.success_response(
            message="Workspace member added successfully.",
            data=_member_response(member, user),
        )

    async def update_member_role_async(
        self,
        workspace_id: UUID,
        user_id: UUID,
        request: UpdateWorkspaceMemberRoleRequest,
        current_user: User,
    ) -> ApiResponse[WorkspaceMemberResponse]:
        _, actor_member = await self._get_active_workspace_for_user(workspace_id, current_user)
        _require_manage_role(actor_member)

        target_member = await self.workspace_repository.get_member(workspace_id, user_id)
        if target_member is None:
            raise NotFoundException(WORKSPACE_MEMBER_NOT_FOUND_MESSAGE)
        target_user = await self._get_existing_user(user_id)

        if target_member.role == WorkspaceRole.OWNER or request.role == WorkspaceRole.OWNER:
            _require_owner(actor_member)
        if target_member.role == WorkspaceRole.OWNER and request.role != WorkspaceRole.OWNER:
            await self._require_not_last_owner(workspace_id)

        target_member = await self.workspace_repository.update_member_role(
            target_member,
            request.role,
        )

        return ApiResponse.success_response(
            message="Member role updated successfully.",
            data=_member_response(target_member, target_user),
        )

    async def remove_member_async(
        self,
        workspace_id: UUID,
        user_id: UUID,
        current_user: User,
    ) -> ApiResponse[None]:
        _, actor_member = await self._get_active_workspace_for_user(workspace_id, current_user)
        _require_manage_role(actor_member)

        target_member = await self.workspace_repository.get_member(workspace_id, user_id)
        if target_member is None:
            raise NotFoundException(WORKSPACE_MEMBER_NOT_FOUND_MESSAGE)

        if target_member.role == WorkspaceRole.OWNER:
            _require_owner(actor_member)
            await self._require_not_last_owner(workspace_id)

        await self.workspace_repository.remove_member(target_member)

        return ApiResponse.success_response(
            message="Workspace member removed successfully.",
            data=None,
        )

    async def _get_active_workspace_for_user(
        self,
        workspace_id: UUID,
        current_user: User,
    ) -> tuple[Workspace, WorkspaceMember]:
        _require_active_user(current_user)
        member = await self.workspace_repository.get_member(workspace_id, current_user.id)
        if member is None:
            raise NotFoundException(WORKSPACE_NOT_FOUND_MESSAGE)

        workspace = await self.workspace_repository.get_workspace_by_id(workspace_id)
        if workspace is None or not workspace.is_active:
            raise NotFoundException(WORKSPACE_NOT_FOUND_MESSAGE)

        return workspace, member

    async def _get_existing_user(self, user_id: UUID) -> User:
        user = await self.workspace_repository.get_user_by_id(user_id)
        if user is None:
            raise NotFoundException(USER_NOT_FOUND_MESSAGE)
        return user

    async def _require_not_last_owner(self, workspace_id: UUID) -> None:
        if await self.workspace_repository.count_owners_for_update(workspace_id) <= 1:
            raise BusinessRuleException(WORKSPACE_LAST_OWNER_MESSAGE)


def _require_active_user(user: User) -> None:
    if not user.is_active:
        raise ForbiddenException("User account is inactive.")


def _require_manage_role(member: WorkspaceMember) -> None:
    if member.role not in MANAGE_WORKSPACE_ROLES:
        raise ForbiddenException(WORKSPACE_MANAGE_DENIED_MESSAGE)


def _require_owner(member: WorkspaceMember) -> None:
    if member.role != WorkspaceRole.OWNER:
        raise ForbiddenException(WORKSPACE_MANAGE_DENIED_MESSAGE)


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    if not slug:
        raise ConflictException(WORKSPACE_NAME_EXISTS_MESSAGE)
    return slug[:120]


def _workspace_response(workspace: Workspace, role: WorkspaceRole) -> WorkspaceResponse:
    return WorkspaceResponse(
        workspaceId=workspace.id,
        name=workspace.name,
        slug=workspace.slug,
        description=workspace.description,
        currentUserRole=role,
        isActive=workspace.is_active,
        createdAt=workspace.created_at,
        updatedAt=workspace.updated_at,
    )


def _member_response(member: WorkspaceMember, user: User) -> WorkspaceMemberResponse:
    return WorkspaceMemberResponse(
        workspaceId=member.workspace_id,
        userId=user.id,
        fullName=user.full_name,
        email=user.email,
        role=member.role,
        joinedAt=member.created_at,
    )


def _member_list_item_response(
    member: WorkspaceMember,
    user: User,
) -> WorkspaceMemberListItemResponse:
    return WorkspaceMemberListItemResponse(
        userId=user.id,
        fullName=user.full_name,
        email=user.email,
        role=member.role,
        joinedAt=member.created_at,
    )
