from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UuidPrimaryKeyMixin
from app.modules.auth.models import User
from app.modules.workspaces.models import Workspace


class DocumentStatus(StrEnum):
    UPLOADED = "Uploaded"
    PENDING_INGESTION = "PendingIngestion"
    PROCESSING = "Processing"
    READY = "Ready"
    FAILED = "Failed"
    DELETED = "Deleted"


class Document(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(
            "status IN ("
            "'Uploaded', 'PendingIngestion', 'Processing', 'Ready', 'Failed', 'Deleted'"
            ")",
            name="ck_documents_status",
        ),
        CheckConstraint("size_bytes > 0", name="ck_documents_size_bytes_positive"),
        Index("ix_documents_workspace_id", "workspace_id"),
        Index("ix_documents_uploaded_by_user_id", "uploaded_by_user_id"),
        Index("ix_documents_workspace_status", "workspace_id", "status"),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    uploaded_by_user_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(180), nullable=False)
    object_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(
        String(30),
        default=DocumentStatus.UPLOADED,
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ingestion_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ingestion_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ingestion_error: Mapped[str | None] = mapped_column(String(500))
    text_char_count: Mapped[int | None] = mapped_column(Integer)

    workspace: Mapped[Workspace] = relationship(foreign_keys=[workspace_id])
    uploaded_by: Mapped[User] = relationship(foreign_keys=[uploaded_by_user_id])
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )


class DocumentChunk(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        CheckConstraint("chunk_index >= 0", name="ck_document_chunks_chunk_index_non_negative"),
        CheckConstraint("char_count > 0", name="ck_document_chunks_char_count_positive"),
        CheckConstraint("length(content_hash) = 64", name="ck_document_chunks_hash_length"),
        Index("ix_document_chunks_workspace_id", "workspace_id"),
        Index("ix_document_chunks_document_id", "document_id"),
        Index("ix_document_chunks_document_index", "document_id", "chunk_index", unique=True),
        Index("ix_document_chunks_workspace_hash", "workspace_id", "content_hash"),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer)
    section_title: Mapped[str | None] = mapped_column(String(255))

    workspace: Mapped[Workspace] = relationship(foreign_keys=[workspace_id])
    document: Mapped[Document] = relationship(back_populates="chunks", foreign_keys=[document_id])
