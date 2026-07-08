from pathlib import Path

from app.core.config import Settings
from app.modules.storage.dependencies import get_storage_service
from app.modules.storage.service import LocalStorageService


def test_get_storage_service_uses_storage_settings() -> None:
    settings = Settings(
        storage_local_root=Path("local_storage/test-private"),
        storage_max_upload_bytes=123,
    )

    service = get_storage_service(settings)

    assert isinstance(service, LocalStorageService)
    assert service.storage_root == Path("local_storage/test-private")
    assert service.max_upload_bytes == 123
