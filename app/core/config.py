from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# This exact placeholder is allowed only for local/test and rejected elsewhere.
LOCAL_JWT_SECRET_PLACEHOLDER = "change-this-in-local-env"  # noqa: S105
MIN_NON_LOCAL_JWT_SECRET_LENGTH = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "KnowBase AI"
    app_env: str = "local"
    app_debug: bool = False
    api_v1_prefix: str = "/api/v1"
    backend_cors_origins: list[str] = Field(default_factory=list)

    database_url: SecretStr = SecretStr(
        "postgresql+asyncpg://knowbase:knowbase@localhost:5432/knowbase"
    )
    jwt_secret_key: SecretStr = SecretStr("change-this-in-local-env")
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 30
    refresh_token_bytes: int = 32
    log_level: str = "INFO"
    storage_provider: str = "local"
    storage_local_root: Path = Path("local_storage/private")
    storage_max_upload_bytes: int = 10 * 1024 * 1024
    storage_allowed_extensions: list[str] = Field(default_factory=lambda: [".pdf", ".txt", ".md"])
    storage_allowed_mime_types: list[str] = Field(
        default_factory=lambda: ["application/pdf", "text/plain", "text/markdown"]
    )

    @property
    def is_local(self) -> bool:
        return self.app_env.lower() in {"local", "development", "dev", "test"}

    @model_validator(mode="after")
    def validate_security_settings(self) -> "Settings":
        jwt_secret = self.jwt_secret_key.get_secret_value()

        if not self.is_local and jwt_secret == LOCAL_JWT_SECRET_PLACEHOLDER:
            raise ValueError("JWT_SECRET_KEY must be changed outside local/test environments.")

        if not self.is_local and len(jwt_secret) < MIN_NON_LOCAL_JWT_SECRET_LENGTH:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters outside local/test.")

        if self.storage_provider != "local":
            raise ValueError("Only local storage provider is supported right now.")

        if not str(self.storage_local_root).strip():
            raise ValueError("STORAGE_LOCAL_ROOT must not be empty.")

        if self.storage_max_upload_bytes <= 0:
            raise ValueError("STORAGE_MAX_UPLOAD_BYTES must be greater than 0.")

        if not self.storage_allowed_extensions:
            raise ValueError("STORAGE_ALLOWED_EXTENSIONS must not be empty.")

        if not self.storage_allowed_mime_types:
            raise ValueError("STORAGE_ALLOWED_MIME_TYPES must not be empty.")

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
