from app.core.config import EMBEDDING_VECTOR_DIMENSION
from app.modules.documents.models import (
    ChunkEmbeddingStatus,
    Document,
    DocumentChunk,
    DocumentStatus,
)


def test_document_has_required_security_constraints() -> None:
    constraint_names = {constraint.name for constraint in Document.__table__.constraints}
    index_names = {index.name for index in Document.__table__.indexes}

    assert "ck_documents_status" in constraint_names
    assert "ck_documents_size_bytes_positive" in constraint_names
    assert "ix_documents_workspace_id" in index_names
    assert "ix_documents_uploaded_by_user_id" in index_names
    assert "ix_documents_workspace_status" in index_names
    assert Document.__table__.c.workspace_id.nullable is False
    assert Document.__table__.c.uploaded_by_user_id.nullable is False
    assert Document.__table__.c.object_key.nullable is False
    assert Document.__table__.c.size_bytes.nullable is False
    assert Document.__table__.c.ingestion_started_at.nullable is True
    assert Document.__table__.c.ingestion_completed_at.nullable is True
    assert Document.__table__.c.ingestion_error.nullable is True
    assert Document.__table__.c.text_char_count.nullable is True


def test_document_statuses_are_explicit() -> None:
    assert {status.value for status in DocumentStatus} == {
        "Uploaded",
        "PendingIngestion",
        "Processing",
        "Ready",
        "Failed",
        "Deleted",
    }


def test_chunk_embedding_statuses_are_explicit() -> None:
    assert {status.value for status in ChunkEmbeddingStatus} == {
        "Pending",
        "Processing",
        "Ready",
        "Failed",
    }


def test_document_chunk_has_required_security_constraints() -> None:
    constraint_names = {constraint.name for constraint in DocumentChunk.__table__.constraints}
    index_names = {index.name for index in DocumentChunk.__table__.indexes}

    assert "ck_document_chunks_chunk_index_non_negative" in constraint_names
    assert "ck_document_chunks_char_count_positive" in constraint_names
    assert "ck_document_chunks_hash_length" in constraint_names
    assert "ck_document_chunks_embedding_status" in constraint_names
    assert "ix_document_chunks_workspace_id" in index_names
    assert "ix_document_chunks_document_id" in index_names
    assert "ix_document_chunks_document_index" in index_names
    assert "ix_document_chunks_workspace_hash" in index_names
    assert "ix_document_chunks_workspace_embedding_status" in index_names
    assert DocumentChunk.__table__.c.workspace_id.nullable is False
    assert DocumentChunk.__table__.c.document_id.nullable is False
    assert DocumentChunk.__table__.c.chunk_index.nullable is False
    assert DocumentChunk.__table__.c.content.nullable is False
    assert DocumentChunk.__table__.c.content_hash.nullable is False
    assert DocumentChunk.__table__.c.char_count.nullable is False
    assert DocumentChunk.__table__.c.embedding.nullable is True
    assert DocumentChunk.__table__.c.embedding_status.nullable is False
    assert DocumentChunk.__table__.c.embedding_status.server_default.arg == "Pending"
    assert DocumentChunk.__table__.c.embedded_at.nullable is True
    assert DocumentChunk.__table__.c.embedding_error.nullable is True
    assert DocumentChunk.__table__.c.embedding.type.dim == EMBEDDING_VECTOR_DIMENSION
