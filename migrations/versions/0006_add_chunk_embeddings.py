"""add chunk embeddings

Revision ID: 0006_add_chunk_embeddings
Revises: 0005_create_document_chunks
Create Date: 2026-07-09 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

from app.core.config import EMBEDDING_VECTOR_DIMENSION

revision: str = "0006_add_chunk_embeddings"
down_revision: str | None = "0005_create_document_chunks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column(
        "document_chunks",
        sa.Column("embedding", Vector(EMBEDDING_VECTOR_DIMENSION), nullable=True),
    )
    op.add_column(
        "document_chunks",
        sa.Column(
            "embedding_status",
            sa.String(length=20),
            server_default="Pending",
            nullable=False,
        ),
    )
    op.add_column(
        "document_chunks",
        sa.Column("embedded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "document_chunks",
        sa.Column("embedding_error", sa.String(length=500), nullable=True),
    )
    op.create_check_constraint(
        "ck_document_chunks_embedding_status",
        "document_chunks",
        "embedding_status IN ('Pending', 'Processing', 'Ready', 'Failed')",
    )
    op.create_index(
        "ix_document_chunks_workspace_embedding_status",
        "document_chunks",
        ["workspace_id", "embedding_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_document_chunks_workspace_embedding_status", table_name="document_chunks")
    op.drop_constraint(
        "ck_document_chunks_embedding_status",
        "document_chunks",
        type_="check",
    )
    op.drop_column("document_chunks", "embedding_error")
    op.drop_column("document_chunks", "embedded_at")
    op.drop_column("document_chunks", "embedding_status")
    op.drop_column("document_chunks", "embedding")
