import os

os.environ["APP_ENV"] = "test"

from app.core.config import Settings


def auth_settings() -> Settings:
    return Settings(
        app_env="test",
        jwt_secret_key="test-secret-with-at-least-32-characters",  # noqa: S106
        jwt_access_token_expire_minutes=15,
        jwt_refresh_token_expire_days=30,
        refresh_token_bytes=32,
    )

