from pathlib import Path

import pytest

from app.core.exceptions import ConflictException, NotFoundException, ValidationException
from app.modules.storage.service import LocalStorageService


def make_service(tmp_path: Path, max_upload_bytes: int = 20) -> LocalStorageService:
    return LocalStorageService(tmp_path / "private", max_upload_bytes)


def test_save_read_exists_and_delete_bytes(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    object_key = "workspaces/1/documents/2/original/file.txt"

    saved_key = service.save_bytes(object_key, b"hello")

    assert saved_key == object_key
    assert service.exists(object_key) is True
    assert service.read_bytes(object_key) == b"hello"

    service.delete(object_key)

    assert service.exists(object_key) is False


def test_save_rejects_empty_or_oversized_content(tmp_path: Path) -> None:
    service = make_service(tmp_path, max_upload_bytes=3)

    with pytest.raises(ValidationException):
        service.save_bytes("workspaces/1/documents/2/original/empty.txt", b"")

    with pytest.raises(ValidationException):
        service.save_bytes("workspaces/1/documents/2/original/big.txt", b"toolong")


def test_save_rejects_duplicate_object_key(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    object_key = "workspaces/1/documents/2/original/file.txt"

    service.save_bytes(object_key, b"hello")

    with pytest.raises(ConflictException):
        service.save_bytes(object_key, b"again")


def test_read_missing_object_raises_not_found(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    with pytest.raises(NotFoundException):
        service.read_bytes("workspaces/1/documents/2/original/missing.txt")


def test_service_blocks_path_traversal(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    with pytest.raises(ValidationException):
        service.save_bytes("../outside.txt", b"hello")

    assert not (tmp_path / "outside.txt").exists()
