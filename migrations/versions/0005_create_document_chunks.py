"""create document chunks

Revision ID: 0005_create_document_chunks
Revises: 0004_create_documents_table
Create Date: 2026-07-08 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_create_document_chunks"
down_revision: str | None = "0004_create_documents_table"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("ingestion_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("ingestion_completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("documents", sa.Column("ingestion_error", sa.String(length=500), nullable=True))
    op.add_column("documents", sa.Column("text_char_count", sa.Integer(), nullable=True))

    op.create_table(
        "document_chunks",
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("section_title", sa.String(length=255), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "chunk_index >= 0",
            name="ck_document_chunks_chunk_index_non_negative",
        ),
        sa.CheckConstraint("char_count > 0", name="ck_document_chunks_char_count_positive"),
        sa.CheckConstraint("length(content_hash) = 64", name="ck_document_chunks_hash_length"),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name="fk_document_chunks_document_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_document_chunks_workspace_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_document_chunks_workspace_id", "document_chunks", ["workspace_id"])
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])
    op.create_index(
        "ix_document_chunks_document_index",
        "document_chunks",
        ["document_id", "chunk_index"],
        unique=True,
    )
    op.create_index(
        "ix_document_chunks_workspace_hash",
        "document_chunks",
        ["workspace_id", "content_hash"],
    )


def downgrade() -> None:
    op.drop_index("ix_document_chunks_workspace_hash", table_name="document_chunks")
    op.drop_index("ix_document_chunks_document_index", table_name="document_chunks")
    op.drop_index("ix_document_chunks_document_id", table_name="document_chunks")
    op.drop_index("ix_document_chunks_workspace_id", table_name="document_chunks")
    op.drop_table("document_chunks")

    op.drop_column("documents", "text_char_count")
    op.drop_column("documents", "ingestion_error")
    op.drop_column("documents", "ingestion_completed_at")
    op.drop_column("documents", "ingestion_started_at")
