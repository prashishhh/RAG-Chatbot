"""add workspace role constraint

Revision ID: 0003_workspace_role_check
Revises: 0002_create_workspace_tables
Create Date: 2026-07-08 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003_workspace_role_check"
down_revision: str | None = "0002_create_workspace_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_workspace_members_role",
        "workspace_members",
        "role IN ('Owner', 'Admin', 'Member', 'Viewer')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_workspace_members_role",
        "workspace_members",
        type_="check",
    )
