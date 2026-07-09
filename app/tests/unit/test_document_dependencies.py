from pathlib import Path

from app.core.config import Settings
from app.modules.documents.dependencies import get_document_repository, get_document_service
from app.modules.documents.repository import DocumentRepository
from app.modules.documents.service import DocumentService
from app.modules.storage.service import LocalStorageService


def test_get_document_repository_returns_repository() -> None:
    assert isinstance(get_document_repository(object()), DocumentRepository)  # type: ignore[arg-type]


def test_get_document_service_returns_service() -> None:
    service = get_document_service(
        DocumentRepository(object()),  # type: ignore[arg-type]
        object(),  # type: ignore[arg-type]
        LocalStorageService(Path("local_storage/private"), 10),
        Settings(app_env="test"),
    )

    assert isinstance(service, DocumentService)
