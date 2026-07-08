import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.core.exceptions import ConflictException, ForbiddenException, UnauthorizedException
from app.modules.auth.models import RefreshToken, User
from app.modules.auth.schemas import (
    LoginRequest,
    LogoutRequest,
    RefreshTokenRequest,
    RegisterRequest,
)
from app.modules.auth.security import create_refresh_token_pair, hash_password, hash_refresh_token
from app.modules.auth.service import (
    INVALID_LOGIN_MESSAGE,
    INVALID_REFRESH_TOKEN_MESSAGE,
    AuthService,
)
from app.tests.conftest import auth_settings


class FakeAuthRepository:
    def __init__(self) -> None:
        self.users_by_email: dict[str, User] = {}
        self.users_by_id: dict[UUID, User] = {}
        self.refresh_tokens_by_hash: dict[str, RefreshToken] = {}
        self.created_refresh_tokens: list[RefreshToken] = []

    async def get_user_by_email(self, email: str) -> User | None:
        return self.users_by_email.get(email.lower())

    async def get_user_by_id(self, user_id: UUID) -> User | None:
        return self.users_by_id.get(user_id)

    async def create_user(self, user: User) -> User:
        user.id = user.id or uuid4()
        self.users_by_email[user.email] = user
        self.users_by_id[user.id] = user
        return user

    async def update_last_login(self, user: User, logged_in_at: datetime) -> User:
        user.last_login_at = logged_in_at
        return user

    async def create_refresh_token(self, refresh_token: RefreshToken) -> RefreshToken:
        refresh_token.id = refresh_token.id or uuid4()
        self.refresh_tokens_by_hash[refresh_token.token_hash] = refresh_token
        self.created_refresh_tokens.append(refresh_token)
        return refresh_token

    async def get_refresh_token_by_hash(self, token_hash: str) -> RefreshToken | None:
        return self.refresh_tokens_by_hash.get(token_hash)

    async def revoke_refresh_token(
        self,
        refresh_token: RefreshToken,
        revoked_at: datetime,
        replaced_by_token_id: UUID | None = None,
    ) -> RefreshToken:
        refresh_token.revoked_at = revoked_at
        refresh_token.replaced_by_token_id = replaced_by_token_id
        return refresh_token

    async def revoke_all_user_refresh_tokens(self, user_id: UUID, revoked_at: datetime) -> int:
        revoked_count = 0
        for refresh_token in self.refresh_tokens_by_hash.values():
            if refresh_token.user_id == user_id and refresh_token.revoked_at is None:
                refresh_token.revoked_at = revoked_at
                revoked_count += 1
        return revoked_count


def make_user(
    *,
    email: str = "ram@example.com",
    password: str = "Password123!",  # noqa: S107
    is_active: bool = True,
) -> User:
    return User(
        id=uuid4(),
        email=email,
        full_name="Ram Sharma",
        password_hash=hash_password(password),
        is_active=is_active,
        is_verified=False,
    )


def make_refresh_token(user_id: UUID, raw_token: str, *, expired: bool = False) -> RefreshToken:
    return RefreshToken(
        id=uuid4(),
        user_id=user_id,
        token_hash=hash_refresh_token(raw_token),
        expires_at=datetime.now(UTC) + (-timedelta(minutes=1) if expired else timedelta(days=1)),
        created_at=datetime.now(UTC),
    )


def test_register_creates_user_and_returns_safe_response() -> None:
    async def run_test() -> None:
        repository = FakeAuthRepository()
        service = AuthService(repository, auth_settings())  # type: ignore[arg-type]
        request = RegisterRequest(
            fullName="Ram Sharma",
            email="Ram@Example.com",
            password="Password123!",  # noqa: S106
            confirmPassword="Password123!",
        )

        response = await service.register_async(request)

        assert response.success is True
        assert response.data is not None
        assert response.data.email == "ram@example.com"
        assert "password" not in response.data.model_dump()
        assert repository.users_by_email["ram@example.com"].password_hash.startswith("$argon2id$")

    asyncio.run(run_test())


def test_register_rejects_duplicate_email() -> None:
    async def run_test() -> None:
        repository = FakeAuthRepository()
        user = make_user()
        repository.users_by_email[user.email] = user
        service = AuthService(repository, auth_settings())  # type: ignore[arg-type]

        with pytest.raises(ConflictException):
            await service.register_async(
                RegisterRequest(
                    fullName="Ram Sharma",
                    email=user.email,
                    password="Password123!",  # noqa: S106
                    confirmPassword="Password123!",
                )
            )

    asyncio.run(run_test())


def test_login_uses_generic_failure_for_unknown_email_and_wrong_password() -> None:
    async def run_test() -> None:
        repository = FakeAuthRepository()
        user = make_user()
        repository.users_by_email[user.email] = user
        service = AuthService(repository, auth_settings())  # type: ignore[arg-type]

        with pytest.raises(UnauthorizedException, match=INVALID_LOGIN_MESSAGE):
            await service.login_async(
                LoginRequest(email="missing@example.com", password="Password123!")  # noqa: S106
            )

        with pytest.raises(UnauthorizedException, match=INVALID_LOGIN_MESSAGE):
            await service.login_async(
                LoginRequest(email=user.email, password="WrongPassword123!")  # noqa: S106
            )

    asyncio.run(run_test())


