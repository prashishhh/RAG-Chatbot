import asyncio
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.core.responses import ApiResponse
from app.modules.documents.models import (
    ChunkEmbeddingStatus,
    Document,
    DocumentChunk,
    DocumentStatus,
)
from app.modules.documents.repository import DocumentRepository
from app.modules.ingestion.chunking import PreparedChunk


class FakeResult:
    def __init__(self, value: object | None = None, rows: list[object] | None = None) -> None:
        self.value = value
        self.rows = rows or []

    def scalar_one_or_none(self) -> object | None:
        return self.value

    def all(self) -> list[object]:
        return self.rows

    def scalars(self) -> "FakeResult":
        return self


class FakeSession:
    def __init__(self, execute_result: FakeResult | None = None) -> None:
        self.added: list[object] = []
        self.flush_count = 0
        self.executed: list[object] = []
        self.deleted: list[object] = []
        self.execute_result = execute_result or FakeResult()

    def add(self, value: object) -> None:
        self.added.append(value)

    def add_all(self, values: list[object]) -> None:
        self.added.extend(values)

    async def delete(self, value: object) -> None:
        self.deleted.append(value)

    async def flush(self) -> None:
        self.flush_count += 1

    async def execute(self, statement: object) -> FakeResult:
        self.executed.append(statement)
        return self.execute_result


def make_document() -> Document:
    return Document(
        id=uuid4(),
        workspace_id=uuid4(),
        uploaded_by_user_id=uuid4(),
        original_filename="Report.pdf",
        stored_filename="Report.pdf",
        object_key="workspaces/1/documents/2/original/Report.pdf",
        content_type="application/pdf",
        size_bytes=123,
        status=DocumentStatus.UPLOADED,
        created_at=datetime(2026, 7, 8, tzinfo=UTC),
        updated_at=datetime(2026, 7, 8, tzinfo=UTC),
    )


def make_chunk(document: Document, chunk_index: int = 0) -> DocumentChunk:
    return DocumentChunk(
        workspace_id=document.workspace_id,
        document_id=document.id,
        chunk_index=chunk_index,
        content="chunk",
        content_hash="a" * 64,
        char_count=5,
    )


def test_create_document_adds_and_flushes_without_api_response() -> None:
    async def run_test() -> None:
        session = FakeSession()
        repository = DocumentRepository(session)  # type: ignore[arg-type]
        document = make_document()

        result = await repository.create_document(document)

        assert result is document
        assert not isinstance(result, ApiResponse)
        assert session.added == [document]
        assert session.flush_count == 1

    asyncio.run(run_test())


def test_list_documents_returns_workspace_scoped_rows() -> None:
    async def run_test() -> None:
        document = make_document()
        session = FakeSession(execute_result=FakeResult(rows=[document]))
        repository = DocumentRepository(session)  # type: ignore[arg-type]

        result = await repository.list_documents(document.workspace_id)

        assert result == [document]
        assert len(session.executed) == 1

    asyncio.run(run_test())


def test_get_document_by_id_returns_workspace_scoped_document() -> None:
    async def run_test() -> None:
        document = make_document()
        session = FakeSession(execute_result=FakeResult(value=document))
        repository = DocumentRepository(session)  # type: ignore[arg-type]

        result = await repository.get_document_by_id(document.workspace_id, document.id)

        assert result is document
        assert len(session.executed) == 1

    asyncio.run(run_test())


def test_update_status_sets_status_and_flushes() -> None:
    async def run_test() -> None:
        session = FakeSession()
        repository = DocumentRepository(session)  # type: ignore[arg-type]
        document = make_document()

        result = await repository.update_status(document, DocumentStatus.READY)

        assert result.status == DocumentStatus.READY
        assert session.flush_count == 1

    asyncio.run(run_test())


def test_mark_ingestion_processing_sets_safe_state() -> None:
    async def run_test() -> None:
        session = FakeSession()
        repository = DocumentRepository(session)  # type: ignore[arg-type]
        document = make_document()
        document.ingestion_error = "old error"

        result = await repository.mark_ingestion_processing(document)

        assert result.status == DocumentStatus.PROCESSING
        assert result.ingestion_started_at is not None
        assert result.ingestion_completed_at is None
        assert result.ingestion_error is None
        assert session.flush_count == 1

    asyncio.run(run_test())


def test_mark_ingestion_ready_sets_count_and_completion() -> None:
    async def run_test() -> None:
        session = FakeSession()
        repository = DocumentRepository(session)  # type: ignore[arg-type]
        document = make_document()

        result = await repository.mark_ingestion_ready(document, 123)

        assert result.status == DocumentStatus.READY
        assert result.ingestion_completed_at is not None
        assert result.text_char_count == 123
        assert result.ingestion_error is None
        assert session.flush_count == 1

    asyncio.run(run_test())


