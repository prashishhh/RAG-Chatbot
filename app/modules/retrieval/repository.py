from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.documents.models import (
    ChunkEmbeddingStatus,
    Document,
    DocumentChunk,
    DocumentStatus,
)
from app.modules.retrieval.schemas import RETRIEVAL_SNIPPET_MAX_LENGTH


@dataclass(frozen=True)
class RetrievalSearchRow:
    document_id: UUID
    document_name: str
    chunk_id: UUID
    page_number: int | None
    snippet: str
    score: float


class RetrievalRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def search_chunks(
        self,
        workspace_id: UUID,
        query_embedding: list[float],
        top_k: int,
    ) -> list[RetrievalSearchRow]:
        distance = DocumentChunk.embedding.cosine_distance(query_embedding)
        score = func.greatest(0.0, 1.0 - distance)
        result = await self.db.execute(
            select(
                Document.id.label("document_id"),
                Document.original_filename.label("document_name"),
                DocumentChunk.id.label("chunk_id"),
                DocumentChunk.page_number.label("page_number"),
                func.substr(DocumentChunk.content, 1, RETRIEVAL_SNIPPET_MAX_LENGTH).label(
                    "snippet"
                ),
                score.label("score"),
            )
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(
                DocumentChunk.workspace_id == workspace_id,
                Document.workspace_id == workspace_id,
                Document.deleted_at.is_(None),
                Document.status == DocumentStatus.READY,
                DocumentChunk.embedding_status == ChunkEmbeddingStatus.READY,
                DocumentChunk.embedding.is_not(None),
            )
            .order_by(distance.asc())
            .limit(top_k)
        )

        return [
            RetrievalSearchRow(
                document_id=row.document_id,
                document_name=row.document_name,
                chunk_id=row.chunk_id,
                page_number=row.page_number,
                snippet=row.snippet,
                score=float(row.score),
            )
            for row in result.all()
        ]
