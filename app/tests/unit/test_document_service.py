import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.core.config import Settings
from app.core.exceptions import (
    ConflictException,
    ExternalProviderException,
    ForbiddenException,
    NotFoundException,
    ValidationException,
)
from app.modules.auth.models import User
from app.modules.documents.models import (
    ChunkEmbeddingStatus,
    Document,
    DocumentChunk,
    DocumentStatus,
)
from app.modules.documents.service import DocumentService
from app.modules.workspaces.models import Workspace, WorkspaceMember, WorkspaceRole


class FakeDocumentRepository:
    def __init__(self, *, fail_create: bool = False) -> None:
        self.documents: dict[tuple[UUID, UUID], Document] = {}
        self.chunks: dict[tuple[UUID, UUID], list[DocumentChunk]] = {}
        self.replaced_chunks: list = []
        self.fail_create = fail_create

    async def create_document(self, document: Document) -> Document:
        if self.fail_create:
            raise RuntimeError("database failure")
        document.created_at = document.created_at or datetime.now(UTC)
        document.updated_at = document.updated_at or datetime.now(UTC)
        self.documents[(document.workspace_id, document.id)] = document
        return document

    async def list_documents(self, workspace_id: UUID) -> list[Document]:
        return [
            document
            for (document_workspace_id, _), document in self.documents.items()
            if document_workspace_id == workspace_id
            and document.deleted_at is None
            and document.status != DocumentStatus.DELETED
        ]

    async def get_document_by_id(self, workspace_id: UUID, document_id: UUID) -> Document | None:
        document = self.documents.get((workspace_id, document_id))
        if (
            document is None
            or document.deleted_at is not None
            or document.status == DocumentStatus.DELETED
        ):
            return None
        return document

    async def soft_delete(self, document: Document) -> Document:
        document.status = DocumentStatus.DELETED
        document.deleted_at = datetime.now(UTC)
        return document

    async def mark_ingestion_processing(self, document: Document) -> Document:
        document.status = DocumentStatus.PROCESSING
        document.ingestion_started_at = datetime.now(UTC)
        document.ingestion_completed_at = None
        document.ingestion_error = None
        return document

    async def mark_ingestion_ready(self, document: Document, text_char_count: int) -> Document:
        document.status = DocumentStatus.READY
        document.ingestion_completed_at = datetime.now(UTC)
        document.ingestion_error = None
        document.text_char_count = text_char_count
        return document

    async def mark_ingestion_failed(self, document: Document, error: str) -> Document:
        document.status = DocumentStatus.FAILED
        document.ingestion_completed_at = datetime.now(UTC)
        document.ingestion_error = error[:500]
        return document

    async def replace_chunks(self, document: Document, chunks) -> list:
        self.replaced_chunks = list(chunks)
        return self.replaced_chunks

    async def list_chunks_needing_embeddings(
        self,
        workspace_id: UUID,
        document_id: UUID,
    ) -> list[DocumentChunk]:
        return [
            chunk
            for chunk in self.chunks.get((workspace_id, document_id), [])
            if chunk.embedding_status
            in {ChunkEmbeddingStatus.PENDING, ChunkEmbeddingStatus.FAILED}
        ]

    async def mark_chunks_embedding_processing(
        self,
        chunks: list[DocumentChunk],
    ) -> list[DocumentChunk]:
        for chunk in chunks:
            chunk.embedding_status = ChunkEmbeddingStatus.PROCESSING
            chunk.embedding_error = None
        return chunks

    async def mark_chunks_embedding_ready(
        self,
        chunk_vectors: list[tuple[DocumentChunk, list[float]]],
    ) -> list[DocumentChunk]:
        rows = []
        for chunk, vector in chunk_vectors:
            chunk.embedding = vector
            chunk.embedding_status = ChunkEmbeddingStatus.READY
            chunk.embedded_at = datetime.now(UTC)
            chunk.embedding_error = None
            rows.append(chunk)
        return rows

    async def mark_chunks_embedding_failed(
        self,
        chunks: list[DocumentChunk],
        error: str,
    ) -> list[DocumentChunk]:
        for chunk in chunks:
            chunk.embedding_status = ChunkEmbeddingStatus.FAILED
            chunk.embedding_error = error[:500]
        return chunks


