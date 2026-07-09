from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.database import get_db
from app.core.config import Settings, get_settings
from app.modules.embeddings.provider import OllamaEmbeddingProvider
from app.modules.retrieval.repository import RetrievalRepository
from app.modules.retrieval.service import RetrievalService
from app.modules.workspaces.dependencies import get_workspace_repository
from app.modules.workspaces.repository import WorkspaceRepository


def get_retrieval_repository(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RetrievalRepository:
    return RetrievalRepository(db)


def get_embedding_provider(
    settings: Annotated[Settings, Depends(get_settings)],
) -> OllamaEmbeddingProvider:
    return OllamaEmbeddingProvider(settings)


def get_retrieval_service(
    retrieval_repository: Annotated[RetrievalRepository, Depends(get_retrieval_repository)],
    workspace_repository: Annotated[WorkspaceRepository, Depends(get_workspace_repository)],
    embedding_provider: Annotated[OllamaEmbeddingProvider, Depends(get_embedding_provider)],
) -> RetrievalService:
    return RetrievalService(retrieval_repository, workspace_repository, embedding_provider)
