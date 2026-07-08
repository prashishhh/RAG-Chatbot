import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_local_environment_allows_placeholder_jwt_secret() -> None:
    settings = Settings(app_env="local", jwt_secret_key="change-this-in-local-env")  # noqa: S106

    assert settings.is_local is True


def test_production_rejects_placeholder_jwt_secret() -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY must be changed"):
        Settings(app_env="production", jwt_secret_key="change-this-in-local-env")  # noqa: S106


def test_production_rejects_short_jwt_secret() -> None:
    with pytest.raises(ValidationError, match="at least 32 characters"):
        Settings(app_env="production", jwt_secret_key="too-short")  # noqa: S106


def test_production_accepts_strong_jwt_secret() -> None:
    settings = Settings(
        app_env="production",
        jwt_secret_key="a-production-secret-with-at-least-32-chars",  # noqa: S106
    )

    assert settings.is_local is False
