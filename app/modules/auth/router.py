from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.responses import ApiResponse
from app.modules.auth.dependencies import get_auth_service, require_active_user
from app.modules.auth.models import User
from app.modules.auth.schemas import (
    CurrentUserResponse,
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    RefreshTokenRequest,
    RefreshTokenResponse,
    RegisterRequest,
    RegisterResponse,
)
from app.modules.auth.service import AuthService

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[RegisterResponse],
)
async def register(
    request: RegisterRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> ApiResponse[RegisterResponse]:
    return await service.register_async(request)


@router.post("/login", response_model=ApiResponse[LoginResponse])
async def login(
    request: LoginRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> ApiResponse[LoginResponse]:
    return await service.login_async(request)


@router.post("/refresh", response_model=ApiResponse[RefreshTokenResponse])
async def refresh_token(
    request: RefreshTokenRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> ApiResponse[RefreshTokenResponse]:
    return await service.refresh_access_token_async(request)


@router.post("/logout", response_model=ApiResponse[None])
async def logout(
    request: LogoutRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> ApiResponse[None]:
    return await service.logout_async(request)


@router.get("/me", response_model=ApiResponse[CurrentUserResponse])
async def get_current_user_profile(
    current_user: Annotated[User, Depends(require_active_user)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> ApiResponse[CurrentUserResponse]:
    return await service.get_current_user_async(current_user)

