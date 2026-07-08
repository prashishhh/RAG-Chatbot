from pathlib import Path

MIGRATION = Path("migrations/versions/0002_create_workspace_tables.py").read_text()
ROLE_CONSTRAINT_MIGRATION = Path(
    "migrations/versions/0003_workspace_role_check.py"
).read_text()


def test_workspace_migration_creates_required_tables() -> None:
    assert '"workspaces"' in MIGRATION
    assert '"workspace_members"' in MIGRATION


def test_workspace_migration_has_security_constraints() -> None:
    assert 'name="uq_workspaces_slug"' in MIGRATION
    assert 'name="uq_workspace_members_workspace_user"' in MIGRATION
    assert 'name="fk_workspaces_created_by_user_id"' in MIGRATION
    assert 'name="fk_workspace_members_workspace_id"' in MIGRATION
    assert 'name="fk_workspace_members_user_id"' in MIGRATION
    assert 'ondelete="RESTRICT"' in MIGRATION
    assert 'ondelete="CASCADE"' in MIGRATION


def test_workspace_migration_indexes_lookup_columns() -> None:
    assert '"ix_workspaces_slug"' in MIGRATION
    assert '"ix_workspaces_created_by_user_id"' in MIGRATION
    assert '"ix_workspace_members_workspace_id"' in MIGRATION
    assert '"ix_workspace_members_user_id"' in MIGRATION


def test_workspace_member_migration_has_created_at() -> None:
    assert '"created_at", sa.DateTime(timezone=True), nullable=False' in MIGRATION


def test_workspace_role_constraint_migration_limits_valid_roles() -> None:
    assert '"ck_workspace_members_role"' in ROLE_CONSTRAINT_MIGRATION
    assert "role IN ('Owner', 'Admin', 'Member', 'Viewer')" in ROLE_CONSTRAINT_MIGRATION
