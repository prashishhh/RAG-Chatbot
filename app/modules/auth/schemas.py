import re
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

_PASSWORD_RULES = [
    (r"[A-Z]", "at least one uppercase letter"),
    (r"[a-z]", "at least one lowercase letter"),
    (r"[0-9]", "at least one digit"),
    (r"[^A-Za-z0-9]", "at least one special character"),
]


class RegisterRequest(BaseModel):
    full_name: str = Field(alias="fullName", min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(alias="confirmPassword", min_length=8, max_length=128)

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("password")
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        missing = [desc for pattern, desc in _PASSWORD_RULES if not re.search(pattern, v)]
        if missing:
            raise ValueError(
                "Password must contain " + ", ".join(missing) + "."
            )
        return v

    @model_validator(mode="after")
    def validate_passwords_match(self) -> "RegisterRequest":
        if self.password != self.confirm_password:
            raise ValueError("Password and confirmation password must match.")
        return self


class RegisterResponse(BaseModel):
    user_id: UUID = Field(alias="userId")
    full_name: str = Field(alias="fullName")
    email: EmailStr

    model_config = ConfigDict(populate_by_name=True)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class AuthUserResponse(BaseModel):
    user_id: UUID = Field(alias="userId")
    full_name: str = Field(alias="fullName")
    email: EmailStr

    model_config = ConfigDict(populate_by_name=True)


class LoginResponse(BaseModel):
    access_token: str = Field(alias="accessToken")
    # Raw refresh token is returned only in auth responses, never DB metadata.
    refresh_token: str = Field(alias="refreshToken")
    token_type: str = Field(default="Bearer", alias="tokenType")
    expires_in: int = Field(alias="expiresIn", ge=1)
    user: AuthUserResponse

    model_config = ConfigDict(populate_by_name=True)


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(alias="refreshToken", min_length=1)

    model_config = ConfigDict(populate_by_name=True)


class RefreshTokenResponse(BaseModel):
    access_token: str = Field(alias="accessToken")
    refresh_token: str = Field(alias="refreshToken")
    token_type: str = Field(default="Bearer", alias="tokenType")
    expires_in: int = Field(alias="expiresIn", ge=1)

    model_config = ConfigDict(populate_by_name=True)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(alias="refreshToken", min_length=1)

    model_config = ConfigDict(populate_by_name=True)


class CurrentUserResponse(BaseModel):
    user_id: UUID = Field(alias="userId")
    full_name: str = Field(alias="fullName")
    email: EmailStr
    is_active: bool = Field(alias="isActive")
    is_verified: bool = Field(alias="isVerified")

    model_config = ConfigDict(populate_by_name=True)


class AccessTokenPayloadInternal(BaseModel):
    sub: UUID
    exp: int
    iat: int
    token_type: str = Field(alias="type")

    model_config = ConfigDict(populate_by_name=True)