def test_login_blocks_inactive_user() -> None:
    async def run_test() -> None:
        repository = FakeAuthRepository()
        user = make_user(is_active=False)
        repository.users_by_email[user.email] = user
        service = AuthService(repository, auth_settings())  # type: ignore[arg-type]

        with pytest.raises(ForbiddenException, match="inactive"):
            await service.login_async(
                LoginRequest(email=user.email, password="Password123!")  # noqa: S106
            )

    asyncio.run(run_test())


def test_login_success_updates_last_login_and_creates_refresh_token() -> None:
    async def run_test() -> None:
        repository = FakeAuthRepository()
        user = make_user()
        repository.users_by_email[user.email] = user
        service = AuthService(repository, auth_settings())  # type: ignore[arg-type]

        response = await service.login_async(
            LoginRequest(email=user.email, password="Password123!")  # noqa: S106
        )

        assert response.data is not None
        assert response.data.access_token
        assert response.data.refresh_token
        assert user.last_login_at is not None
        assert len(repository.created_refresh_tokens) == 1

    asyncio.run(run_test())


def test_refresh_access_token_rotates_refresh_token() -> None:
    async def run_test() -> None:
        repository = FakeAuthRepository()
        user = make_user()
        raw_token, _ = create_refresh_token_pair(auth_settings())
        old_token = make_refresh_token(user.id, raw_token)
        repository.refresh_tokens_by_hash[old_token.token_hash] = old_token
        service = AuthService(repository, auth_settings())  # type: ignore[arg-type]

        response = await service.refresh_access_token_async(
            RefreshTokenRequest(refreshToken=raw_token)
        )

        assert response.data is not None
        assert response.data.access_token
        assert response.data.refresh_token != raw_token
        assert old_token.revoked_at is not None
        assert old_token.replaced_by_token_id == repository.created_refresh_tokens[-1].id

    asyncio.run(run_test())


def test_refresh_rejects_revoked_and_expired_tokens() -> None:
    async def run_test() -> None:
        repository = FakeAuthRepository()
        user = make_user()
        revoked_raw_token, _ = create_refresh_token_pair(auth_settings())
        revoked_token = make_refresh_token(user.id, revoked_raw_token)
        revoked_token.revoked_at = datetime.now(UTC)
        expired_raw_token, _ = create_refresh_token_pair(auth_settings())
        expired_token = make_refresh_token(user.id, expired_raw_token, expired=True)
        repository.refresh_tokens_by_hash[revoked_token.token_hash] = revoked_token
        repository.refresh_tokens_by_hash[expired_token.token_hash] = expired_token
        service = AuthService(repository, auth_settings())  # type: ignore[arg-type]

        with pytest.raises(UnauthorizedException, match=INVALID_REFRESH_TOKEN_MESSAGE):
            await service.refresh_access_token_async(
                RefreshTokenRequest(refreshToken=revoked_raw_token)
            )

        with pytest.raises(UnauthorizedException, match=INVALID_REFRESH_TOKEN_MESSAGE):
            await service.refresh_access_token_async(
                RefreshTokenRequest(refreshToken=expired_raw_token)
            )

    asyncio.run(run_test())


def test_logout_revokes_existing_token_and_is_idempotent_for_missing_token() -> None:
    async def run_test() -> None:
        repository = FakeAuthRepository()
        user = make_user()
        raw_token, _ = create_refresh_token_pair(auth_settings())
        refresh_token = make_refresh_token(user.id, raw_token)
        repository.refresh_tokens_by_hash[refresh_token.token_hash] = refresh_token
        service = AuthService(repository, auth_settings())  # type: ignore[arg-type]

        response = await service.logout_async(LogoutRequest(refreshToken=raw_token))
        missing_response = await service.logout_async(LogoutRequest(refreshToken="missing-token"))

        assert response.success is True
        assert missing_response.success is True
        assert refresh_token.revoked_at is not None

    asyncio.run(run_test())


def test_get_current_user_blocks_inactive_user() -> None:
    async def run_test() -> None:
        service = AuthService(FakeAuthRepository(), auth_settings())  # type: ignore[arg-type]

        with pytest.raises(ForbiddenException, match="inactive"):
            await service.get_current_user_async(make_user(is_active=False))

    asyncio.run(run_test())


def test_refresh_token_reuse_revokes_token_family() -> None:
    async def run_test() -> None:
        repository = FakeAuthRepository()
        user = make_user()
        repository.users_by_email[user.email] = user
        
        # Create an active refresh token
        active_raw_token, _ = create_refresh_token_pair(auth_settings())
        active_token = make_refresh_token(user.id, active_raw_token)
        repository.refresh_tokens_by_hash[active_token.token_hash] = active_token
        
        # Create a revoked refresh token
        revoked_raw_token, _ = create_refresh_token_pair(auth_settings())
        revoked_token = make_refresh_token(user.id, revoked_raw_token)
        revoked_token.revoked_at = datetime.now(UTC)
        repository.refresh_tokens_by_hash[revoked_token.token_hash] = revoked_token
        
        service = AuthService(repository, auth_settings())  # type: ignore[arg-type]
        
        # Try to use the revoked token
        with pytest.raises(UnauthorizedException, match=INVALID_REFRESH_TOKEN_MESSAGE):
            await service.refresh_access_token_async(
                RefreshTokenRequest(refreshToken=revoked_raw_token)
            )
            
        # Verify that the active token is now also revoked
        assert active_token.revoked_at is not None

    asyncio.run(run_test())

