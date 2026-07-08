import asyncio
from uuid import UUID, uuid4

import pytest

from app.core.exceptions import ForbiddenException, NotFoundException
from app.modules.auth.models import User
from app.modules.workspaces.dependencies import (
    get_workspace_member,
    get_workspace_repository,
    get_workspace_service,
    require_workspace_member_or_above,
    require_workspace_owner,
    require_workspace_owner_or_admin,
)
from app.modules.workspaces.models import Workspace, WorkspaceMember, WorkspaceRole
from app.modules.workspaces.repository import WorkspaceRepository
from app.modules.workspaces.service import WorkspaceService


class FakeWorkspaceRepository:
    def __init__(
        self,
        member: WorkspaceMember | None = None,
        workspace: Workspace | None = None,
    ) -> None:
        self.member = member
        self.workspace = workspace

    async def get_active_workspace_by_id(self, workspace_id: UUID) -> Workspace | None:
        if self.workspace is not None and self.workspace.id == workspace_id:
            return self.workspace
        return None

    async def get_member(self, workspace_id: UUID, user_id: UUID) -> WorkspaceMember | None:
        if (
            self.member is not None
            and self.member.workspace_id == workspace_id
            and self.member.user_id == user_id
        ):
            return self.member
        return None


def make_user() -> User:
    return User(
        id=uuid4(),
        email="ram@example.com",
        full_name="Ram Sharma",
        password_hash="$argon2id$hash",  # noqa: S106
        is_active=True,
    )


def make_member(user_id: UUID, role: WorkspaceRole = WorkspaceRole.MEMBER) -> WorkspaceMember:
    return WorkspaceMember(
        id=uuid4(),
        workspace_id=uuid4(),
        user_id=user_id,
        role=role,
    )


def make_workspace(workspace_id: UUID) -> Workspace:
    return Workspace(
        id=workspace_id,
        name="Acme Inc",
        slug="acme-inc",
        description=None,
        is_active=True,
        created_by_user_id=uuid4(),
    )


def test_get_workspace_repository_returns_repository() -> None:
    assert isinstance(get_workspace_repository(object()), WorkspaceRepository)  # type: ignore[arg-type]


def test_get_workspace_service_returns_service() -> None:
    repository = FakeWorkspaceRepository()

    assert isinstance(get_workspace_service(repository), WorkspaceService)  # type: ignore[arg-type]


def test_get_workspace_member_returns_matching_member() -> None:
    async def run_test() -> None:
        user = make_user()
        member = make_member(user.id)
        repository = FakeWorkspaceRepository(member, make_workspace(member.workspace_id))

        result = await get_workspace_member(
            member.workspace_id,
            user,
            repository,  # type: ignore[arg-type]
        )

        assert result is member

    asyncio.run(run_test())


def test_get_workspace_member_hides_missing_membership() -> None:
    async def run_test() -> None:
        with pytest.raises(NotFoundException):
            await get_workspace_member(
                uuid4(),
                make_user(),
                FakeWorkspaceRepository(),  # type: ignore[arg-type]
            )

    asyncio.run(run_test())


def test_get_workspace_member_hides_archived_workspace() -> None:
    async def run_test() -> None:
        user = make_user()
        member = make_member(user.id)

        with pytest.raises(NotFoundException):
            await get_workspace_member(
                member.workspace_id,
                user,
                FakeWorkspaceRepository(member),  # type: ignore[arg-type]
            )

    asyncio.run(run_test())


@pytest.mark.parametrize("role", [WorkspaceRole.OWNER, WorkspaceRole.ADMIN])
def test_require_workspace_owner_or_admin_allows_management_roles(role: WorkspaceRole) -> None:
    async def run_test() -> None:
        member = make_member(uuid4(), role)

        assert await require_workspace_owner_or_admin(member) is member

    asyncio.run(run_test())


@pytest.mark.parametrize("role", [WorkspaceRole.MEMBER, WorkspaceRole.VIEWER])
def test_require_workspace_owner_or_admin_rejects_non_management_roles(role: WorkspaceRole) -> None:
    async def run_test() -> None:
        with pytest.raises(ForbiddenException):
            await require_workspace_owner_or_admin(make_member(uuid4(), role))

    asyncio.run(run_test())


@pytest.mark.parametrize("role", [WorkspaceRole.OWNER, WorkspaceRole.ADMIN, WorkspaceRole.MEMBER])
def test_require_workspace_member_or_above_rejects_only_viewer(role: WorkspaceRole) -> None:
    async def run_test() -> None:
        member = make_member(uuid4(), role)

        assert await require_workspace_member_or_above(member) is member

    asyncio.run(run_test())


def test_require_workspace_member_or_above_rejects_viewer() -> None:
    async def run_test() -> None:
        with pytest.raises(ForbiddenException):
            await require_workspace_member_or_above(make_member(uuid4(), WorkspaceRole.VIEWER))

    asyncio.run(run_test())


def test_require_workspace_owner_allows_only_owner() -> None:
    async def run_test() -> None:
        owner = make_member(uuid4(), WorkspaceRole.OWNER)

        assert await require_workspace_owner(owner) is owner

        with pytest.raises(ForbiddenException):
            await require_workspace_owner(make_member(uuid4(), WorkspaceRole.ADMIN))

    asyncio.run(run_test())
