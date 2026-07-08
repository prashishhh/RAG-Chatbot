import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import (
    BusinessRuleException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
)
from app.modules.auth.models import User
from app.modules.workspaces.models import Workspace, WorkspaceMember, WorkspaceRole
from app.modules.workspaces.schemas import (
    AddWorkspaceMemberRequest,
    CreateWorkspaceRequest,
    UpdateWorkspaceMemberRoleRequest,
    UpdateWorkspaceRequest,
)
from app.modules.workspaces.service import WorkspaceService


class FakeWorkspaceRepository:
    def __init__(self) -> None:
        self.workspaces_by_id: dict[UUID, Workspace] = {}
        self.workspaces_by_slug: dict[str, Workspace] = {}
        self.members: dict[tuple[UUID, UUID], WorkspaceMember] = {}
        self.users_by_email: dict[str, User] = {}
        self.users_by_id: dict[UUID, User] = {}

    async def create_workspace(self, workspace: Workspace) -> Workspace:
        workspace.id = workspace.id or uuid4()
        workspace.created_at = workspace.created_at or datetime.now(UTC)
        workspace.updated_at = workspace.updated_at or datetime.now(UTC)
        self.workspaces_by_id[workspace.id] = workspace
        self.workspaces_by_slug[workspace.slug] = workspace
        return workspace

    async def create_member(self, member: WorkspaceMember) -> WorkspaceMember:
        member.id = member.id or uuid4()
        member.created_at = member.created_at or datetime.now(UTC)
        self.members[(member.workspace_id, member.user_id)] = member
        return member

    async def get_workspace_by_id(self, workspace_id: UUID) -> Workspace | None:
        return self.workspaces_by_id.get(workspace_id)

    async def get_workspace_by_slug(self, slug: str) -> Workspace | None:
        return self.workspaces_by_slug.get(slug)

    async def get_user_by_email(self, email: str) -> User | None:
        return self.users_by_email.get(email.lower())

    async def get_user_by_id(self, user_id: UUID) -> User | None:
        return self.users_by_id.get(user_id)

    async def get_member(self, workspace_id: UUID, user_id: UUID) -> WorkspaceMember | None:
        return self.members.get((workspace_id, user_id))

    async def list_members(self, workspace_id: UUID) -> list[tuple[WorkspaceMember, User]]:
        return [
            (member, self.users_by_id[member.user_id])
            for (member_workspace_id, _), member in self.members.items()
            if member_workspace_id == workspace_id
        ]

    async def count_owners_for_update(self, workspace_id: UUID) -> int:
        return sum(
            1
            for (member_workspace_id, _), member in self.members.items()
            if member_workspace_id == workspace_id and member.role == WorkspaceRole.OWNER
        )

    async def list_workspaces_for_user(
        self, user_id: UUID
    ) -> list[tuple[Workspace, WorkspaceMember]]:
        return [
            (self.workspaces_by_id[workspace_id], member)
            for (workspace_id, member_user_id), member in self.members.items()
            if member_user_id == user_id and self.workspaces_by_id[workspace_id].is_active
        ]

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
            self.workspaces_by_slug.pop(workspace.slug, None)
            workspace.slug = slug
            self.workspaces_by_slug[slug] = workspace
        workspace.description = description
        return workspace

    async def archive_workspace(self, workspace: Workspace) -> Workspace:
        workspace.is_active = False
        return workspace

    async def update_member_role(
        self,
        member: WorkspaceMember,
        role: WorkspaceRole,
    ) -> WorkspaceMember:
        member.role = role
        return member

    async def remove_member(self, member: WorkspaceMember) -> None:
        self.members.pop((member.workspace_id, member.user_id), None)


class IntegrityErrorWorkspaceRepository(FakeWorkspaceRepository):
    def __init__(self, *, fail_on_update: bool = False) -> None:
        super().__init__()
        self.fail_on_update = fail_on_update

    async def create_workspace(self, workspace: Workspace) -> Workspace:
        if not self.fail_on_update:
            raise IntegrityError("insert", {}, Exception("unique violation"))
        return await super().create_workspace(workspace)

    async def update_workspace(
        self,
        workspace: Workspace,
        *,
        name: str | None = None,
        slug: str | None = None,
        description: str | None = None,
    ) -> Workspace:
        if self.fail_on_update:
            raise IntegrityError("update", {}, Exception("unique violation"))
        return await super().update_workspace(
            workspace,
            name=name,
            slug=slug,
            description=description,
        )


