import re
from pathlib import Path, PurePosixPath
from uuid import UUID

from app.core.exceptions import ValidationException

MAX_SAFE_FILENAME_LENGTH = 180
_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(filename: str) -> str:
    raw_name = PurePosixPath(filename.replace("\\", "/")).name.strip()
    path_name = PurePosixPath(raw_name)
    stem = _UNSAFE_FILENAME_CHARS.sub("-", path_name.stem).strip(".-_")
    suffix = _UNSAFE_FILENAME_CHARS.sub("", path_name.suffix.lower())

    if not stem:
        stem = "file"

    max_stem_length = max(1, MAX_SAFE_FILENAME_LENGTH - len(suffix))
    return f"{stem[:max_stem_length]}{suffix}"


def validate_file_extension(filename: str, allowed_extensions: list[str]) -> str:
    extension = PurePosixPath(filename).suffix.lower()
    normalized_allowed = {
        value.lower() if value.startswith(".") else f".{value.lower()}"
        for value in allowed_extensions
    }
    if extension not in normalized_allowed:
        raise ValidationException("File extension is not allowed.")
    return extension


def validate_mime_type(content_type: str | None, allowed_mime_types: list[str]) -> str:
    mime_type = (content_type or "").split(";", 1)[0].strip().lower()
    normalized_allowed = {value.lower() for value in allowed_mime_types}
    if not mime_type or mime_type not in normalized_allowed:
        raise ValidationException("File type is not allowed.")
    return mime_type


def validate_file_size(size_bytes: int, max_upload_bytes: int) -> None:
    if size_bytes <= 0:
        raise ValidationException("File is empty.")
    if size_bytes > max_upload_bytes:
        raise ValidationException("File is too large.")


def validate_object_key(object_key: str) -> str:
    key = object_key.strip()
    path = PurePosixPath(key)
    if not key or path.is_absolute() or "\\" in key:
        raise ValidationException("Invalid storage object key.")
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ValidationException("Invalid storage object key.")
    return key


def build_document_object_key(workspace_id: UUID, document_id: UUID, filename: str) -> str:
    safe_filename = sanitize_filename(filename)
    return validate_object_key(
        f"workspaces/{workspace_id}/documents/{document_id}/original/{safe_filename}"
    )


def resolve_local_storage_path(storage_root: Path, object_key: str) -> Path:
    key = validate_object_key(object_key)
    root = storage_root.resolve()
    target = (root / key).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValidationException("Invalid storage object key.") from exc
    return target
