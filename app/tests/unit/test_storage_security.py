from pathlib import Path
from uuid import uuid4

import pytest

from app.core.exceptions import ValidationException
from app.modules.storage.security import (
    build_document_object_key,
    resolve_local_storage_path,
    sanitize_filename,
    validate_file_extension,
    validate_file_size,
    validate_mime_type,
    validate_object_key,
)


def test_sanitize_filename_removes_paths_and_unsafe_characters() -> None:
    assert sanitize_filename("../Invoice Final!!.PDF") == "Invoice-Final.pdf"
    assert sanitize_filename(r"..\..\secret.txt") == "secret.txt"
    assert sanitize_filename("...") == "file"


def test_validate_file_extension_allows_only_configured_extensions() -> None:
    assert validate_file_extension("report.PDF", [".pdf"]) == ".pdf"

    with pytest.raises(ValidationException):
        validate_file_extension("script.exe", [".pdf", ".txt"])


def test_validate_mime_type_allows_only_configured_types() -> None:
    assert validate_mime_type("Application/PDF; charset=binary", ["application/pdf"]) == (
        "application/pdf"
    )

    with pytest.raises(ValidationException):
        validate_mime_type("application/x-msdownload", ["application/pdf"])


def test_validate_file_size_blocks_empty_and_oversized_files() -> None:
    validate_file_size(10, 10)

    with pytest.raises(ValidationException):
        validate_file_size(0, 10)

    with pytest.raises(ValidationException):
        validate_file_size(11, 10)


def test_validate_object_key_blocks_path_traversal() -> None:
    assert validate_object_key("workspaces/123/documents/456/original/file.pdf")

    unsafe_keys = ["", "/absolute/file.pdf", "../file.pdf", "safe/../file.pdf", r"safe\file.pdf"]
    for object_key in unsafe_keys:
        with pytest.raises(ValidationException):
            validate_object_key(object_key)


def test_build_document_object_key_is_workspace_scoped_and_s3_compatible() -> None:
    workspace_id = uuid4()
    document_id = uuid4()

    object_key = build_document_object_key(workspace_id, document_id, "../My File.PDF")

    assert object_key == (
        f"workspaces/{workspace_id}/documents/{document_id}/original/My-File.pdf"
    )


def test_resolve_local_storage_path_stays_under_storage_root() -> None:
    root = Path("local_storage/private")

    resolved = resolve_local_storage_path(root, "workspaces/1/documents/2/original/file.pdf")

    assert resolved == (root / "workspaces/1/documents/2/original/file.pdf").resolve()

    with pytest.raises(ValidationException):
        resolve_local_storage_path(root, "../outside.pdf")
