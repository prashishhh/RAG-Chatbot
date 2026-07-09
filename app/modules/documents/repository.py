from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.documents.models import (
    ChunkEmbeddingStatus,
    Document,
    DocumentChunk,
    DocumentStatus,
)
from app.modules.ingestion.chunking import PreparedChunk


class DocumentRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_document(self, document: Document) -> Document:
        self.db.add(document)
        await self.db.flush()
        return document

    async def list_documents(self, workspace_id: UUID) -> list[Document]:
        result = await self.db.execute(
            select(Document)
            .where(
                Document.workspace_id == workspace_id,
                Document.deleted_at.is_(None),
                Document.status != DocumentStatus.DELETED,
            )
            .order_by(Document.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_document_by_id(self, workspace_id: UUID, document_id: UUID) -> Document | None:
        result = await self.db.execute(
            select(Document).where(
                Document.workspace_id == workspace_id,
                Document.id == document_id,
                Document.deleted_at.is_(None),
                Document.status != DocumentStatus.DELETED,
            )
        )
        return result.scalar_one_or_none()

    async def update_status(self, document: Document, status: DocumentStatus) -> Document:
        document.status = status
        await self.db.flush()
        return document

    async def mark_ingestion_processing(self, document: Document) -> Document:
        document.status = DocumentStatus.PROCESSING
        document.ingestion_started_at = datetime.now(UTC)
        document.ingestion_completed_at = None
        document.ingestion_error = None
        await self.db.flush()
        return document

    async def mark_ingestion_ready(self, document: Document, text_char_count: int) -> Document:
        document.status = DocumentStatus.READY
        document.ingestion_completed_at = datetime.now(UTC)
        document.ingestion_error = None
        document.text_char_count = text_char_count
        await self.db.flush()
        return document

    async def mark_ingestion_failed(self, document: Document, error: str) -> Document:
        document.status = DocumentStatus.FAILED
        document.ingestion_completed_at = datetime.now(UTC)
        document.ingestion_error = error[:500]
        await self.db.flush()
        return document

    async def replace_chunks(
        self,
        document: Document,
        chunks: list[PreparedChunk],
    ) -> list[DocumentChunk]:
        await self.delete_chunks(document.id)
        rows = [
            DocumentChunk(
                workspace_id=document.workspace_id,
                document_id=document.id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                content_hash=chunk.content_hash,
                char_count=chunk.char_count,
                page_number=chunk.page_number,
                section_title=chunk.section_title,
            )
            for chunk in chunks
        ]
        self.db.add_all(rows)
        await self.db.flush()
        return rows

    async def delete_chunks(self, document_id: UUID) -> None:
        result = await self.db.execute(
            select(DocumentChunk).where(DocumentChunk.document_id == document_id)
        )
        for chunk in result.scalars().all():
            await self.db.delete(chunk)
        await self.db.flush()

    async def list_chunks_needing_embeddings(
        self,
        workspace_id: UUID,
        document_id: UUID,
    ) -> list[DocumentChunk]:
        result = await self.db.execute(
            select(DocumentChunk)
            .where(
                DocumentChunk.workspace_id == workspace_id,
                DocumentChunk.document_id == document_id,
                DocumentChunk.embedding_status.in_(
                    [ChunkEmbeddingStatus.PENDING, ChunkEmbeddingStatus.FAILED]
                ),
            )
            .order_by(DocumentChunk.chunk_index)
            .with_for_update(skip_locked=True)
        )
        return list(result.scalars().all())

    async def mark_chunks_embedding_processing(
        self,
        chunks: list[DocumentChunk],
    ) -> list[DocumentChunk]:
        for chunk in chunks:
            chunk.embedding_status = ChunkEmbeddingStatus.PROCESSING
            chunk.embedding_error = None
        await self.db.flush()
        return chunks

    async def mark_chunks_embedding_ready(
        self,
        chunk_vectors: list[tuple[DocumentChunk, list[float]]],
    ) -> list[DocumentChunk]:
        now = datetime.now(UTC)
        chunks: list[DocumentChunk] = []
        for chunk, vector in chunk_vectors:
            chunk.embedding = vector
            chunk.embedding_status = ChunkEmbeddingStatus.READY
            chunk.embedded_at = now
            chunk.embedding_error = None
            chunks.append(chunk)
        await self.db.flush()
        return chunks

    async def mark_chunks_embedding_failed(
        self,
        chunks: list[DocumentChunk],
        error: str,
    ) -> list[DocumentChunk]:
        for chunk in chunks:
            chunk.embedding_status = ChunkEmbeddingStatus.FAILED
            chunk.embedding_error = error[:500]
        await self.db.flush()
        return chunks

    async def soft_delete(self, document: Document) -> Document:
        document.status = DocumentStatus.DELETED
        document.deleted_at = datetime.now(UTC)
        await self.db.flush()
        return document
