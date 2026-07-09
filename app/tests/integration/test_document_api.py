from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.exceptions import ForbiddenException, NotFoundException, ValidationException
from app.core.responses import ApiResponse
from app.main import app
from app.modules.auth.dependencies import get_auth_repository
from app.modules.auth.models import User
from app.modules.auth.security import create_access_token
from app.modules.documents.dependencies import get_document_service
from app.modules.documents.models import DocumentStatus
from app.modules.documents.schemas import (
    DeleteDocumentResponse,
    DocumentListItemResponse,
    DocumentResponse,
    EmbedDocumentResponse,
    IngestDocumentResponse,
)
from app.tests.conftest import auth_settings


class FakeAuthRepository:
    def __init__(self, user: User | None) -> None:
        self.user = user

    async def get_user_by_id(self, user_id):
        if self.user is not None and self.user.id == user_id:
            return self.user
        return None


class FakeDocumentService:
    def __init__(self) -> None:
        self.workspace_id = uuid4()
        self.document_id = uuid4()

    async def upload_async(self, workspace_id, filename, content_type, content, current_user):
        if filename == "forbidden.pdf":
            raise ForbiddenException("You do not have permission to upload documents.")
        if filename == "bad.exe":
            raise ValidationException("File extension is not allowed.")
        return ApiResponse.success_response(
            message="Document uploaded successfully.",
            data=_document_response(
                self.document_id,
                workspace_id,
                filename,
                content_type,
                len(content),
            ),
        )

    async def list_async(self, workspace_id, current_user):
        return ApiResponse.success_response(
            message="Documents retrieved successfully.",
            data=[
                DocumentListItemResponse(
                    documentId=self.document_id,
                    originalFilename="Report.pdf",
                    contentType="application/pdf",
                    sizeBytes=123,
                    status=DocumentStatus.UPLOADED,
                    createdAt=datetime(2026, 7, 8, tzinfo=UTC),
                )
            ],
        )

    async def get_by_id_async(self, workspace_id, document_id, current_user):
        if document_id != self.document_id:
            raise NotFoundException("Document not found.")
        return ApiResponse.success_response(
            message="Document retrieved successfully.",
            data=_document_response(
                document_id,
                workspace_id,
                "Report.pdf",
                "application/pdf",
                123,
            ),
        )

    async def delete_async(self, workspace_id, document_id, current_user):
        if document_id != self.document_id:
            raise NotFoundException("Document not found.")
        return ApiResponse.success_response(
            message="Document deleted successfully.",
            data=DeleteDocumentResponse(
                documentId=document_id,
                status=DocumentStatus.DELETED,
                deletedAt=datetime(2026, 7, 8, tzinfo=UTC),
            ),
        )

    async def ingest_async(self, workspace_id, document_id, current_user):
        if document_id != self.document_id:
            raise NotFoundException("Document not found.")
        return ApiResponse.success_response(
            message="Document ingested successfully.",
            data=IngestDocumentResponse(
                documentId=document_id,
                status=DocumentStatus.READY,
                chunkCount=2,
                textCharCount=250,
                ingestionStartedAt=datetime(2026, 7, 8, tzinfo=UTC),
                ingestionCompletedAt=datetime(2026, 7, 8, tzinfo=UTC),
            ),
        )

    async def embed_async(self, workspace_id, document_id, current_user):
        if document_id != self.document_id:
            raise NotFoundException("Document not found.")
        return ApiResponse.success_response(
            message="Document embedded successfully.",
            data=EmbedDocumentResponse(
                documentId=document_id,
                status=DocumentStatus.READY,
                embeddedChunkCount=2,
            ),
        )


def _document_response(
    document_id,
    workspace_id,
    filename: str,
    content_type: str | None,
    size_bytes: int,
) -> DocumentResponse:
    return DocumentResponse(
        documentId=document_id,
        workspaceId=workspace_id,
        originalFilename=filename,
        contentType=content_type or "application/octet-stream",
        sizeBytes=size_bytes,
        status=DocumentStatus.UPLOADED,
        createdAt=datetime(2026, 7, 8, tzinfo=UTC),
        updatedAt=datetime(2026, 7, 8, tzinfo=UTC),
    )


def make_user(*, is_active: bool = True) -> User:
    return User(
        id=uuid4(),
        email="ram@example.com",
        full_name="Ram Sharma",
        password_hash="$argon2id$hash",  # noqa: S106
        is_active=is_active,
        is_verified=False,
    )


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def authenticated_client(user: User | None = None) -> TestClient:
    current_user = user or make_user()
    token = create_access_token(user_id=current_user.id, settings=auth_settings())
    app.dependency_overrides[get_auth_repository] = lambda: FakeAuthRepository(current_user)
    app.dependency_overrides[get_settings] = auth_settings
    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


def limited_upload_settings() -> Settings:
    return Settings(
        app_env="test",
        jwt_secret_key="test-secret-with-at-least-32-characters",  # noqa: S106
        storage_max_upload_bytes=3,
    )


