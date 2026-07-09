from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.database import get_db
from app.core.config import Settings, get_settings
from app.modules.documents.repository import DocumentRepository
from app.modules.documents.service import DocumentService
from app.modules.storage.dependencies import get_storage_service
from app.modules.storage.service import LocalStorageService
from app.modules.workspaces.dependencies import get_workspace_repository
from app.modules.workspaces.repository import WorkspaceRepository


def get_document_repository(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DocumentRepository:
    return DocumentRepository(db)


def get_document_service(
    document_repository: Annotated[DocumentRepository, Depends(get_document_repository)],
    workspace_repository: Annotated[WorkspaceRepository, Depends(get_workspace_repository)],
    storage_service: Annotated[LocalStorageService, Depends(get_storage_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DocumentService:
    return DocumentService(
        document_repository,
        workspace_repository,
        storage_service,
        settings,
    )
