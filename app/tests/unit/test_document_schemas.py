from datetime import UTC, datetime
from uuid import uuid4

from app.modules.documents.models import DocumentStatus
from app.modules.documents.schemas import (
    DeleteDocumentResponse,
    DocumentListItemResponse,
    DocumentResponse,
    IngestDocumentResponse,
)


def test_document_response_exposes_no_storage_path_or_object_key() -> None:
    response = DocumentResponse(
        documentId=uuid4(),
        workspaceId=uuid4(),
        originalFilename="Report.pdf",
        contentType="application/pdf",
        sizeBytes=123,
        status=DocumentStatus.UPLOADED,
        createdAt=datetime.now(UTC),
        updatedAt=datetime.now(UTC),
    )

    payload = response.model_dump(by_alias=True)

    assert set(payload) == {
        "documentId",
        "workspaceId",
        "originalFilename",
        "contentType",
        "sizeBytes",
        "status",
        "createdAt",
        "updatedAt",
    }
    assert "objectKey" not in payload
    assert "localPath" not in payload


def test_document_list_item_omits_workspace_and_storage_metadata() -> None:
    response = DocumentListItemResponse(
        documentId=uuid4(),
        originalFilename="Report.pdf",
        contentType="application/pdf",
        sizeBytes=123,
        status=DocumentStatus.READY,
        createdAt=datetime.now(UTC),
    )

    payload = response.model_dump(by_alias=True)

    assert set(payload) == {
        "documentId",
        "originalFilename",
        "contentType",
        "sizeBytes",
        "status",
        "createdAt",
    }


def test_delete_document_response_is_minimal() -> None:
    response = DeleteDocumentResponse(
        documentId=uuid4(),
        status=DocumentStatus.DELETED,
        deletedAt=datetime.now(UTC),
    )

    assert set(response.model_dump(by_alias=True)) == {"documentId", "status", "deletedAt"}


def test_ingest_document_response_exposes_no_chunks_or_storage_metadata() -> None:
    response = IngestDocumentResponse(
        documentId=uuid4(),
        status=DocumentStatus.READY,
        chunkCount=3,
        textCharCount=500,
        ingestionStartedAt=datetime.now(UTC),
        ingestionCompletedAt=datetime.now(UTC),
    )

    payload = response.model_dump(by_alias=True)

    assert set(payload) == {
        "documentId",
        "status",
        "chunkCount",
        "textCharCount",
        "ingestionStartedAt",
        "ingestionCompletedAt",
    }
    assert "content" not in payload
    assert "chunks" not in payload
    assert "objectKey" not in payload
    assert "localPath" not in payload
