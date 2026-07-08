from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.database import get_db
from app.core.exceptions import ForbiddenException, NotFoundException
from app.modules.auth.dependencies import require_active_user
from app.modules.auth.models import User
from app.modules.workspaces.models import WorkspaceMember, WorkspaceRole
from app.modules.workspaces.repository import WorkspaceRepository
from app.modules.workspaces.service import (
    MANAGE_WORKSPACE_ROLES,
    WORKSPACE_MANAGE_DENIED_MESSAGE,
    WORKSPACE_NOT_FOUND_MESSAGE,
    WorkspaceService,
)


def get_workspace_repository(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WorkspaceRepository:
    return WorkspaceRepository(db)


def get_workspace_service(
    workspace_repository: Annotated[WorkspaceRepository, Depends(get_workspace_repository)],
) -> WorkspaceService:
    return WorkspaceService(workspace_repository)


async def get_workspace_member(
    workspace_id: UUID,
    current_user: Annotated[User, Depends(require_active_user)],
    workspace_repository: Annotated[WorkspaceRepository, Depends(get_workspace_repository)],
) -> WorkspaceMember:
    workspace = await workspace_repository.get_active_workspace_by_id(workspace_id)
    if workspace is None:
        raise NotFoundException(WORKSPACE_NOT_FOUND_MESSAGE)

    member = await workspace_repository.get_member(workspace_id, current_user.id)
    if member is None:
        raise NotFoundException(WORKSPACE_NOT_FOUND_MESSAGE)
    return member


async def require_workspace_owner_or_admin(
    member: Annotated[WorkspaceMember, Depends(get_workspace_member)],
) -> WorkspaceMember:
    if member.role not in MANAGE_WORKSPACE_ROLES:
        raise ForbiddenException(WORKSPACE_MANAGE_DENIED_MESSAGE)
    return member


async def require_workspace_member_or_above(
    member: Annotated[WorkspaceMember, Depends(get_workspace_member)],
) -> WorkspaceMember:
    if member.role == WorkspaceRole.VIEWER:
        raise ForbiddenException(WORKSPACE_MANAGE_DENIED_MESSAGE)
    return member


async def require_workspace_owner(
    member: Annotated[WorkspaceMember, Depends(get_workspace_member)],
) -> WorkspaceMember:
    if member.role != WorkspaceRole.OWNER:
        raise ForbiddenException(WORKSPACE_MANAGE_DENIED_MESSAGE)
    return member