def make_user(
    *,
    email: str = "ram@example.com",
    full_name: str = "Ram Sharma",
    is_active: bool = True,
) -> User:
    return User(
        id=uuid4(),
        email=email,
        full_name=full_name,
        password_hash="$argon2id$hash",  # noqa: S106
        is_active=is_active,
    )


def make_workspace(created_by_user_id: UUID, *, is_active: bool = True) -> Workspace:
    return Workspace(
        id=uuid4(),
        name="Acme Inc",
        slug="acme-inc",
        description=None,
        is_active=is_active,
        created_by_user_id=created_by_user_id,
        created_at=datetime(2026, 7, 8, tzinfo=UTC),
        updated_at=datetime(2026, 7, 8, tzinfo=UTC),
    )


def add_member(
    repository: FakeWorkspaceRepository,
    workspace: Workspace,
    user: User,
    role: WorkspaceRole,
) -> WorkspaceMember:
    member = WorkspaceMember(
        id=uuid4(),
        workspace_id=workspace.id,
        user_id=user.id,
        role=role,
        created_at=datetime(2026, 7, 8, tzinfo=UTC),
    )
    repository.members[(workspace.id, user.id)] = member
    repository.users_by_id[user.id] = user
    repository.users_by_email[user.email] = user
    return member


def test_create_workspace_creates_owner_membership() -> None:
    async def run_test() -> None:
        repository = FakeWorkspaceRepository()
        service = WorkspaceService(repository)  # type: ignore[arg-type]
        user = make_user()

        response = await service.create_async(
            CreateWorkspaceRequest(name="Acme Inc", description="Docs"),
            user,
        )

        assert response.data is not None
        assert response.data.slug == "acme-inc"
        assert response.data.current_user_role == WorkspaceRole.OWNER
        assert len(repository.workspaces_by_id) == 1
        assert len(repository.members) == 1

    asyncio.run(run_test())


def test_create_workspace_rejects_duplicate_slug() -> None:
    async def run_test() -> None:
        repository = FakeWorkspaceRepository()
        user = make_user()
        workspace = make_workspace(user.id)
        repository.workspaces_by_slug[workspace.slug] = workspace
        service = WorkspaceService(repository)  # type: ignore[arg-type]

        with pytest.raises(ConflictException):
            await service.create_async(CreateWorkspaceRequest(name="Acme Inc"), user)

    asyncio.run(run_test())


def test_create_workspace_translates_unique_race_to_conflict() -> None:
    async def run_test() -> None:
        service = WorkspaceService(IntegrityErrorWorkspaceRepository())  # type: ignore[arg-type]

        with pytest.raises(ConflictException):
            await service.create_async(CreateWorkspaceRequest(name="Acme Inc"), make_user())

    asyncio.run(run_test())


def test_list_workspaces_returns_only_repository_memberships() -> None:
    async def run_test() -> None:
        repository = FakeWorkspaceRepository()
        user = make_user()
        workspace = make_workspace(user.id)
        archived_workspace = make_workspace(user.id, is_active=False)
        repository.workspaces_by_id[workspace.id] = workspace
        repository.workspaces_by_id[archived_workspace.id] = archived_workspace
        add_member(repository, workspace, user, WorkspaceRole.MEMBER)
        add_member(repository, archived_workspace, user, WorkspaceRole.ADMIN)
        service = WorkspaceService(repository)  # type: ignore[arg-type]

        response = await service.list_async(user)

        assert response.data is not None
        assert len(response.data) == 1
        assert response.data[0].workspace_id == workspace.id
        assert response.data[0].current_user_role == WorkspaceRole.MEMBER

    asyncio.run(run_test())


def test_get_workspace_requires_membership_and_active_workspace() -> None:
    async def run_test() -> None:
        repository = FakeWorkspaceRepository()
        user = make_user()
        workspace = make_workspace(user.id)
        repository.workspaces_by_id[workspace.id] = workspace
        service = WorkspaceService(repository)  # type: ignore[arg-type]

        with pytest.raises(NotFoundException):
            await service.get_by_id_async(workspace.id, user)

        add_member(repository, workspace, user, WorkspaceRole.VIEWER)
        workspace.is_active = False
        with pytest.raises(NotFoundException):
            await service.get_by_id_async(workspace.id, user)

    asyncio.run(run_test())