def test_upload_document_success_returns_201_standard_response() -> None:
    service = FakeDocumentService()
    client = authenticated_client()
    app.dependency_overrides[get_document_service] = lambda: service

    response = client.post(
        f"/api/v1/workspaces/{service.workspace_id}/documents",
        files={"file": ("Report.pdf", b"pdf", "application/pdf")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["message"] == "Document uploaded successfully."
    assert body["data"]["originalFilename"] == "Report.pdf"
    assert "objectKey" not in body["data"]
    assert "localPath" not in body["data"]


def test_document_routes_require_authentication() -> None:
    app.dependency_overrides[get_document_service] = FakeDocumentService
    client = TestClient(app)

    response = client.get(f"/api/v1/workspaces/{uuid4()}/documents")

    assert response.status_code == 401


def test_ingest_document_requires_authentication() -> None:
    service = FakeDocumentService()
    app.dependency_overrides[get_document_service] = lambda: service
    client = TestClient(app)

    response = client.post(
        f"/api/v1/workspaces/{service.workspace_id}/documents/{service.document_id}/ingest"
    )

    assert response.status_code == 401


def test_embed_document_requires_authentication() -> None:
    service = FakeDocumentService()
    app.dependency_overrides[get_document_service] = lambda: service
    client = TestClient(app)

    response = client.post(
        f"/api/v1/workspaces/{service.workspace_id}/documents/{service.document_id}/embed"
    )

    assert response.status_code == 401


def test_document_routes_reject_inactive_user() -> None:
    service = FakeDocumentService()
    client = authenticated_client(make_user(is_active=False))
    app.dependency_overrides[get_document_service] = lambda: service

    response = client.get(f"/api/v1/workspaces/{service.workspace_id}/documents")

    assert response.status_code == 403
    assert response.json()["message"] == "User account is inactive."


def test_upload_document_validation_error_is_standard_response() -> None:
    service = FakeDocumentService()
    client = authenticated_client()
    app.dependency_overrides[get_document_service] = lambda: service

    response = client.post(
        f"/api/v1/workspaces/{service.workspace_id}/documents",
        files={"file": ("bad.exe", b"bad", "application/x-msdownload")},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert "traceback" not in str(body).lower()


def test_upload_document_reads_only_limit_plus_one_byte() -> None:
    service = FakeDocumentService()
    client = authenticated_client()
    app.dependency_overrides[get_settings] = limited_upload_settings
    app.dependency_overrides[get_document_service] = lambda: service

    response = client.post(
        f"/api/v1/workspaces/{service.workspace_id}/documents",
        files={"file": ("Report.pdf", b"0123456789", "application/pdf")},
    )

    assert response.status_code == 201
    assert response.json()["data"]["sizeBytes"] == 4


def test_list_documents_success() -> None:
    service = FakeDocumentService()
    client = authenticated_client()
    app.dependency_overrides[get_document_service] = lambda: service

    response = client.get(f"/api/v1/workspaces/{service.workspace_id}/documents")

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Documents retrieved successfully."
    assert body["data"][0]["originalFilename"] == "Report.pdf"


def test_get_document_hides_missing_document() -> None:
    service = FakeDocumentService()
    client = authenticated_client()
    app.dependency_overrides[get_document_service] = lambda: service

    response = client.get(f"/api/v1/workspaces/{service.workspace_id}/documents/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["message"] == "Document not found."


def test_get_document_success() -> None:
    service = FakeDocumentService()
    client = authenticated_client()
    app.dependency_overrides[get_document_service] = lambda: service

    response = client.get(
        f"/api/v1/workspaces/{service.workspace_id}/documents/{service.document_id}"
    )

    assert response.status_code == 200
    assert response.json()["data"]["documentId"] == str(service.document_id)


def test_delete_document_success() -> None:
    service = FakeDocumentService()
    client = authenticated_client()
    app.dependency_overrides[get_document_service] = lambda: service

    response = client.delete(
        f"/api/v1/workspaces/{service.workspace_id}/documents/{service.document_id}"
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Document deleted successfully."
    assert response.json()["data"]["status"] == "Deleted"


def test_ingest_document_success() -> None:
    service = FakeDocumentService()
    client = authenticated_client()
    app.dependency_overrides[get_document_service] = lambda: service

    response = client.post(
        f"/api/v1/workspaces/{service.workspace_id}/documents/{service.document_id}/ingest"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Document ingested successfully."
    assert body["data"]["documentId"] == str(service.document_id)
    assert body["data"]["status"] == "Ready"
    assert body["data"]["chunkCount"] == 2
    assert body["data"]["textCharCount"] == 250
    assert "objectKey" not in body["data"]
    assert "localPath" not in body["data"]
    assert "content" not in body["data"]


def test_embed_document_success_hides_vectors_and_content() -> None:
    service = FakeDocumentService()
    client = authenticated_client()
    app.dependency_overrides[get_document_service] = lambda: service

    response = client.post(
        f"/api/v1/workspaces/{service.workspace_id}/documents/{service.document_id}/embed"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Document embedded successfully."
    assert body["data"]["documentId"] == str(service.document_id)
    assert body["data"]["status"] == "Ready"
    assert body["data"]["embeddedChunkCount"] == 2
    assert "embedding" not in body["data"]
    assert "vector" not in body["data"]
    assert "content" not in body["data"]


def test_ingest_document_hides_missing_document() -> None:
    service = FakeDocumentService()
    client = authenticated_client()
    app.dependency_overrides[get_document_service] = lambda: service

    response = client.post(f"/api/v1/workspaces/{service.workspace_id}/documents/{uuid4()}/ingest")

    assert response.status_code == 404
    assert response.json()["message"] == "Document not found."


def test_embed_document_hides_missing_document() -> None:
    service = FakeDocumentService()
    client = authenticated_client()
    app.dependency_overrides[get_document_service] = lambda: service

    response = client.post(f"/api/v1/workspaces/{service.workspace_id}/documents/{uuid4()}/embed")

    assert response.status_code == 404
    assert response.json()["message"] == "Document not found."
