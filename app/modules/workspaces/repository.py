from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User
from app.modules.workspaces.models import Workspace, WorkspaceMember, WorkspaceRole


class WorkspaceRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_workspace(self, workspace: Workspace) -> Workspace:
        self.db.add(workspace)
        await self.db.flush()
        return workspace

    async def create_member(self, member: WorkspaceMember) -> WorkspaceMember:
        self.db.add(member)
        await self.db.flush()
        return member

    async def get_workspace_by_id(self, workspace_id: UUID) -> Workspace | None:
        result = await self.db.execute(select(Workspace).where(Workspace.id == workspace_id))
        return result.scalar_one_or_none()

    async def get_active_workspace_by_id(self, workspace_id: UUID) -> Workspace | None:
        result = await self.db.execute(
            select(Workspace).where(Workspace.id == workspace_id, Workspace.is_active.is_(True))
        )
        return result.scalar_one_or_none()

    async def get_workspace_by_slug(self, slug: str) -> Workspace | None:
        result = await self.db.execute(select(Workspace).where(Workspace.slug == slug))
        return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str) -> User | None:
        result = await self.db.execute(select(User).where(User.email == email.lower()))
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: UUID) -> User | None:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_member(self, workspace_id: UUID, user_id: UUID) -> WorkspaceMember | None:
        result = await self.db.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_members(self, workspace_id: UUID) -> list[tuple[WorkspaceMember, User]]:
        result = await self.db.execute(
            select(WorkspaceMember, User)
            .join(User, User.id == WorkspaceMember.user_id)
            .where(WorkspaceMember.workspace_id == workspace_id)
            .order_by(WorkspaceMember.created_at.asc())
        )
        return list(result.all())

    async def count_owners_for_update(self, workspace_id: UUID) -> int:
        result = await self.db.execute(
            select(WorkspaceMember)
            .where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.role == WorkspaceRole.OWNER,
            )
            .with_for_update()
        )
        return len(result.scalars().all())

    async def list_workspaces_for_user(
        self, user_id: UUID
    ) -> list[tuple[Workspace, WorkspaceMember]]:
        result = await self.db.execute(
            select(Workspace, WorkspaceMember)
            .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
            .where(WorkspaceMember.user_id == user_id, Workspace.is_active.is_(True))
            .order_by(Workspace.created_at.desc())
        )
        return list(result.all())

    async def update_workspace(
        self,
        workspace: Workspace,
        *,
        name: str | None = None,
        slug: str | None = None,
        description: str | None = None,
    ) -> Workspace:
        if name is not None:
            workspace.name = name
        if slug is not None:
            workspace.slug = slug
        workspace.description = description
        await self.db.flush()
        return workspace

    async def archive_workspace(self, workspace: Workspace) -> Workspace:
        workspace.is_active = False
        await self.db.flush()
        return workspace

    async def update_member_role(
        self,
        member: WorkspaceMember,
        role: WorkspaceRole,
    ) -> WorkspaceMember:
        member.role = role
        await self.db.flush()
        return member

    async def remove_member(self, member: WorkspaceMember) -> None:
        await self.db.delete(member)
        await self.db.flush()
