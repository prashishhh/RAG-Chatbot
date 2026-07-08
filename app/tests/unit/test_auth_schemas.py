from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.auth.schemas import (
    CurrentUserResponse,
    LoginResponse,
    RefreshTokenResponse,
    RegisterRequest,
    RegisterResponse,
)


def test_register_request_accepts_api_aliases() -> None:
    request = RegisterRequest(
        fullName="Ram Sharma",
        email="ram@example.com",
        password="Password123!",  # noqa: S106
        confirmPassword="Password123!",
    )

    assert request.full_name == "Ram Sharma"
    assert request.model_dump(by_alias=True)["fullName"] == "Ram Sharma"


def test_register_request_rejects_password_mismatch() -> None:
    with pytest.raises(ValidationError, match="Password and confirmation password must match"):
        RegisterRequest(
            fullName="Ram Sharma",
            email="ram@example.com",
            password="Password123!",  # noqa: S106
            confirmPassword="Different123!",
        )


def test_register_response_does_not_expose_password_hash() -> None:
    response = RegisterResponse(
        userId=uuid4(),
        fullName="Ram Sharma",
        email="ram@example.com",
    )

    payload = response.model_dump(by_alias=True)
    assert "password" not in payload
    assert "passwordHash" not in payload
    assert "password_hash" not in payload


def test_login_response_exposes_raw_tokens_but_not_refresh_token_metadata() -> None:
    response = LoginResponse(
        accessToken="access-token",
        refreshToken="refresh-token",
        expiresIn=900,
        user={
            "userId": uuid4(),
            "fullName": "Ram Sharma",
            "email": "ram@example.com",
        },
    )

    payload = response.model_dump(by_alias=True)
    assert payload["refreshToken"] == "refresh-token"
    assert "tokenHash" not in payload
    assert "revokedAt" not in payload
    assert "replacedByTokenId" not in payload


def test_refresh_response_does_not_expose_refresh_token_db_metadata() -> None:
    response = RefreshTokenResponse(
        accessToken="new-access-token",
        refreshToken="new-refresh-token",
        expiresIn=900,
    )

    payload = response.model_dump(by_alias=True)
    assert set(payload) == {"accessToken", "refreshToken", "tokenType", "expiresIn"}


def test_current_user_response_does_not_expose_password_or_token_fields() -> None:
    response = CurrentUserResponse(
        userId=uuid4(),
        fullName="Ram Sharma",
        email="ram@example.com",
        isActive=True,
        isVerified=False,
    )

    payload = response.model_dump(by_alias=True)
    assert "passwordHash" not in payload
    assert "refreshTokens" not in payload
    assert "tokenHash" not in payload


@pytest.mark.parametrize(
    "password,error_msg",
    [
        ("lowercase123!", "at least one uppercase letter"),
        ("UPPERCASE123!", "at least one lowercase letter"),
        ("NoDigitsHere!", "at least one digit"),
        ("NoSpecial123", "at least one special character"),
    ],
)
def test_register_request_password_complexity_failure(password: str, error_msg: str) -> None:
    with pytest.raises(ValidationError, match=error_msg):
        RegisterRequest(
            fullName="Ram Sharma",
            email="ram@example.com",
            password=password,
            confirmPassword=password,
        )


def test_register_request_password_complexity_success() -> None:
    request = RegisterRequest(
        fullName="Ram Sharma",
        email="ram@example.com",
        password="Password123!",  # noqa: S106
        confirmPassword="Password123!",
    )
    assert request.password == "Password123!"  # noqa: S105