def test_update_workspace_requires_owner_or_admin() -> None:
    async def run_test() -> None:
        repository = FakeWorkspaceRepository()
        user = make_user()
        workspace = make_workspace(user.id)
        repository.workspaces_by_id[workspace.id] = workspace
        add_member(repository, workspace, user, WorkspaceRole.MEMBER)
        service = WorkspaceService(repository)  # type: ignore[arg-type]

        with pytest.raises(ForbiddenException):
            await service.update_async(
                workspace.id,
                UpdateWorkspaceRequest(name="New Name"),
                user,
            )

    asyncio.run(run_test())


def test_update_workspace_updates_fields_for_admin() -> None:
    async def run_test() -> None:
        repository = FakeWorkspaceRepository()
        user = make_user()
        workspace = make_workspace(user.id)
        repository.workspaces_by_id[workspace.id] = workspace
        repository.workspaces_by_slug[workspace.slug] = workspace
        add_member(repository, workspace, user, WorkspaceRole.ADMIN)
        service = WorkspaceService(repository)  # type: ignore[arg-type]

        response = await service.update_async(
            workspace.id,
            UpdateWorkspaceRequest(name="Acme Knowledge Base", description="Updated"),
            user,
        )

        assert response.data is not None
        assert response.data.name == "Acme Knowledge Base"
        assert response.data.slug == "acme-knowledge-base"
        assert response.data.description == "Updated"

    asyncio.run(run_test())


def test_update_workspace_rejects_duplicate_slug() -> None:
    async def run_test() -> None:
        repository = FakeWorkspaceRepository()
        user = make_user()
        workspace = make_workspace(user.id)
        other_workspace = Workspace(
            id=uuid4(),
            name="Taken Name",
            slug="taken-name",
            description=None,
            is_active=True,
            created_by_user_id=user.id,
            created_at=datetime(2026, 7, 8, tzinfo=UTC),
            updated_at=datetime(2026, 7, 8, tzinfo=UTC),
        )
        repository.workspaces_by_id[workspace.id] = workspace
        repository.workspaces_by_slug[workspace.slug] = workspace
        repository.workspaces_by_slug[other_workspace.slug] = other_workspace
        add_member(repository, workspace, user, WorkspaceRole.ADMIN)
        service = WorkspaceService(repository)  # type: ignore[arg-type]

        with pytest.raises(ConflictException):
            await service.update_async(
                workspace.id,
                UpdateWorkspaceRequest(name="Taken Name"),
                user,
            )

    asyncio.run(run_test())


def test_update_workspace_translates_unique_race_to_conflict() -> None:
    async def run_test() -> None:
        repository = IntegrityErrorWorkspaceRepository(fail_on_update=True)
        user = make_user()
        workspace = make_workspace(user.id)
        repository.workspaces_by_id[workspace.id] = workspace
        add_member(repository, workspace, user, WorkspaceRole.ADMIN)
        service = WorkspaceService(repository)  # type: ignore[arg-type]

        with pytest.raises(ConflictException):
            await service.update_async(
                workspace.id,
                UpdateWorkspaceRequest(name="Acme Knowledge Base"),
                user,
            )

    asyncio.run(run_test())


def test_archive_workspace_requires_management_role() -> None:
    async def run_test() -> None:
        repository = FakeWorkspaceRepository()
        user = make_user()
        workspace = make_workspace(user.id)
        repository.workspaces_by_id[workspace.id] = workspace
        add_member(repository, workspace, user, WorkspaceRole.VIEWER)
        service = WorkspaceService(repository)  # type: ignore[arg-type]

        with pytest.raises(ForbiddenException):
            await service.archive_async(workspace.id, user)

        repository.members[(workspace.id, user.id)].role = WorkspaceRole.OWNER
        response = await service.archive_async(workspace.id, user)

        assert response.success is True
        assert workspace.is_active is False

    asyncio.run(run_test())


def test_workspace_service_blocks_inactive_user() -> None:
    async def run_test() -> None:
        repository = FakeWorkspaceRepository()
        service = WorkspaceService(repository)  # type: ignore[arg-type]

        with pytest.raises(ForbiddenException, match="inactive"):
            await service.create_async(
                CreateWorkspaceRequest(name="Acme Inc"),
                make_user(is_active=False),
            )

    asyncio.run(run_test())


