from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.documents.models import DocumentStatus


class DocumentResponse(BaseModel):
    document_id: UUID = Field(alias="documentId")
    workspace_id: UUID = Field(alias="workspaceId")
    original_filename: str = Field(alias="originalFilename")
    content_type: str = Field(alias="contentType")
    size_bytes: int = Field(alias="sizeBytes")
    status: DocumentStatus
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True)


class DocumentListItemResponse(BaseModel):
    document_id: UUID = Field(alias="documentId")
    original_filename: str = Field(alias="originalFilename")
    content_type: str = Field(alias="contentType")
    size_bytes: int = Field(alias="sizeBytes")
    status: DocumentStatus
    created_at: datetime = Field(alias="createdAt")

    model_config = ConfigDict(populate_by_name=True)


class DeleteDocumentResponse(BaseModel):
    document_id: UUID = Field(alias="documentId")
    status: DocumentStatus
    deleted_at: datetime = Field(alias="deletedAt")

    model_config = ConfigDict(populate_by_name=True)


class IngestDocumentResponse(BaseModel):
    document_id: UUID = Field(alias="documentId")
    status: DocumentStatus
    chunk_count: int = Field(alias="chunkCount", ge=0)
    text_char_count: int = Field(alias="textCharCount", ge=0)
    ingestion_started_at: datetime | None = Field(alias="ingestionStartedAt")
    ingestion_completed_at: datetime | None = Field(alias="ingestionCompletedAt")

    model_config = ConfigDict(populate_by_name=True)
