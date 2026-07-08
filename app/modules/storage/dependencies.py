from typing import Annotated

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.modules.storage.service import LocalStorageService


def get_storage_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> LocalStorageService:
    return LocalStorageService(
        settings.storage_local_root,
        settings.storage_max_upload_bytes,
    )
