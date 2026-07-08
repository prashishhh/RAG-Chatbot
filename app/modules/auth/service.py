import logging
from datetime import datetime
from uuid import UUID

from app.core.config import Settings, get_settings
from app.core.exceptions import ConflictException, ForbiddenException, UnauthorizedException
from app.core.responses import ApiResponse
from app.modules.auth.models import RefreshToken, User
from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import (
    AuthUserResponse,
    CurrentUserResponse,
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    RefreshTokenRequest,
    RefreshTokenResponse,
    RegisterRequest,
    RegisterResponse,
)
from app.modules.auth.security import (
    create_access_token,
    create_refresh_token_pair,
    hash_password,
    hash_refresh_token,
    refresh_token_expires_at,
    seconds_until,
    utc_now,
    verify_password,
)

INVALID_LOGIN_MESSAGE = "Invalid email or password."
INVALID_REFRESH_TOKEN_MESSAGE = "Refresh token is invalid or expired."  # noqa: S105

_logger = logging.getLogger(__name__)


class AuthService:
    def __init__(
        self,
        auth_repository: AuthRepository,
        settings: Settings | None = None,
    ) -> None:
        self.auth_repository = auth_repository
        self.settings = settings or get_settings()

    async def register_async(self, request: RegisterRequest) -> ApiResponse[RegisterResponse]:
        email = _normalize_email(str(request.email))
        existing_user = await self.auth_repository.get_user_by_email(email)
        if existing_user is not None:
            raise ConflictException("A user with this email already exists.")

        user = User(
            email=email,
            full_name=request.full_name.strip(),
            password_hash=hash_password(request.password),
        )
        user = await self.auth_repository.create_user(user)

        return ApiResponse.success_response(
            message="User registered successfully.",
            data=RegisterResponse(
                userId=user.id,
                fullName=user.full_name,
                email=user.email,
            ),
        )

    async def login_async(self, request: LoginRequest) -> ApiResponse[LoginResponse]:
        user = await self.auth_repository.get_user_by_email(_normalize_email(str(request.email)))

        # Keep unknown-email and wrong-password failures indistinguishable.
        if user is None or not verify_password(request.password, user.password_hash):
            raise UnauthorizedException(INVALID_LOGIN_MESSAGE)

        if not user.is_active:
            raise ForbiddenException("User account is inactive.")

        logged_in_at = utc_now()
        user = await self.auth_repository.update_last_login(user, logged_in_at)
        refresh_token = await self._create_refresh_token_for_user(user)
        access_token = create_access_token(user_id=user.id, settings=self.settings)

        return ApiResponse.success_response(
            message="Login successful.",
            data=LoginResponse(
                accessToken=access_token,
                refreshToken=refresh_token[0],
                expiresIn=self.settings.jwt_access_token_expire_minutes * 60,
                user=_auth_user_response(user),
            ),
        )

    async def refresh_access_token_async(
        self,
        request: RefreshTokenRequest,
    ) -> ApiResponse[RefreshTokenResponse]:
        existing_token = await self._get_valid_refresh_token(request.refresh_token)
        new_token = await self._create_refresh_token_for_user_id(existing_token.user_id)

        await self.auth_repository.revoke_refresh_token(
            existing_token,
            utc_now(),
            new_token[1].id,
        )

        access_token = create_access_token(user_id=existing_token.user_id, settings=self.settings)

        return ApiResponse.success_response(
            message="Token refreshed successfully.",
            data=RefreshTokenResponse(
                accessToken=access_token,
                refreshToken=new_token[0],
                expiresIn=self.settings.jwt_access_token_expire_minutes * 60,
            ),
        )

    async def logout_async(self, request: LogoutRequest) -> ApiResponse[None]:
        token_hash = hash_refresh_token(request.refresh_token)
        refresh_token = await self.auth_repository.get_refresh_token_by_hash(token_hash)

        if refresh_token is not None and refresh_token.revoked_at is None:
            await self.auth_repository.revoke_refresh_token(refresh_token, utc_now())

        return ApiResponse.success_response(
            message="Logged out successfully.",
            data=None,
        )

    async def get_current_user_async(self, user: User) -> ApiResponse[CurrentUserResponse]:
        if not user.is_active:
            raise ForbiddenException("User account is inactive.")

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

    async def _get_valid_refresh_token(self, raw_refresh_token: str) -> RefreshToken:
        token_hash = hash_refresh_token(raw_refresh_token)
        refresh_token = await self.auth_repository.get_refresh_token_by_hash(token_hash)

        if refresh_token is None:
            raise UnauthorizedException(INVALID_REFRESH_TOKEN_MESSAGE)

        # Reuse detection: if the token was already revoked, this may indicate
        # token theft. Revoke the entire token family for this user.
        if refresh_token.revoked_at is not None:
            _logger.warning(
                "Refresh token reuse detected for user_id=%s — revoking all tokens.",
                refresh_token.user_id,
            )
            await self.auth_repository.revoke_all_user_refresh_tokens(
                refresh_token.user_id, utc_now()
            )
            raise UnauthorizedException(INVALID_REFRESH_TOKEN_MESSAGE)

        if _is_expired(refresh_token.expires_at):
            raise UnauthorizedException(INVALID_REFRESH_TOKEN_MESSAGE)

        return refresh_token

    async def _create_refresh_token_for_user(self, user: User) -> tuple[str, RefreshToken]:
        return await self._create_refresh_token_for_user_id(user.id)

    async def _create_refresh_token_for_user_id(self, user_id: UUID) -> tuple[str, RefreshToken]:
        raw_token, token_hash = create_refresh_token_pair(self.settings)
        refresh_token = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=refresh_token_expires_at(self.settings),
            created_at=utc_now(),
        )
        refresh_token = await self.auth_repository.create_refresh_token(refresh_token)
        return raw_token, refresh_token


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _is_expired(expires_at: datetime) -> bool:
    return seconds_until(expires_at) == 0


def _auth_user_response(user: User) -> AuthUserResponse:
    return AuthUserResponse(
        userId=user.id,
        fullName=user.full_name,
        email=user.email,
    )
