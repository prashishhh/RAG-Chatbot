from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.core.responses import ApiResponse
from app.modules.auth.dependencies import require_active_user
from app.modules.auth.models import User
from app.modules.workspaces.dependencies import get_workspace_service
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
from app.modules.workspaces.service import WorkspaceService

router = APIRouter(prefix="/workspaces", tags=["Workspaces"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[WorkspaceResponse],
)
async def create_workspace(
    request: CreateWorkspaceRequest,
    current_user: Annotated[User, Depends(require_active_user)],
    service: Annotated[WorkspaceService, Depends(get_workspace_service)],
) -> ApiResponse[WorkspaceResponse]:
    return await service.create_async(request, current_user)


@router.get("", response_model=ApiResponse[list[WorkspaceListItemResponse]])
async def list_workspaces(
    current_user: Annotated[User, Depends(require_active_user)],
    service: Annotated[WorkspaceService, Depends(get_workspace_service)],
) -> ApiResponse[list[WorkspaceListItemResponse]]:
    return await service.list_async(current_user)


@router.get("/{workspace_id}", response_model=ApiResponse[WorkspaceResponse])
async def get_workspace(
    workspace_id: UUID,
    current_user: Annotated[User, Depends(require_active_user)],
    service: Annotated[WorkspaceService, Depends(get_workspace_service)],
) -> ApiResponse[WorkspaceResponse]:
    return await service.get_by_id_async(workspace_id, current_user)


@router.patch("/{workspace_id}", response_model=ApiResponse[WorkspaceResponse])
async def update_workspace(
    workspace_id: UUID,
    request: UpdateWorkspaceRequest,
    current_user: Annotated[User, Depends(require_active_user)],
    service: Annotated[WorkspaceService, Depends(get_workspace_service)],
) -> ApiResponse[WorkspaceResponse]:
    return await service.update_async(workspace_id, request, current_user)


@router.delete("/{workspace_id}", response_model=ApiResponse[None])
async def archive_workspace(
    workspace_id: UUID,
    current_user: Annotated[User, Depends(require_active_user)],
    service: Annotated[WorkspaceService, Depends(get_workspace_service)],
) -> ApiResponse[None]:
    return await service.archive_async(workspace_id, current_user)


@router.get(
    "/{workspace_id}/members",
    response_model=ApiResponse[list[WorkspaceMemberListItemResponse]],
)
async def list_workspace_members(
    workspace_id: UUID,
    current_user: Annotated[User, Depends(require_active_user)],
    service: Annotated[WorkspaceService, Depends(get_workspace_service)],
) -> ApiResponse[list[WorkspaceMemberListItemResponse]]:
    return await service.list_members_async(workspace_id, current_user)


@router.post(
    "/{workspace_id}/members",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[WorkspaceMemberResponse],
)
async def add_workspace_member(
    workspace_id: UUID,
    request: AddWorkspaceMemberRequest,
    current_user: Annotated[User, Depends(require_active_user)],
    service: Annotated[WorkspaceService, Depends(get_workspace_service)],
) -> ApiResponse[WorkspaceMemberResponse]:
    return await service.add_member_async(workspace_id, request, current_user)


@router.patch(
    "/{workspace_id}/members/{user_id}/role",
    response_model=ApiResponse[WorkspaceMemberResponse],
)
async def update_workspace_member_role(
    workspace_id: UUID,
    user_id: UUID,
    request: UpdateWorkspaceMemberRoleRequest,
    current_user: Annotated[User, Depends(require_active_user)],
    service: Annotated[WorkspaceService, Depends(get_workspace_service)],
) -> ApiResponse[WorkspaceMemberResponse]:
    return await service.update_member_role_async(workspace_id, user_id, request, current_user)


@router.delete("/{workspace_id}/members/{user_id}", response_model=ApiResponse[None])
async def remove_workspace_member(
    workspace_id: UUID,
    user_id: UUID,
    current_user: Annotated[User, Depends(require_active_user)],
    service: Annotated[WorkspaceService, Depends(get_workspace_service)],
) -> ApiResponse[None]:
    return await service.remove_member_async(workspace_id, user_id, current_user)
