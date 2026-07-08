from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.exceptions import ConflictException, ForbiddenException, UnauthorizedException
from app.core.responses import ApiResponse
from app.main import app
from app.modules.auth.dependencies import get_auth_repository, get_auth_service
from app.modules.auth.models import User
from app.modules.auth.schemas import (
    AuthUserResponse,
    CurrentUserResponse,
    LoginResponse,
    RefreshTokenResponse,
    RegisterResponse,
)
from app.modules.auth.security import create_access_token
from app.modules.auth.service import INVALID_LOGIN_MESSAGE, INVALID_REFRESH_TOKEN_MESSAGE
from app.tests.conftest import auth_settings


class FakeAuthService:
    def __init__(self) -> None:
        self.refresh_calls = 0
        self.logout_calls = 0

    async def register_async(self, request) -> ApiResponse[RegisterResponse]:  # type: ignore[no-untyped-def]
        if request.email == "exists@example.com":
            raise ConflictException("A user with this email already exists.")

        return ApiResponse.success_response(
            message="User registered successfully.",
            data=RegisterResponse(
                userId=uuid4(),
                fullName=request.full_name,
                email=request.email,
            ),
        )

    async def login_async(self, request) -> ApiResponse[LoginResponse]:  # type: ignore[no-untyped-def]
        if request.email == "inactive@example.com":
            raise ForbiddenException("User account is inactive.")

        if request.password != "Password123!":  # noqa: S105
            raise UnauthorizedException(INVALID_LOGIN_MESSAGE)

        return ApiResponse.success_response(
            message="Login successful.",
            data=LoginResponse(
                accessToken="access-token",
                refreshToken="refresh-token",
                expiresIn=900,
                user=AuthUserResponse(
                    userId=uuid4(),
                    fullName="Ram Sharma",
                    email=request.email,
                ),
            ),
        )

    async def refresh_access_token_async(
        self,
        request,
    ) -> ApiResponse[RefreshTokenResponse]:  # type: ignore[no-untyped-def]
        self.refresh_calls += 1
        if request.refresh_token == "used-refresh-token":  # noqa: S105
            raise UnauthorizedException(INVALID_REFRESH_TOKEN_MESSAGE)

        return ApiResponse.success_response(
            message="Token refreshed successfully.",
            data=RefreshTokenResponse(
                accessToken="new-access-token",
                refreshToken="new-refresh-token",
                expiresIn=900,
            ),
        )

    async def logout_async(self, request) -> ApiResponse[None]:  # type: ignore[no-untyped-def]
        self.logout_calls += 1
        return ApiResponse.success_response(message="Logged out successfully.", data=None)

    async def get_current_user_async(self, user: User) -> ApiResponse[CurrentUserResponse]:
        return ApiResponse.success_response(
            message="Current user retrieved successfully.",
            data=CurrentUserResponse(
                userId=user.id,
                fullName=user.full_name,
                email=user.email,
                isActive=user.is_active,
                isVerified=user.is_verified,
            ),
        )


class FakeAuthRepository:
    def __init__(self, user: User | None) -> None:
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


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def test_register_success_returns_201_standard_response() -> None:
    app.dependency_overrides[get_auth_service] = FakeAuthService
    client = TestClient(app)

    response = client.post(
        "/api/v1/auth/register",
        json={
            "fullName": "Ram Sharma",
            "email": "ram@example.com",
            "password": "Password123!",
            "confirmPassword": "Password123!",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "User registered successfully."
    assert body["data"]["email"] == "ram@example.com"
    assert "passwordHash" not in body["data"]


def test_duplicate_email_rejected_without_sensitive_details() -> None:
    app.dependency_overrides[get_auth_service] = FakeAuthService
    client = TestClient(app)

    response = client.post(
        "/api/v1/auth/register",
        json={
            "fullName": "Ram Sharma",
            "email": "exists@example.com",
            "password": "Password123!",
            "confirmPassword": "Password123!",
        },
    )

    assert response.status_code == 409
    body = response.json()
    assert body["success"] is False
    assert body["data"] is None
    assert "password" not in str(body).lower()


def test_login_success_returns_tokens() -> None:
    app.dependency_overrides[get_auth_service] = FakeAuthService
    client = TestClient(app)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "ram@example.com", "password": "Password123!"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["accessToken"] == "access-token"
    assert body["data"]["refreshToken"] == "refresh-token"
    assert body["data"]["tokenType"] == "Bearer"


def test_wrong_password_rejected_with_generic_error() -> None:
    app.dependency_overrides[get_auth_service] = FakeAuthService
    client = TestClient(app)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "ram@example.com", "password": "WrongPassword123!"},
    )

    assert response.status_code == 401
    body = response.json()
    assert body["message"] == INVALID_LOGIN_MESSAGE
    assert "wrong" not in body["message"].lower()


def test_inactive_user_cannot_login() -> None:
    app.dependency_overrides[get_auth_service] = FakeAuthService
    client = TestClient(app)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "inactive@example.com", "password": "Password123!"},
    )

    assert response.status_code == 403
    assert response.json()["message"] == "User account is inactive."


def test_refresh_success_rotates_token_response() -> None:
    fake_service = FakeAuthService()
    app.dependency_overrides[get_auth_service] = lambda: fake_service
    client = TestClient(app)

    response = client.post(
        "/api/v1/auth/refresh",
        json={"refreshToken": "old-refresh-token"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["accessToken"] == "new-access-token"
    assert body["data"]["refreshToken"] == "new-refresh-token"
    assert body["data"]["refreshToken"] != "old-refresh-token"
    assert fake_service.refresh_calls == 1


def test_reused_refresh_token_rejected() -> None:
    app.dependency_overrides[get_auth_service] = FakeAuthService
    client = TestClient(app)

    response = client.post(
        "/api/v1/auth/refresh",
        json={"refreshToken": "used-refresh-token"},
    )

    assert response.status_code == 401
    assert response.json()["message"] == INVALID_REFRESH_TOKEN_MESSAGE


def test_logout_revokes_token() -> None:
    fake_service = FakeAuthService()
    app.dependency_overrides[get_auth_service] = lambda: fake_service
    client = TestClient(app)

    response = client.post(
        "/api/v1/auth/logout",
        json={"refreshToken": "refresh-token"},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Logged out successfully."
    assert fake_service.logout_calls == 1


def test_auth_me_requires_valid_access_token() -> None:
    user = make_user()
    app.dependency_overrides[get_auth_repository] = lambda: FakeAuthRepository(user)
    app.dependency_overrides[get_settings] = auth_settings
    client = TestClient(app)

    missing_response = client.get("/api/v1/auth/me")
    token = create_access_token(user_id=user.id, settings=auth_settings())
    valid_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert missing_response.status_code == 401
    assert valid_response.status_code == 200
    assert valid_response.json()["data"]["userId"] == str(user.id)


def test_auth_me_rejects_invalid_and_expired_tokens() -> None:
    user = make_user()
    app.dependency_overrides[get_auth_repository] = lambda: FakeAuthRepository(user)
    app.dependency_overrides[get_settings] = auth_settings
    client = TestClient(app)
    expired_token = create_access_token(
        user_id=user.id,
        settings=auth_settings(),
        issued_at=datetime(2026, 7, 7, tzinfo=UTC),
    )

    invalid_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid-token"},
    )
    expired_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )

    assert invalid_response.status_code == 401
    assert expired_response.status_code == 401
    assert invalid_response.json()["data"] is None
    assert expired_response.json()["data"] is None
