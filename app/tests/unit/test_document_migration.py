from pathlib import Path

MIGRATION = Path("migrations/versions/0004_create_documents_table.py").read_text()


def test_document_migration_creates_documents_table() -> None:
    assert '"documents"' in MIGRATION


def test_document_migration_has_security_constraints() -> None:
    assert '"ck_documents_status"' in MIGRATION
    assert '"ck_documents_size_bytes_positive"' in MIGRATION
    assert 'name="fk_documents_workspace_id"' in MIGRATION
    assert 'name="fk_documents_uploaded_by_user_id"' in MIGRATION
    assert 'ondelete="CASCADE"' in MIGRATION
    assert 'ondelete="RESTRICT"' in MIGRATION


def test_document_migration_indexes_workspace_scoped_lookups() -> None:
    assert '"ix_documents_workspace_id"' in MIGRATION
    assert '"ix_documents_uploaded_by_user_id"' in MIGRATION
    assert '"ix_documents_workspace_status"' in MIGRATION


def test_document_migration_has_soft_delete_column() -> None:
    assert '"deleted_at", sa.DateTime(timezone=True), nullable=True' in MIGRATION
