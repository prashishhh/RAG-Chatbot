import asyncio
from datetime import timedelta
from uuid import UUID, uuid4

import pytest

from app.core.exceptions import ForbiddenException, UnauthorizedException
from app.modules.auth.dependencies import get_bearer_token, get_current_user, require_active_user
from app.modules.auth.models import User
from app.modules.auth.security import create_access_token, utc_now
from app.tests.conftest import auth_settings


class FakeAuthRepository:
    def __init__(self, user: User | None = None) -> None:
        self.user = user

    async def get_user_by_id(self, user_id: UUID) -> User | None:
        if self.user is not None and self.user.id == user_id:
            return self.user
        return None


def make_user(*, is_active: bool = True) -> User:
    return User(
        id=uuid4(),
        email="ram@example.com",
        full_name="Ram Sharma",
        password_hash="$argon2id$hash",  # noqa: S106
        is_active=is_active,
        is_verified=False,
    )


def test_get_bearer_token_extracts_token() -> None:
    assert get_bearer_token("Bearer access-token") == "access-token"
    assert get_bearer_token("bearer access-token") == "access-token"


@pytest.mark.parametrize(
    "authorization",
    [None, "", "Basic token", "Bearer", "Bearer   "],
)
def test_get_bearer_token_rejects_missing_or_malformed_header(
    authorization: str | None,
) -> None:
    with pytest.raises(UnauthorizedException):
        get_bearer_token(authorization)


def test_get_current_user_returns_user_for_valid_jwt() -> None:
    async def run_test() -> None:
        user = make_user()
        token = create_access_token(user_id=user.id, settings=auth_settings())

        current_user = await get_current_user(
            token,
            FakeAuthRepository(user),  # type: ignore[arg-type]
            auth_settings(),
        )

        assert current_user is user

    asyncio.run(run_test())


def test_get_current_user_rejects_invalid_jwt() -> None:
    async def run_test() -> None:
        with pytest.raises(UnauthorizedException):
            await get_current_user(
                "invalid-token",
                FakeAuthRepository(),  # type: ignore[arg-type]
                auth_settings(),
            )

    asyncio.run(run_test())


def test_get_current_user_rejects_expired_jwt() -> None:
    async def run_test() -> None:
        user = make_user()
        token = create_access_token(
            user_id=user.id,
            settings=auth_settings(),
            issued_at=utc_now() - timedelta(hours=1),
        )

        with pytest.raises(UnauthorizedException):
            await get_current_user(
                token,
                FakeAuthRepository(user),  # type: ignore[arg-type]
                auth_settings(),
            )

    asyncio.run(run_test())


def test_get_current_user_rejects_missing_user() -> None:
    async def run_test() -> None:
        token = create_access_token(user_id=uuid4(), settings=auth_settings())

        with pytest.raises(UnauthorizedException):
            await get_current_user(
                token,
                FakeAuthRepository(),  # type: ignore[arg-type]
                auth_settings(),
            )

    asyncio.run(run_test())


def test_require_active_user_returns_active_user() -> None:
    async def run_test() -> None:
        user = make_user(is_active=True)

        assert await require_active_user(user) is user

    asyncio.run(run_test())


def test_require_active_user_rejects_inactive_user() -> None:
    async def run_test() -> None:
        with pytest.raises(ForbiddenException, match="inactive"):
            await require_active_user(make_user(is_active=False))

    asyncio.run(run_test())