def test_list_members_requires_workspace_membership() -> None:
    async def run_test() -> None:
        repository = FakeWorkspaceRepository()
        user = make_user()
        workspace = make_workspace(user.id)
        repository.workspaces_by_id[workspace.id] = workspace
        service = WorkspaceService(repository)  # type: ignore[arg-type]

        with pytest.raises(NotFoundException):
            await service.list_members_async(workspace.id, user)

        add_member(repository, workspace, user, WorkspaceRole.VIEWER)
        response = await service.list_members_async(workspace.id, user)

        assert response.data is not None
        assert response.data[0].user_id == user.id

    asyncio.run(run_test())


def test_add_member_requires_owner_or_admin() -> None:
    async def run_test() -> None:
        repository = FakeWorkspaceRepository()
        actor = make_user()
        target = make_user(email="sita@example.com", full_name="Sita Sharma")
        workspace = make_workspace(actor.id)
        repository.workspaces_by_id[workspace.id] = workspace
        repository.users_by_email[target.email] = target
        repository.users_by_id[target.id] = target
        add_member(repository, workspace, actor, WorkspaceRole.MEMBER)
        service = WorkspaceService(repository)  # type: ignore[arg-type]

        with pytest.raises(ForbiddenException):
            await service.add_member_async(
                workspace.id,
                AddWorkspaceMemberRequest(email=target.email, role=WorkspaceRole.VIEWER),
                actor,
            )

    asyncio.run(run_test())


def test_admin_can_add_existing_active_member() -> None:
    async def run_test() -> None:
        repository = FakeWorkspaceRepository()
        actor = make_user()
        target = make_user(email="sita@example.com", full_name="Sita Sharma")
        workspace = make_workspace(actor.id)
        repository.workspaces_by_id[workspace.id] = workspace
        repository.users_by_email[target.email] = target
        repository.users_by_id[target.id] = target
        add_member(repository, workspace, actor, WorkspaceRole.ADMIN)
        service = WorkspaceService(repository)  # type: ignore[arg-type]

        response = await service.add_member_async(
            workspace.id,
            AddWorkspaceMemberRequest(email=target.email, role=WorkspaceRole.MEMBER),
            actor,
        )

        assert response.data is not None
        assert response.data.user_id == target.id
        assert response.data.role == WorkspaceRole.MEMBER

    asyncio.run(run_test())


def test_admin_cannot_add_owner() -> None:
    async def run_test() -> None:
        repository = FakeWorkspaceRepository()
        actor = make_user()
        target = make_user(email="sita@example.com")
        workspace = make_workspace(actor.id)
        repository.workspaces_by_id[workspace.id] = workspace
        repository.users_by_email[target.email] = target
        repository.users_by_id[target.id] = target
        add_member(repository, workspace, actor, WorkspaceRole.ADMIN)
        service = WorkspaceService(repository)  # type: ignore[arg-type]

        with pytest.raises(ForbiddenException):
            await service.add_member_async(
                workspace.id,
                AddWorkspaceMemberRequest(email=target.email, role=WorkspaceRole.OWNER),
                actor,
            )

    asyncio.run(run_test())


def test_add_member_rejects_missing_inactive_and_duplicate_user() -> None:
    async def run_test() -> None:
        repository = FakeWorkspaceRepository()
        actor = make_user()
        target = make_user(email="sita@example.com", is_active=False)
        workspace = make_workspace(actor.id)
        repository.workspaces_by_id[workspace.id] = workspace
        repository.users_by_email[target.email] = target
        repository.users_by_id[target.id] = target
        add_member(repository, workspace, actor, WorkspaceRole.OWNER)
        service = WorkspaceService(repository)  # type: ignore[arg-type]

        with pytest.raises(NotFoundException):
            await service.add_member_async(
                workspace.id,
                AddWorkspaceMemberRequest(email="missing@example.com", role=WorkspaceRole.MEMBER),
                actor,
            )

        with pytest.raises(NotFoundException):
            await service.add_member_async(
                workspace.id,
                AddWorkspaceMemberRequest(email=target.email, role=WorkspaceRole.MEMBER),
                actor,
            )

        target.is_active = True
        add_member(repository, workspace, target, WorkspaceRole.MEMBER)
        with pytest.raises(ConflictException):
            await service.add_member_async(
                workspace.id,
                AddWorkspaceMemberRequest(email=target.email, role=WorkspaceRole.MEMBER),
                actor,
            )

    asyncio.run(run_test())