def test_mark_ingestion_failed_truncates_safe_error() -> None:
    async def run_test() -> None:
        session = FakeSession()
        repository = DocumentRepository(session)  # type: ignore[arg-type]
        document = make_document()

        result = await repository.mark_ingestion_failed(document, "x" * 600)

        assert result.status == DocumentStatus.FAILED
        assert result.ingestion_completed_at is not None
        assert result.ingestion_error == "x" * 500
        assert session.flush_count == 1

    asyncio.run(run_test())


def test_replace_chunks_deletes_existing_and_adds_new_rows() -> None:
    async def run_test() -> None:
        old_chunk = DocumentChunk(
            workspace_id=uuid4(),
            document_id=uuid4(),
            chunk_index=0,
            content="old",
            content_hash="a" * 64,
            char_count=3,
        )
        session = FakeSession(execute_result=FakeResult(rows=[old_chunk]))
        repository = DocumentRepository(session)  # type: ignore[arg-type]
        document = make_document()

        rows = await repository.replace_chunks(
            document,
            [
                PreparedChunk(
                    chunk_index=0,
                    content="hello",
                    content_hash="b" * 64,
                    char_count=5,
                    page_number=1,
                )
            ],
        )

        assert session.deleted == [old_chunk]
        assert len(rows) == 1
        assert rows[0] in session.added
        assert rows[0].workspace_id == document.workspace_id
        assert rows[0].document_id == document.id
        assert rows[0].page_number == 1
        assert session.flush_count == 2

    asyncio.run(run_test())


def test_soft_delete_marks_deleted_and_flushes() -> None:
    async def run_test() -> None:
        session = FakeSession()
        repository = DocumentRepository(session)  # type: ignore[arg-type]
        document = make_document()

        result = await repository.soft_delete(document)

        assert result.status == DocumentStatus.DELETED
        assert result.deleted_at is not None
        assert session.flush_count == 1

    asyncio.run(run_test())


def test_list_chunks_needing_embeddings_returns_workspace_scoped_chunks() -> None:
    async def run_test() -> None:
        document = make_document()
        chunk = make_chunk(document)
        session = FakeSession(execute_result=FakeResult(rows=[chunk]))
        repository = DocumentRepository(session)  # type: ignore[arg-type]

        result = await repository.list_chunks_needing_embeddings(document.workspace_id, document.id)

        assert result == [chunk]
        assert len(session.executed) == 1

    asyncio.run(run_test())


def test_mark_chunks_embedding_processing_clears_error_and_flushes() -> None:
    async def run_test() -> None:
        session = FakeSession()
        repository = DocumentRepository(session)  # type: ignore[arg-type]
        document = make_document()
        chunk = make_chunk(document)
        chunk.embedding_error = "old"

        result = await repository.mark_chunks_embedding_processing([chunk])

        assert result == [chunk]
        assert chunk.embedding_status == ChunkEmbeddingStatus.PROCESSING
        assert chunk.embedding_error is None
        assert session.flush_count == 1

    asyncio.run(run_test())


def test_mark_chunks_embedding_ready_stores_vectors_and_safe_state() -> None:
    async def run_test() -> None:
        session = FakeSession()
        repository = DocumentRepository(session)  # type: ignore[arg-type]
        document = make_document()
        chunk = make_chunk(document)
        vector = [0.1, 0.2]

        result = await repository.mark_chunks_embedding_ready([(chunk, vector)])

        assert result == [chunk]
        assert chunk.embedding == vector
        assert chunk.embedding_status == ChunkEmbeddingStatus.READY
        assert chunk.embedded_at is not None
        assert chunk.embedding_error is None
        assert session.flush_count == 1

    asyncio.run(run_test())


def test_mark_chunks_embedding_failed_truncates_safe_error() -> None:
    async def run_test() -> None:
        session = FakeSession()
        repository = DocumentRepository(session)  # type: ignore[arg-type]
        document = make_document()
        chunk = make_chunk(document)

        result = await repository.mark_chunks_embedding_failed([chunk], "x" * 600)

        assert result == [chunk]
        assert chunk.embedding_status == ChunkEmbeddingStatus.FAILED
        assert chunk.embedding_error == "x" * 500
        assert session.flush_count == 1

    asyncio.run(run_test())


def test_repository_does_not_import_or_return_api_response_contracts() -> None:
    source = Path("app/modules/documents/repository.py").read_text()

    assert "ApiResponse" not in source
    assert "PagedResponse" not in source
    assert "success_response" not in source
    assert "error_response" not in source
