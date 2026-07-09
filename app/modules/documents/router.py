from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile, status

from app.core.config import Settings, get_settings
from app.core.responses import ApiResponse
from app.modules.auth.dependencies import require_active_user
from app.modules.auth.models import User
from app.modules.documents.dependencies import get_document_service
from app.modules.documents.schemas import (
    DeleteDocumentResponse,
    DocumentListItemResponse,
    DocumentResponse,
    EmbedDocumentResponse,
    IngestDocumentResponse,
)
from app.modules.documents.service import DocumentService

router = APIRouter(prefix="/workspaces/{workspace_id}/documents", tags=["Documents"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[DocumentResponse],
)
async def upload_document(
    workspace_id: UUID,
    file: Annotated[UploadFile, File()],
    current_user: Annotated[User, Depends(require_active_user)],
    service: Annotated[DocumentService, Depends(get_document_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ApiResponse[DocumentResponse]:
    content = await _read_upload(file, settings.storage_max_upload_bytes)
    return await service.upload_async(
        workspace_id,
        file.filename or "file",
        file.content_type,
        content,
        current_user,
    )


@router.get("", response_model=ApiResponse[list[DocumentListItemResponse]])
async def list_documents(
    workspace_id: UUID,
    current_user: Annotated[User, Depends(require_active_user)],
    service: Annotated[DocumentService, Depends(get_document_service)],
) -> ApiResponse[list[DocumentListItemResponse]]:
    return await service.list_async(workspace_id, current_user)


@router.get("/{document_id}", response_model=ApiResponse[DocumentResponse])
async def get_document(
    workspace_id: UUID,
    document_id: UUID,
    current_user: Annotated[User, Depends(require_active_user)],
    service: Annotated[DocumentService, Depends(get_document_service)],
) -> ApiResponse[DocumentResponse]:
    return await service.get_by_id_async(workspace_id, document_id, current_user)


@router.delete("/{document_id}", response_model=ApiResponse[DeleteDocumentResponse])
async def delete_document(
    workspace_id: UUID,
    document_id: UUID,
    current_user: Annotated[User, Depends(require_active_user)],
    service: Annotated[DocumentService, Depends(get_document_service)],
) -> ApiResponse[DeleteDocumentResponse]:
    return await service.delete_async(workspace_id, document_id, current_user)


@router.post("/{document_id}/ingest", response_model=ApiResponse[IngestDocumentResponse])
async def ingest_document(
    workspace_id: UUID,
    document_id: UUID,
    current_user: Annotated[User, Depends(require_active_user)],
    service: Annotated[DocumentService, Depends(get_document_service)],
) -> ApiResponse[IngestDocumentResponse]:
    return await service.ingest_async(workspace_id, document_id, current_user)


@router.post("/{document_id}/embed", response_model=ApiResponse[EmbedDocumentResponse])
async def embed_document(
    workspace_id: UUID,
    document_id: UUID,
    current_user: Annotated[User, Depends(require_active_user)],
    service: Annotated[DocumentService, Depends(get_document_service)],
) -> ApiResponse[EmbedDocumentResponse]:
    return await service.embed_async(workspace_id, document_id, current_user)


async def _read_upload(file: UploadFile, max_upload_bytes: int) -> bytes:
    return await file.read(max_upload_bytes + 1)