class FakeWorkspaceRepository:
    def __init__(self) -> None:
        self.workspaces: dict[UUID, Workspace] = {}
        self.members: dict[tuple[UUID, UUID], WorkspaceMember] = {}

    async def get_workspace_by_id(self, workspace_id: UUID) -> Workspace | None:
        return self.workspaces.get(workspace_id)

    async def get_member(self, workspace_id: UUID, user_id: UUID) -> WorkspaceMember | None:
        return self.members.get((workspace_id, user_id))


class FakeStorageService:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.deleted_keys: list[str] = []

    def save_bytes(self, object_key: str, content: bytes) -> str:
        self.objects[object_key] = content
        return object_key

    def read_bytes(self, object_key: str) -> bytes:
        return self.objects[object_key]

    def delete(self, object_key: str) -> None:
        self.deleted_keys.append(object_key)
        self.objects.pop(object_key, None)


class FakeEmbeddingProvider:
    def __init__(
        self,
        *,
        vectors: list[list[float]] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.calls: list[list[str]] = []
        self.vectors = vectors or [[0.1]]
        self.error = error

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        if self.error is not None:
            raise self.error
        return self.vectors[: len(texts)]


def make_user(*, is_active: bool = True) -> User:
    return User(
        id=uuid4(),
        email="ram@example.com",
        full_name="Ram Sharma",
        password_hash="$argon2id$hash",  # noqa: S106
        is_active=is_active,
    )


def make_workspace(user_id: UUID, *, is_active: bool = True) -> Workspace:
    return Workspace(
        id=uuid4(),
        name="Acme Inc",
        slug="acme-inc",
        description=None,
        is_active=is_active,
        created_by_user_id=user_id,
        created_at=datetime(2026, 7, 8, tzinfo=UTC),
        updated_at=datetime(2026, 7, 8, tzinfo=UTC),
    )


def add_member(
    repository: FakeWorkspaceRepository,
    workspace: Workspace,
    user: User,
    role: WorkspaceRole,
) -> None:
    repository.members[(workspace.id, user.id)] = WorkspaceMember(
        id=uuid4(),
        workspace_id=workspace.id,
        user_id=user.id,
        role=role,
        created_at=datetime(2026, 7, 8, tzinfo=UTC),
    )


def make_document(workspace_id: UUID, user_id: UUID) -> Document:
    return Document(
        id=uuid4(),
        workspace_id=workspace_id,
        uploaded_by_user_id=user_id,
        original_filename="Report.txt",
        stored_filename="Report.txt",
        object_key="workspaces/1/documents/2/original/Report.pdf",
        content_type="text/plain",
        size_bytes=123,
        status=DocumentStatus.UPLOADED,
        created_at=datetime(2026, 7, 8, tzinfo=UTC),
        updated_at=datetime(2026, 7, 8, tzinfo=UTC),
    )


def make_chunk(document: Document, chunk_index: int = 0) -> DocumentChunk:
    return DocumentChunk(
        id=uuid4(),
        workspace_id=document.workspace_id,
        document_id=document.id,
        chunk_index=chunk_index,
        content=f"chunk {chunk_index}",
        content_hash="a" * 64,
        char_count=7,
        embedding_status=ChunkEmbeddingStatus.PENDING,
    )


def make_service(
    workspace_repository: FakeWorkspaceRepository,
    document_repository: FakeDocumentRepository | None = None,
    storage_service: FakeStorageService | None = None,
    embedding_provider: FakeEmbeddingProvider | None = None,
) -> tuple[DocumentService, FakeDocumentRepository, FakeStorageService]:
    documents = document_repository or FakeDocumentRepository()
    storage = storage_service or FakeStorageService()
    service = DocumentService(
        documents,  # type: ignore[arg-type]
        workspace_repository,  # type: ignore[arg-type]
        storage,  # type: ignore[arg-type]
        Settings(app_env="test"),
        embedding_provider,  # type: ignore[arg-type]
    )
    return service, documents, storage


def test_upload_document_success_for_member() -> None:
    async def run_test() -> None:
        workspace_repository = FakeWorkspaceRepository()
        user = make_user()
        workspace = make_workspace(user.id)
        workspace_repository.workspaces[workspace.id] = workspace
        add_member(workspace_repository, workspace, user, WorkspaceRole.MEMBER)
        service, documents, storage = make_service(workspace_repository)

        response = await service.upload_async(
            workspace.id,
            "../Report Final.PDF",
            "Application/PDF",
            b"pdf",
            user,
        )

        assert response.data is not None
        assert response.data.original_filename == "Report-Final.pdf"
        assert response.data.status == DocumentStatus.UPLOADED
        assert len(documents.documents) == 1
        document = next(iter(documents.documents.values()))
        assert document.object_key in storage.objects
        assert str(workspace.id) in document.object_key
        assert str(document.id) in document.object_key

    asyncio.run(run_test())


def test_upload_requires_member_or_above() -> None:
    async def run_test() -> None:
        workspace_repository = FakeWorkspaceRepository()
        user = make_user()
        workspace = make_workspace(user.id)
        workspace_repository.workspaces[workspace.id] = workspace
        add_member(workspace_repository, workspace, user, WorkspaceRole.VIEWER)
        service, _, _ = make_service(workspace_repository)

        with pytest.raises(ForbiddenException):
            await service.upload_async(workspace.id, "Report.pdf", "application/pdf", b"pdf", user)

    asyncio.run(run_test())


def test_upload_validates_file_before_storage() -> None:
    async def run_test() -> None:
        workspace_repository = FakeWorkspaceRepository()
        user = make_user()
        workspace = make_workspace(user.id)
        workspace_repository.workspaces[workspace.id] = workspace
        add_member(workspace_repository, workspace, user, WorkspaceRole.MEMBER)
        service, documents, storage = make_service(workspace_repository)

        with pytest.raises(ValidationException):
            await service.upload_async(workspace.id, "malware.exe", "application/pdf", b"pdf", user)

        assert documents.documents == {}
        assert storage.objects == {}

    asyncio.run(run_test())


def test_upload_deletes_saved_file_if_metadata_create_fails() -> None:
    async def run_test() -> None:
        workspace_repository = FakeWorkspaceRepository()
        user = make_user()
        workspace = make_workspace(user.id)
        workspace_repository.workspaces[workspace.id] = workspace
        add_member(workspace_repository, workspace, user, WorkspaceRole.ADMIN)
        failing_documents = FakeDocumentRepository(fail_create=True)
        service, _, storage = make_service(workspace_repository, failing_documents)

        with pytest.raises(RuntimeError, match="database failure"):
            await service.upload_async(workspace.id, "Report.pdf", "application/pdf", b"pdf", user)

        assert storage.objects == {}
        assert len(storage.deleted_keys) == 1

    asyncio.run(run_test())


def test_list_and_detail_allow_viewer() -> None:
    async def run_test() -> None:
        workspace_repository = FakeWorkspaceRepository()
        user = make_user()
        workspace = make_workspace(user.id)
        workspace_repository.workspaces[workspace.id] = workspace
        add_member(workspace_repository, workspace, user, WorkspaceRole.VIEWER)
        service, documents, _ = make_service(workspace_repository)
        document = make_document(workspace.id, user.id)
        documents.documents[(workspace.id, document.id)] = document

        list_response = await service.list_async(workspace.id, user)
        detail_response = await service.get_by_id_async(workspace.id, document.id, user)

        assert list_response.data is not None
        assert list_response.data[0].document_id == document.id
        assert detail_response.data is not None
        assert detail_response.data.document_id == document.id

    asyncio.run(run_test())


def test_detail_missing_document_returns_not_found() -> None:
    async def run_test() -> None:
        workspace_repository = FakeWorkspaceRepository()
        user = make_user()
        workspace = make_workspace(user.id)
        workspace_repository.workspaces[workspace.id] = workspace
        add_member(workspace_repository, workspace, user, WorkspaceRole.MEMBER)
        service, _, _ = make_service(workspace_repository)

        with pytest.raises(NotFoundException):
            await service.get_by_id_async(workspace.id, uuid4(), user)

    asyncio.run(run_test())


def test_delete_requires_admin_or_owner() -> None:
    async def run_test() -> None:
        workspace_repository = FakeWorkspaceRepository()
        user = make_user()
        workspace = make_workspace(user.id)
        workspace_repository.workspaces[workspace.id] = workspace
        add_member(workspace_repository, workspace, user, WorkspaceRole.MEMBER)
        service, documents, _ = make_service(workspace_repository)
        document = make_document(workspace.id, user.id)
        documents.documents[(workspace.id, document.id)] = document

        with pytest.raises(ForbiddenException):
            await service.delete_async(workspace.id, document.id, user)

    asyncio.run(run_test())


def test_admin_can_soft_delete_document() -> None:
    async def run_test() -> None:
        workspace_repository = FakeWorkspaceRepository()
        user = make_user()
        workspace = make_workspace(user.id)
        workspace_repository.workspaces[workspace.id] = workspace
        add_member(workspace_repository, workspace, user, WorkspaceRole.ADMIN)
        service, documents, _ = make_service(workspace_repository)
        document = make_document(workspace.id, user.id)
        documents.documents[(workspace.id, document.id)] = document

        response = await service.delete_async(workspace.id, document.id, user)

        assert response.data is not None
        assert response.data.status == DocumentStatus.DELETED
        assert document.deleted_at is not None

    asyncio.run(run_test())


def test_workspace_membership_and_active_user_required() -> None:
    async def run_test() -> None:
        workspace_repository = FakeWorkspaceRepository()
        user = make_user()
        inactive_user = make_user(is_active=False)
        workspace = make_workspace(user.id)
        workspace_repository.workspaces[workspace.id] = workspace
        service, _, _ = make_service(workspace_repository)

        with pytest.raises(NotFoundException):
            await service.list_async(workspace.id, user)

        add_member(workspace_repository, workspace, inactive_user, WorkspaceRole.ADMIN)
        with pytest.raises(ForbiddenException):
            await service.list_async(workspace.id, inactive_user)

    asyncio.run(run_test())


def test_ingest_document_success_for_member() -> None:
    async def run_test() -> None:
        workspace_repository = FakeWorkspaceRepository()
        user = make_user()
        workspace = make_workspace(user.id)
        workspace_repository.workspaces[workspace.id] = workspace
        add_member(workspace_repository, workspace, user, WorkspaceRole.MEMBER)
        service, documents, storage = make_service(workspace_repository)
        document = make_document(workspace.id, user.id)
        documents.documents[(workspace.id, document.id)] = document
        storage.objects[document.object_key] = b"first paragraph\n\nsecond paragraph"

        response = await service.ingest_async(workspace.id, document.id, user)

        assert response.data is not None
        assert response.data.document_id == document.id
        assert response.data.status == DocumentStatus.READY
        assert response.data.chunk_count == 1
        assert response.data.text_char_count == len("first paragraph\n\nsecond paragraph")
        assert document.status == DocumentStatus.READY
        assert document.ingestion_started_at is not None
        assert document.ingestion_completed_at is not None
        assert document.ingestion_error is None
        assert documents.replaced_chunks[0].page_number is None

    asyncio.run(run_test())


def test_ingest_requires_member_or_above() -> None:
    async def run_test() -> None:
        workspace_repository = FakeWorkspaceRepository()
        user = make_user()
        workspace = make_workspace(user.id)
        workspace_repository.workspaces[workspace.id] = workspace
        add_member(workspace_repository, workspace, user, WorkspaceRole.VIEWER)
        service, documents, _ = make_service(workspace_repository)
        document = make_document(workspace.id, user.id)
        documents.documents[(workspace.id, document.id)] = document

        with pytest.raises(ForbiddenException):
            await service.ingest_async(workspace.id, document.id, user)

    asyncio.run(run_test())


def test_ingest_rejects_processing_document() -> None:
    async def run_test() -> None:
        workspace_repository = FakeWorkspaceRepository()
        user = make_user()
        workspace = make_workspace(user.id)
        workspace_repository.workspaces[workspace.id] = workspace
        add_member(workspace_repository, workspace, user, WorkspaceRole.ADMIN)
        service, documents, _ = make_service(workspace_repository)
        document = make_document(workspace.id, user.id)
        document.status = DocumentStatus.PROCESSING
        documents.documents[(workspace.id, document.id)] = document

        with pytest.raises(ConflictException):
            await service.ingest_async(workspace.id, document.id, user)

    asyncio.run(run_test())


def test_ingest_missing_document_returns_not_found() -> None:
    async def run_test() -> None:
        workspace_repository = FakeWorkspaceRepository()
        user = make_user()
        workspace = make_workspace(user.id)
        workspace_repository.workspaces[workspace.id] = workspace
        add_member(workspace_repository, workspace, user, WorkspaceRole.ADMIN)
        service, _, _ = make_service(workspace_repository)

        with pytest.raises(NotFoundException):
            await service.ingest_async(workspace.id, uuid4(), user)

    asyncio.run(run_test())


def test_ingest_marks_failed_on_safe_extraction_error() -> None:
    async def run_test() -> None:
        workspace_repository = FakeWorkspaceRepository()
        user = make_user()
        workspace = make_workspace(user.id)
        workspace_repository.workspaces[workspace.id] = workspace
        add_member(workspace_repository, workspace, user, WorkspaceRole.ADMIN)
        service, documents, storage = make_service(workspace_repository)
        document = make_document(workspace.id, user.id)
        documents.documents[(workspace.id, document.id)] = document
        storage.objects[document.object_key] = b"\xff"

        with pytest.raises(ValidationException, match="could not be decoded"):
            await service.ingest_async(workspace.id, document.id, user)

        assert document.status == DocumentStatus.FAILED
        assert document.ingestion_completed_at is not None
        assert document.ingestion_error == "Document text could not be decoded."
        assert documents.replaced_chunks == []

    asyncio.run(run_test())


def test_embed_document_success_for_member() -> None:
    async def run_test() -> None:
        workspace_repository = FakeWorkspaceRepository()
        user = make_user()
        workspace = make_workspace(user.id)
        workspace_repository.workspaces[workspace.id] = workspace
        add_member(workspace_repository, workspace, user, WorkspaceRole.MEMBER)
        provider = FakeEmbeddingProvider(vectors=[[0.1], [0.2]])
        service, documents, _ = make_service(workspace_repository, embedding_provider=provider)
        document = make_document(workspace.id, user.id)
        document.status = DocumentStatus.READY
        chunks = [make_chunk(document, 0), make_chunk(document, 1)]
        documents.documents[(workspace.id, document.id)] = document
        documents.chunks[(workspace.id, document.id)] = chunks

        response = await service.embed_async(workspace.id, document.id, user)

        assert response.data is not None
        assert response.data.document_id == document.id
        assert response.data.embedded_chunk_count == 2
        assert provider.calls == [["chunk 0", "chunk 1"]]
        assert chunks[0].embedding == [0.1]
        assert chunks[1].embedding == [0.2]
        assert all(chunk.embedding_status == ChunkEmbeddingStatus.READY for chunk in chunks)

    asyncio.run(run_test())


def test_embed_document_batches_provider_calls() -> None:
    async def run_test() -> None:
        workspace_repository = FakeWorkspaceRepository()
        user = make_user()
        workspace = make_workspace(user.id)
        workspace_repository.workspaces[workspace.id] = workspace
        add_member(workspace_repository, workspace, user, WorkspaceRole.MEMBER)
        provider = FakeEmbeddingProvider(vectors=[[0.1]])
        service, documents, _ = make_service(workspace_repository, embedding_provider=provider)
        service.settings.embedding_batch_size = 1
        document = make_document(workspace.id, user.id)
        document.status = DocumentStatus.READY
        chunks = [make_chunk(document, 0), make_chunk(document, 1)]
        documents.documents[(workspace.id, document.id)] = document
        documents.chunks[(workspace.id, document.id)] = chunks

        response = await service.embed_async(workspace.id, document.id, user)

        assert response.data is not None
        assert response.data.embedded_chunk_count == 2
        assert provider.calls == [["chunk 0"], ["chunk 1"]]

    asyncio.run(run_test())


def test_embed_requires_member_or_above() -> None:
    async def run_test() -> None:
        workspace_repository = FakeWorkspaceRepository()
        user = make_user()
        workspace = make_workspace(user.id)
        workspace_repository.workspaces[workspace.id] = workspace
        add_member(workspace_repository, workspace, user, WorkspaceRole.VIEWER)
        service, documents, _ = make_service(workspace_repository)
        document = make_document(workspace.id, user.id)
        document.status = DocumentStatus.READY
        documents.documents[(workspace.id, document.id)] = document

        with pytest.raises(ForbiddenException):
            await service.embed_async(workspace.id, document.id, user)

    asyncio.run(run_test())


def test_embed_requires_ready_document() -> None:
    async def run_test() -> None:
        workspace_repository = FakeWorkspaceRepository()
        user = make_user()
        workspace = make_workspace(user.id)
        workspace_repository.workspaces[workspace.id] = workspace
        add_member(workspace_repository, workspace, user, WorkspaceRole.ADMIN)
        service, documents, _ = make_service(workspace_repository)
        document = make_document(workspace.id, user.id)
        documents.documents[(workspace.id, document.id)] = document

        with pytest.raises(ConflictException):
            await service.embed_async(workspace.id, document.id, user)

    asyncio.run(run_test())


def test_embed_returns_zero_when_chunks_are_already_embedded() -> None:
    async def run_test() -> None:
        workspace_repository = FakeWorkspaceRepository()
        user = make_user()
        workspace = make_workspace(user.id)
        workspace_repository.workspaces[workspace.id] = workspace
        add_member(workspace_repository, workspace, user, WorkspaceRole.ADMIN)
        provider = FakeEmbeddingProvider()
        service, documents, _ = make_service(workspace_repository, embedding_provider=provider)
        document = make_document(workspace.id, user.id)
        document.status = DocumentStatus.READY
        documents.documents[(workspace.id, document.id)] = document

        response = await service.embed_async(workspace.id, document.id, user)

        assert response.data is not None
        assert response.data.embedded_chunk_count == 0
        assert provider.calls == []

    asyncio.run(run_test())


def test_embed_marks_chunks_failed_on_provider_error_without_raw_text() -> None:
    async def run_test() -> None:
        workspace_repository = FakeWorkspaceRepository()
        user = make_user()
        workspace = make_workspace(user.id)
        workspace_repository.workspaces[workspace.id] = workspace
        add_member(workspace_repository, workspace, user, WorkspaceRole.ADMIN)
        provider = FakeEmbeddingProvider(
            error=ExternalProviderException("Embedding provider is unavailable.")
        )
        service, documents, _ = make_service(workspace_repository, embedding_provider=provider)
        document = make_document(workspace.id, user.id)
        document.status = DocumentStatus.READY
        chunk = make_chunk(document)
        chunk.content = "raw private chunk text"
        documents.documents[(workspace.id, document.id)] = document
        documents.chunks[(workspace.id, document.id)] = [chunk]

        with pytest.raises(ExternalProviderException):
            await service.embed_async(workspace.id, document.id, user)

        assert chunk.embedding_status == ChunkEmbeddingStatus.FAILED
        assert chunk.embedding_error == "Embedding provider is unavailable."
        assert "raw private chunk text" not in (chunk.embedding_error or "")

    asyncio.run(run_test())
