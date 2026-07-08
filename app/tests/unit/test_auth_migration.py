from pathlib import Path

MIGRATION = Path("migrations/versions/0001_create_auth_tables.py")


def test_auth_migration_creates_required_tables() -> None:
    migration = MIGRATION.read_text()

    assert '"users"' in migration
    assert '"refresh_tokens"' in migration


def test_auth_migration_enforces_email_uniqueness_and_token_hash_index() -> None:
    migration = MIGRATION.read_text()

    assert 'sa.UniqueConstraint("email", name="uq_users_email")' in migration
    assert '"ix_users_email"' in migration
    assert '"ix_refresh_tokens_token_hash"' in migration


def test_auth_migration_uses_foreign_key_delete_rules() -> None:
    migration = MIGRATION.read_text()

    assert 'name="fk_refresh_tokens_user_id"' in migration
    assert 'ondelete="CASCADE"' in migration
    assert 'name="fk_refresh_tokens_replaced_by_token_id"' in migration
    assert 'ondelete="SET NULL"' in migration


def test_auth_migration_has_no_plaintext_refresh_token_column() -> None:
    migration = MIGRATION.read_text()

    assert 'sa.Column("token",' not in migration
    assert 'sa.Column("refresh_token",' not in migration
    assert 'sa.Column("plain_token",' not in migration
    assert 'sa.Column("token_hash"' in migration

