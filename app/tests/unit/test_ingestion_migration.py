from pathlib import Path

MIGRATION = Path("migrations/versions/0005_create_document_chunks.py").read_text()


def test_ingestion_migration_adds_document_metadata_columns() -> None:
    assert '"ingestion_started_at", sa.DateTime(timezone=True), nullable=True' in MIGRATION
    assert '"ingestion_completed_at", sa.DateTime(timezone=True), nullable=True' in MIGRATION
    assert '"ingestion_error", sa.String(length=500), nullable=True' in MIGRATION
    assert '"text_char_count", sa.Integer(), nullable=True' in MIGRATION


def test_ingestion_migration_creates_document_chunks_table() -> None:
    assert '"document_chunks"' in MIGRATION
    assert '"workspace_id", postgresql.UUID(as_uuid=True), nullable=False' in MIGRATION
    assert '"document_id", postgresql.UUID(as_uuid=True), nullable=False' in MIGRATION
    assert '"chunk_index", sa.Integer(), nullable=False' in MIGRATION
    assert '"content", sa.Text(), nullable=False' in MIGRATION
    assert '"content_hash", sa.String(length=64), nullable=False' in MIGRATION
    assert '"char_count", sa.Integer(), nullable=False' in MIGRATION


def test_ingestion_migration_has_security_constraints() -> None:
    assert '"ck_document_chunks_chunk_index_non_negative"' in MIGRATION
    assert '"ck_document_chunks_char_count_positive"' in MIGRATION
    assert '"ck_document_chunks_hash_length"' in MIGRATION
    assert 'name="fk_document_chunks_workspace_id"' in MIGRATION
    assert 'name="fk_document_chunks_document_id"' in MIGRATION
    assert 'ondelete="CASCADE"' in MIGRATION


def test_ingestion_migration_indexes_workspace_and_document_lookups() -> None:
    assert '"ix_document_chunks_workspace_id"' in MIGRATION
    assert '"ix_document_chunks_document_id"' in MIGRATION
    assert '"ix_document_chunks_document_index"' in MIGRATION
    assert "unique=True" in MIGRATION
    assert '"ix_document_chunks_workspace_hash"' in MIGRATION
