import pytest
from pydantic import ValidationError

from app.core.config import EMBEDDING_VECTOR_DIMENSION, Settings


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


def test_storage_defaults_are_local_private() -> None:
    settings = Settings()

    assert str(settings.storage_local_root) == "local_storage/private"
    assert settings.storage_max_upload_bytes == 10 * 1024 * 1024
    assert ".pdf" in settings.storage_allowed_extensions
    assert "application/pdf" in settings.storage_allowed_mime_types


def test_storage_rejects_invalid_limits() -> None:
    with pytest.raises(ValidationError, match="STORAGE_MAX_UPLOAD_BYTES"):
        Settings(storage_max_upload_bytes=0)


def test_storage_rejects_empty_allowlists() -> None:
    with pytest.raises(ValidationError, match="STORAGE_ALLOWED_EXTENSIONS"):
        Settings(storage_allowed_extensions=[])

    with pytest.raises(ValidationError, match="STORAGE_ALLOWED_MIME_TYPES"):
        Settings(storage_allowed_mime_types=[])


def test_embedding_defaults_use_ollama() -> None:
    settings = Settings()

    assert settings.embedding_model == "nomic-embed-text"
    assert EMBEDDING_VECTOR_DIMENSION == 768
    assert settings.embedding_batch_size == 16
    assert settings.ollama_base_url == "http://localhost:11434"
    assert settings.ollama_timeout_seconds == 30.0


def test_embedding_rejects_invalid_settings() -> None:
    with pytest.raises(ValidationError, match="EMBEDDING_MODEL"):
        Settings(embedding_model="")

    with pytest.raises(ValidationError, match="EMBEDDING_BATCH_SIZE"):
        Settings(embedding_batch_size=0)

    with pytest.raises(ValidationError, match="OLLAMA_BASE_URL"):
        Settings(ollama_base_url="localhost:11434")

    with pytest.raises(ValidationError, match="OLLAMA_TIMEOUT_SECONDS"):
        Settings(ollama_timeout_seconds=0)
