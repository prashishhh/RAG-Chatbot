from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.database import get_db
from app.core.config import Settings, get_settings
from app.core.exceptions import ForbiddenException, UnauthorizedException
from app.modules.auth.models import User
from app.modules.auth.repository import AuthRepository
from app.modules.auth.security import decode_access_token
from app.modules.auth.service import AuthService


def get_auth_repository(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AuthRepository:
    return AuthRepository(db)


def get_auth_service(
    auth_repository: Annotated[AuthRepository, Depends(get_auth_repository)],
) -> AuthService:
    return AuthService(auth_repository)


def get_bearer_token(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> str:
    if authorization is None:
        raise UnauthorizedException()

    scheme, _, token = authorization.strip().partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise UnauthorizedException()

    return token.strip()


async def get_current_user(
    token: Annotated[str, Depends(get_bearer_token)],
    auth_repository: Annotated[AuthRepository, Depends(get_auth_repository)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    token_payload = decode_access_token(token, settings)
    user = await auth_repository.get_user_by_id(token_payload.sub)

    if user is None:
        raise UnauthorizedException()

    return user


async def require_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if not current_user.is_active:
        raise ForbiddenException("User account is inactive.")

    return current_user
