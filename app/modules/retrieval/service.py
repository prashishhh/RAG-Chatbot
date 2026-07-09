from uuid import UUID

from app.core.exceptions import ExternalProviderException, ForbiddenException, NotFoundException
from app.core.responses import ApiResponse
from app.modules.auth.models import User
from app.modules.embeddings.provider import OllamaEmbeddingProvider
from app.modules.retrieval.repository import RetrievalRepository, RetrievalSearchRow
from app.modules.retrieval.schemas import (
    RetrievalSearchRequest,
    RetrievalSearchResponse,
    RetrievalSearchResult,
)
from app.modules.workspaces.repository import WorkspaceRepository

WORKSPACE_NOT_FOUND_MESSAGE = "Workspace not found."


class RetrievalService:
    def __init__(
        self,
        retrieval_repository: RetrievalRepository,
        workspace_repository: WorkspaceRepository,
        embedding_provider: OllamaEmbeddingProvider,
    ) -> None:
        self.retrieval_repository = retrieval_repository
        self.workspace_repository = workspace_repository
        self.embedding_provider = embedding_provider

    async def search_async(
        self,
        workspace_id: UUID,
        request: RetrievalSearchRequest,
        current_user: User,
    ) -> ApiResponse[RetrievalSearchResponse]:
        await self._require_active_workspace_member(workspace_id, current_user)
        query_embedding = await self._embed_query(request.query)
        rows = await self.retrieval_repository.search_chunks(
            workspace_id,
            query_embedding,
            request.top_k,
        )

        return ApiResponse.success_response(
            message="Retrieval search completed successfully.",
            data=RetrievalSearchResponse(results=[_result_from_row(row) for row in rows]),
        )

    async def _embed_query(self, query: str) -> list[float]:
        vectors = await self.embedding_provider.embed_texts([query])
        if len(vectors) != 1:
            raise ExternalProviderException("Embedding provider returned invalid embeddings.")
        return vectors[0]

    async def _require_active_workspace_member(
        self,
        workspace_id: UUID,
        current_user: User,
    ) -> None:
        if not current_user.is_active:
            raise ForbiddenException("User account is inactive.")

        member = await self.workspace_repository.get_member(workspace_id, current_user.id)
        if member is None:
            raise NotFoundException(WORKSPACE_NOT_FOUND_MESSAGE)

        workspace = await self.workspace_repository.get_workspace_by_id(workspace_id)
        if workspace is None or not workspace.is_active:
            raise NotFoundException(WORKSPACE_NOT_FOUND_MESSAGE)


def _result_from_row(row: RetrievalSearchRow) -> RetrievalSearchResult:
    return RetrievalSearchResult(
        documentId=row.document_id,
        documentName=row.document_name,
        chunkId=row.chunk_id,
        pageNumber=row.page_number,
        snippet=row.snippet,
        score=row.score,
    )