def test_owner_can_promote_member_to_owner() -> None:
    async def run_test() -> None:
        repository = FakeWorkspaceRepository()
        owner = make_user()
        target = make_user(email="sita@example.com")
        workspace = make_workspace(owner.id)
        repository.workspaces_by_id[workspace.id] = workspace
        add_member(repository, workspace, owner, WorkspaceRole.OWNER)
        add_member(repository, workspace, target, WorkspaceRole.MEMBER)
        service = WorkspaceService(repository)  # type: ignore[arg-type]

        response = await service.update_member_role_async(
            workspace.id,
            target.id,
            UpdateWorkspaceMemberRoleRequest(role=WorkspaceRole.OWNER),
            owner,
        )

        assert response.data is not None
        assert response.data.role == WorkspaceRole.OWNER

    asyncio.run(run_test())


def test_admin_cannot_promote_member_to_owner() -> None:
    async def run_test() -> None:
        repository = FakeWorkspaceRepository()
        admin = make_user()
        target = make_user(email="sita@example.com")
        workspace = make_workspace(admin.id)
        repository.workspaces_by_id[workspace.id] = workspace
        add_member(repository, workspace, admin, WorkspaceRole.ADMIN)
        add_member(repository, workspace, target, WorkspaceRole.MEMBER)
        service = WorkspaceService(repository)  # type: ignore[arg-type]

        with pytest.raises(ForbiddenException):
            await service.update_member_role_async(
                workspace.id,
                target.id,
                UpdateWorkspaceMemberRoleRequest(role=WorkspaceRole.OWNER),
                admin,
            )

    asyncio.run(run_test())


def test_last_owner_cannot_be_demoted_or_removed() -> None:
    async def run_test() -> None:
        repository = FakeWorkspaceRepository()
        owner = make_user()
        workspace = make_workspace(owner.id)
        repository.workspaces_by_id[workspace.id] = workspace
        add_member(repository, workspace, owner, WorkspaceRole.OWNER)
        service = WorkspaceService(repository)  # type: ignore[arg-type]

        with pytest.raises(BusinessRuleException):
            await service.update_member_role_async(
                workspace.id,
                owner.id,
                UpdateWorkspaceMemberRoleRequest(role=WorkspaceRole.ADMIN),
                owner,
            )

        with pytest.raises(BusinessRuleException):
            await service.remove_member_async(workspace.id, owner.id, owner)

    asyncio.run(run_test())


def test_admin_can_remove_member_but_not_owner() -> None:
    async def run_test() -> None:
        repository = FakeWorkspaceRepository()
        admin = make_user()
        member = make_user(email="sita@example.com")
        owner = make_user(email="owner@example.com")
        workspace = make_workspace(admin.id)
        repository.workspaces_by_id[workspace.id] = workspace
        add_member(repository, workspace, admin, WorkspaceRole.ADMIN)
        add_member(repository, workspace, member, WorkspaceRole.MEMBER)
        add_member(repository, workspace, owner, WorkspaceRole.OWNER)
        service = WorkspaceService(repository)  # type: ignore[arg-type]

        response = await service.remove_member_async(workspace.id, member.id, admin)

        assert response.success is True
        assert (workspace.id, member.id) not in repository.members

        with pytest.raises(ForbiddenException):
            await service.remove_member_async(workspace.id, owner.id, admin)

    asyncio.run(run_test())


def test_update_and_remove_missing_member_return_not_found() -> None:
    async def run_test() -> None:
        repository = FakeWorkspaceRepository()
        actor = make_user()
        workspace = make_workspace(actor.id)
        repository.workspaces_by_id[workspace.id] = workspace
        add_member(repository, workspace, actor, WorkspaceRole.ADMIN)
        service = WorkspaceService(repository)  # type: ignore[arg-type]
        missing_user_id = uuid4()

        with pytest.raises(NotFoundException):
            await service.update_member_role_async(
                workspace.id,
                missing_user_id,
                UpdateWorkspaceMemberRoleRequest(role=WorkspaceRole.VIEWER),
                actor,
            )

        with pytest.raises(NotFoundException):
            await service.remove_member_async(workspace.id, missing_user_id, actor)

    asyncio.run(run_test())
