from uuid import uuid4

import pytest

from app.core.exceptions import UnauthorizedException
from app.modules.auth import security
from app.tests.conftest import auth_settings


def test_password_hash_uses_argon2id_and_verifies() -> None:
    password_hash = security.hash_password("Password123!")  # noqa: S106

    assert password_hash.startswith("$argon2id$")
    assert security.verify_password("Password123!", password_hash) is True  # noqa: S106
    assert security.verify_password("WrongPassword123!", password_hash) is False  # noqa: S106


def test_access_token_round_trip_returns_minimal_payload() -> None:
    user_id = uuid4()
    settings = auth_settings()
    token = security.create_access_token(
        user_id=user_id,
        settings=settings,
        issued_at=security.utc_now(),
    )

    payload = security.decode_access_token(token, settings=settings)

    assert payload.sub == user_id
    assert payload.token_type == security.ACCESS_TOKEN_TYPE
    assert payload.exp - payload.iat == 900


def test_invalid_access_token_raises_unauthorized() -> None:
    with pytest.raises(UnauthorizedException):
        security.decode_access_token("not-a-valid-token", settings=auth_settings())


def test_expiry_helpers_use_short_access_and_long_refresh_windows() -> None:
    settings = auth_settings()
    access_delta = security.access_token_expires_at(settings) - security.utc_now()
    refresh_delta = security.refresh_token_expires_at(settings) - security.utc_now()

    assert 14 * 60 <= access_delta.total_seconds() <= 15 * 60
    assert 29 * 24 * 60 * 60 <= refresh_delta.total_seconds() <= 30 * 24 * 60 * 60


def test_refresh_token_pair_uses_opaque_raw_token_and_sha256_hash() -> None:
    raw_token, token_hash = security.create_refresh_token_pair(auth_settings())

    assert raw_token
    assert raw_token != token_hash
    assert len(token_hash) == 64
    assert security.verify_refresh_token_hash(raw_token, token_hash) is True


def test_refresh_token_hash_verification_rejects_wrong_token() -> None:
    _, token_hash = security.create_refresh_token_pair(auth_settings())

    assert security.verify_refresh_token_hash("wrong-token", token_hash) is False


def test_refresh_token_generation_creates_new_token_for_rotation() -> None:
    settings = auth_settings()
    first = security.create_refresh_token_pair(settings)
    second = security.create_refresh_token_pair(settings)

    assert first[0] != second[0]
    assert first[1] != second[1]
