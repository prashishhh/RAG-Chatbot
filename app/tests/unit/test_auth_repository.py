import asyncio
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.core.responses import ApiResponse
from app.modules.auth.models import RefreshToken, User
from app.modules.auth.repository import AuthRepository


class FakeResult:
    def __init__(self, value: object | None = None, rowcount: int | None = None) -> None:
        self.value = value
        self.rowcount = rowcount

    def scalar_one_or_none(self) -> object | None:
        return self.value


class FakeSession:
    def __init__(self, execute_result: FakeResult | None = None) -> None:
        self.added: list[object] = []
        self.flush_count = 0
        self.executed: list[object] = []
        self.execute_result = execute_result or FakeResult()

    def add(self, value: object) -> None:
        self.added.append(value)

    async def flush(self) -> None:
        self.flush_count += 1

    async def execute(self, statement: object) -> FakeResult:
        self.executed.append(statement)
        return self.execute_result


def test_create_user_adds_and_flushes_without_api_response() -> None:
    async def run_test() -> None:
        session = FakeSession()
        repository = AuthRepository(session)  # type: ignore[arg-type]
        user = User(
            email="ram@example.com",
            full_name="Ram Sharma",
            password_hash="$argon2id$hash",  # noqa: S106
        )

        result = await repository.create_user(user)

        assert result is user
        assert not isinstance(result, ApiResponse)
        assert session.added == [user]
        assert session.flush_count == 1

    asyncio.run(run_test())


def test_update_last_login_sets_timestamp_and_flushes() -> None:
    async def run_test() -> None:
        session = FakeSession()
        repository = AuthRepository(session)  # type: ignore[arg-type]
        user = User(
            email="ram@example.com",
            full_name="Ram Sharma",
            password_hash="$argon2id$hash",  # noqa: S106
        )
        logged_in_at = datetime(2026, 7, 7, tzinfo=UTC)

        result = await repository.update_last_login(user, logged_in_at)

        assert result.last_login_at == logged_in_at
        assert session.flush_count == 1

    asyncio.run(run_test())


def test_create_refresh_token_adds_and_flushes_without_plain_token() -> None:
    async def run_test() -> None:
        session = FakeSession()
        repository = AuthRepository(session)  # type: ignore[arg-type]
        refresh_token = RefreshToken(
            user_id=uuid4(),
            token_hash="a" * 64,
            expires_at=datetime(2026, 8, 7, tzinfo=UTC),
            created_at=datetime(2026, 7, 7, tzinfo=UTC),
        )

        result = await repository.create_refresh_token(refresh_token)

        assert result is refresh_token
        assert not hasattr(result, "token")
        assert not hasattr(result, "refresh_token")
        assert session.added == [refresh_token]
        assert session.flush_count == 1

    asyncio.run(run_test())


def test_revoke_refresh_token_sets_revocation_fields() -> None:
    async def run_test() -> None:
        session = FakeSession()
        repository = AuthRepository(session)  # type: ignore[arg-type]
        replacement_id = uuid4()
        revoked_at = datetime(2026, 7, 7, tzinfo=UTC)
        refresh_token = RefreshToken(
            user_id=uuid4(),
            token_hash="a" * 64,
            expires_at=datetime(2026, 8, 7, tzinfo=UTC),
            created_at=datetime(2026, 7, 7, tzinfo=UTC),
        )

        result = await repository.revoke_refresh_token(refresh_token, revoked_at, replacement_id)

        assert result.revoked_at == revoked_at
        assert result.replaced_by_token_id == replacement_id
        assert session.flush_count == 1

    asyncio.run(run_test())


def test_revoke_all_user_refresh_tokens_returns_updated_row_count() -> None:
    async def run_test() -> None:
        session = FakeSession(execute_result=FakeResult(rowcount=3))
        repository = AuthRepository(session)  # type: ignore[arg-type]

        revoked_count = await repository.revoke_all_user_refresh_tokens(
            uuid4(),
            datetime(2026, 7, 7, tzinfo=UTC),
        )

        assert revoked_count == 3
        assert len(session.executed) == 1

    asyncio.run(run_test())


def test_repository_does_not_import_or_return_api_response_contracts() -> None:
    source = Path("app/modules/auth/repository.py").read_text()

    assert "ApiResponse" not in source
    assert "PagedResponse" not in source
    assert "success_response" not in source
    assert "error_response" not in source

