import asyncio
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.core.responses import ApiResponse
from app.modules.auth.models import User
from app.modules.workspaces.models import Workspace, WorkspaceMember, WorkspaceRole
from app.modules.workspaces.repository import WorkspaceRepository


class FakeResult:
    def __init__(self, value: object | None = None, rows: list[object] | None = None) -> None:
        self.value = value
        self.rows = rows or []

    def scalar_one_or_none(self) -> object | None:
        return self.value

    def scalar_one(self) -> object:
        return self.value

    def all(self) -> list[object]:
        return self.rows

    def scalars(self) -> "FakeResult":
        return self


class FakeSession:
    def __init__(self, execute_result: FakeResult | None = None) -> None:
        self.added: list[object] = []
        self.deleted: list[object] = []
        self.flush_count = 0
        self.executed: list[object] = []
        self.execute_result = execute_result or FakeResult()

    def add(self, value: object) -> None:
        self.added.append(value)

    async def delete(self, value: object) -> None:
        self.deleted.append(value)

    async def flush(self) -> None:
        self.flush_count += 1

    async def execute(self, statement: object) -> FakeResult:
        self.executed.append(statement)
        return self.execute_result


def make_workspace() -> Workspace:
    return Workspace(
        name="Acme Inc",
        slug="acme-inc",
        description=None,
        created_by_user_id=uuid4(),
    )


def make_user() -> User:
    return User(
        id=uuid4(),
        email="sita@example.com",
        full_name="Sita Sharma",
        password_hash="$argon2id$hash",  # noqa: S106
        is_active=True,
    )


def test_create_workspace_adds_and_flushes_without_api_response() -> None:
    async def run_test() -> None:
        session = FakeSession()
        repository = WorkspaceRepository(session)  # type: ignore[arg-type]
        workspace = make_workspace()

        result = await repository.create_workspace(workspace)

        assert result is workspace
        assert not isinstance(result, ApiResponse)
        assert session.added == [workspace]
        assert session.flush_count == 1

    asyncio.run(run_test())


def test_create_member_adds_and_flushes() -> None:
    async def run_test() -> None:
        session = FakeSession()
        repository = WorkspaceRepository(session)  # type: ignore[arg-type]
        member = WorkspaceMember(
            workspace_id=uuid4(),
            user_id=uuid4(),
            role=WorkspaceRole.OWNER,
            created_at=datetime(2026, 7, 8, tzinfo=UTC),
        )

        result = await repository.create_member(member)

        assert result is member
        assert session.added == [member]
        assert session.flush_count == 1

    asyncio.run(run_test())


def test_get_member_executes_tenant_lookup() -> None:
    async def run_test() -> None:
        member = WorkspaceMember(
            workspace_id=uuid4(),
            user_id=uuid4(),
            role=WorkspaceRole.ADMIN,
            created_at=datetime(2026, 7, 8, tzinfo=UTC),
        )
        session = FakeSession(execute_result=FakeResult(value=member))
        repository = WorkspaceRepository(session)  # type: ignore[arg-type]

        result = await repository.get_member(member.workspace_id, member.user_id)

        assert result is member
        assert len(session.executed) == 1

    asyncio.run(run_test())


def test_get_user_by_email_normalizes_email() -> None:
    async def run_test() -> None:
        user = make_user()
        session = FakeSession(execute_result=FakeResult(value=user))
        repository = WorkspaceRepository(session)  # type: ignore[arg-type]

        result = await repository.get_user_by_email("SITA@EXAMPLE.COM")

        assert result is user
        assert len(session.executed) == 1

    asyncio.run(run_test())


def test_list_members_returns_member_user_rows_for_workspace() -> None:
    async def run_test() -> None:
        row = (object(), make_user())
        session = FakeSession(execute_result=FakeResult(rows=[row]))
        repository = WorkspaceRepository(session)  # type: ignore[arg-type]

        result = await repository.list_members(uuid4())

        assert result == [row]
        assert len(session.executed) == 1

    asyncio.run(run_test())


def test_count_owners_for_update_locks_owner_rows() -> None:
    async def run_test() -> None:
        session = FakeSession(execute_result=FakeResult(rows=[object(), object()]))
        repository = WorkspaceRepository(session)  # type: ignore[arg-type]

        result = await repository.count_owners_for_update(uuid4())

        assert result == 2
        assert len(session.executed) == 1

    asyncio.run(run_test())


def test_get_active_workspace_by_id_executes_active_lookup() -> None:
    async def run_test() -> None:
        workspace = make_workspace()
        session = FakeSession(execute_result=FakeResult(value=workspace))
        repository = WorkspaceRepository(session)  # type: ignore[arg-type]

        result = await repository.get_active_workspace_by_id(uuid4())

        assert result is workspace
        assert len(session.executed) == 1

    asyncio.run(run_test())


def test_list_workspaces_for_user_returns_workspace_member_rows() -> None:
    async def run_test() -> None:
        row = (make_workspace(), object())
        session = FakeSession(execute_result=FakeResult(rows=[row]))
        repository = WorkspaceRepository(session)  # type: ignore[arg-type]

        result = await repository.list_workspaces_for_user(uuid4())

        assert result == [row]
        assert len(session.executed) == 1

    asyncio.run(run_test())


def test_update_workspace_sets_mutable_fields_and_flushes() -> None:
    async def run_test() -> None:
        session = FakeSession()
        repository = WorkspaceRepository(session)  # type: ignore[arg-type]
        workspace = make_workspace()

        result = await repository.update_workspace(
            workspace,
            name="Acme KB",
            slug="acme-kb",
            description="Docs",
        )

        assert result.name == "Acme KB"
        assert result.slug == "acme-kb"
        assert result.description == "Docs"
        assert session.flush_count == 1

    asyncio.run(run_test())


def test_archive_workspace_sets_inactive_and_flushes() -> None:
    async def run_test() -> None:
        session = FakeSession()
        repository = WorkspaceRepository(session)  # type: ignore[arg-type]
        workspace = make_workspace()

        result = await repository.archive_workspace(workspace)

        assert result.is_active is False
        assert session.flush_count == 1

    asyncio.run(run_test())


def test_update_member_role_sets_role_and_flushes() -> None:
    async def run_test() -> None:
        session = FakeSession()
        repository = WorkspaceRepository(session)  # type: ignore[arg-type]
        member = WorkspaceMember(
            workspace_id=uuid4(),
            user_id=uuid4(),
            role=WorkspaceRole.MEMBER,
            created_at=datetime(2026, 7, 8, tzinfo=UTC),
        )

        result = await repository.update_member_role(member, WorkspaceRole.ADMIN)

        assert result.role == WorkspaceRole.ADMIN
        assert session.flush_count == 1

    asyncio.run(run_test())


def test_remove_member_deletes_and_flushes() -> None:
    async def run_test() -> None:
        session = FakeSession()
        repository = WorkspaceRepository(session)  # type: ignore[arg-type]
        member = WorkspaceMember(
            workspace_id=uuid4(),
            user_id=uuid4(),
            role=WorkspaceRole.VIEWER,
            created_at=datetime(2026, 7, 8, tzinfo=UTC),
        )

        await repository.remove_member(member)

        assert session.deleted == [member]
        assert session.flush_count == 1

    asyncio.run(run_test())


def test_repository_does_not_import_or_return_api_response_contracts() -> None:
    source = Path("app/modules/workspaces/repository.py").read_text()

    assert "ApiResponse" not in source
    assert "PagedResponse" not in source
    assert "success_response" not in source
    assert "error_response" not in source
