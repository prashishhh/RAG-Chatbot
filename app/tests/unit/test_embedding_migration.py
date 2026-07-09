from pathlib import Path

MIGRATION = Path("migrations/versions/0006_add_chunk_embeddings.py").read_text()


def test_embedding_migration_enables_vector_extension() -> None:
    assert '"CREATE EXTENSION IF NOT EXISTS vector"' in MIGRATION


def test_embedding_migration_adds_chunk_embedding_columns() -> None:
    assert '"embedding", Vector(EMBEDDING_VECTOR_DIMENSION), nullable=True' in MIGRATION
    assert '"embedding_status"' in MIGRATION
    assert 'server_default="Pending"' in MIGRATION
    assert '"embedded_at", sa.DateTime(timezone=True), nullable=True' in MIGRATION
    assert '"embedding_error", sa.String(length=500), nullable=True' in MIGRATION


def test_embedding_migration_has_security_constraints() -> None:
    assert '"ck_document_chunks_embedding_status"' in MIGRATION
    assert "embedding_status IN ('Pending', 'Processing', 'Ready', 'Failed')" in MIGRATION


def test_embedding_migration_indexes_workspace_scoped_jobs() -> None:
    assert '"ix_document_chunks_workspace_embedding_status"' in MIGRATION
    assert '["workspace_id", "embedding_status"]' in MIGRATION
