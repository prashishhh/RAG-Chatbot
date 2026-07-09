from pathlib import Path

from app.core.exceptions import ConflictException, NotFoundException
from app.modules.storage.security import resolve_local_storage_path, validate_file_size


class LocalStorageService:
    def __init__(self, storage_root: Path, max_upload_bytes: int) -> None:
        self.storage_root = storage_root
        self.max_upload_bytes = max_upload_bytes

    def save_bytes(self, object_key: str, content: bytes) -> str:
        validate_file_size(len(content), self.max_upload_bytes)
        path = self._path_for_key(object_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("xb") as file:
                file.write(content)
        except FileExistsError as exc:
            raise ConflictException("Storage object already exists.") from exc
        return object_key

    def read_bytes(self, object_key: str) -> bytes:
        path = self._path_for_key(object_key)
        try:
            return path.read_bytes()
        except FileNotFoundError as exc:
            raise NotFoundException("Storage object not found.") from exc

    def delete(self, object_key: str) -> None:
        path = self._path_for_key(object_key)
        try:
            path.unlink()
        except FileNotFoundError:
            return

    def _path_for_key(self, object_key: str) -> Path:
        return resolve_local_storage_path(self.storage_root, object_key)
