from datetime import UTC, datetime, timedelta
from hashlib import sha256
from hmac import compare_digest
from secrets import token_urlsafe
from uuid import UUID

import jwt
from argon2 import PasswordHasher, Type
from argon2.exceptions import Argon2Error
from jwt import InvalidTokenError
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.core.exceptions import UnauthorizedException
from app.modules.auth.schemas import AccessTokenPayloadInternal

ACCESS_TOKEN_TYPE = "access"  # noqa: S105

_password_hasher = PasswordHasher(type=Type.ID)


def utc_now() -> datetime:
    return datetime.now(UTC)


def access_token_expires_at(settings: Settings | None = None) -> datetime:
    auth_settings = settings or get_settings()
    return utc_now() + timedelta(minutes=auth_settings.jwt_access_token_expire_minutes)


def refresh_token_expires_at(settings: Settings | None = None) -> datetime:
    auth_settings = settings or get_settings()
    return utc_now() + timedelta(days=auth_settings.jwt_refresh_token_expire_days)


def seconds_until(expires_at: datetime) -> int:
    return max(0, int((expires_at - utc_now()).total_seconds()))


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except Argon2Error:
        return False


def create_access_token(
    *,
    user_id: UUID,
    settings: Settings | None = None,
    issued_at: datetime | None = None,
) -> str:
    auth_settings = settings or get_settings()
    issued = issued_at or utc_now()
    expires = issued + timedelta(minutes=auth_settings.jwt_access_token_expire_minutes)
    payload = {
        "sub": str(user_id),
        "iat": int(issued.timestamp()),
        "exp": int(expires.timestamp()),
        "type": ACCESS_TOKEN_TYPE,
    }

    return jwt.encode(
        payload,
        auth_settings.jwt_secret_key.get_secret_value(),
        algorithm=auth_settings.jwt_algorithm,
    )


def decode_access_token(
    token: str,
    settings: Settings | None = None,
) -> AccessTokenPayloadInternal:
    auth_settings = settings or get_settings()

    try:
        payload = jwt.decode(
            token,
            auth_settings.jwt_secret_key.get_secret_value(),
            algorithms=[auth_settings.jwt_algorithm],
        )
        token_payload = AccessTokenPayloadInternal.model_validate(payload)
    except (InvalidTokenError, ValidationError) as exc:
        raise UnauthorizedException() from exc

    if token_payload.token_type != ACCESS_TOKEN_TYPE:
        raise UnauthorizedException()

    return token_payload


def generate_refresh_token(settings: Settings | None = None) -> str:
    auth_settings = settings or get_settings()
    return token_urlsafe(auth_settings.refresh_token_bytes)


def hash_refresh_token(refresh_token: str) -> str:
    return sha256(refresh_token.encode("utf-8")).hexdigest()


def verify_refresh_token_hash(refresh_token: str, token_hash: str) -> bool:
    return compare_digest(hash_refresh_token(refresh_token), token_hash)


def create_refresh_token_pair(settings: Settings | None = None) -> tuple[str, str]:
    raw_token = generate_refresh_token(settings)
    return raw_token, hash_refresh_token(raw_token)
