import asyncio
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from app.core.responses import ApiResponse
from app.modules.retrieval.repository import RetrievalRepository, RetrievalSearchRow


class FakeResult:
    def __init__(self, rows: list[object] | None = None) -> None:
        self.rows = rows or []

    def all(self) -> list[object]:
        return self.rows


class FakeSession:
    def __init__(self, execute_result: FakeResult | None = None) -> None:
        self.executed: list[object] = []
        self.execute_result = execute_result or FakeResult()

    async def execute(self, statement: object) -> FakeResult:
        self.executed.append(statement)
        return self.execute_result


def test_search_chunks_returns_internal_rows_without_api_contracts() -> None:
    async def run_test() -> None:
        document_id = uuid4()
        chunk_id = uuid4()
        row = SimpleNamespace(
            document_id=document_id,
            document_name="Report.pdf",
            chunk_id=chunk_id,
            page_number=2,
            snippet="Relevant excerpt",
            score=0.82,
        )
        session = FakeSession(execute_result=FakeResult(rows=[row]))
        repository = RetrievalRepository(session)  # type: ignore[arg-type]

        result = await repository.search_chunks(uuid4(), [0.1, 0.2], 5)

        assert result == [
            RetrievalSearchRow(
                document_id=document_id,
                document_name="Report.pdf",
                chunk_id=chunk_id,
                page_number=2,
                snippet="Relevant excerpt",
                score=0.82,
            )
        ]
        assert not isinstance(result[0], ApiResponse)

    asyncio.run(run_test())


def test_search_chunks_query_is_workspace_scoped_and_safe() -> None:
    async def run_test() -> None:
        session = FakeSession()
        repository = RetrievalRepository(session)  # type: ignore[arg-type]
        workspace_id = uuid4()

        await repository.search_chunks(workspace_id, [0.1, 0.2], 5)

        statement = str(session.executed[0])
        assert "document_chunks.workspace_id" in statement
        assert "documents.workspace_id" in statement
        assert "documents.deleted_at IS NULL" in statement
        assert "documents.status" in statement
        assert "document_chunks.embedding_status" in statement
        assert "document_chunks.embedding IS NOT NULL" in statement
        assert "substr(document_chunks.content" in statement
        assert "document_chunks.embedding <=> :embedding_1" in statement
        assert "ORDER BY (document_chunks.embedding <=> :embedding_1) ASC" in statement

    asyncio.run(run_test())


def test_search_chunks_query_excludes_deleted_and_unembedded_rows() -> None:
    async def run_test() -> None:
        session = FakeSession()
        repository = RetrievalRepository(session)  # type: ignore[arg-type]

        await repository.search_chunks(uuid4(), [0.1, 0.2], 5)

        statement = str(session.executed[0])
        assert "documents.deleted_at IS NULL" in statement
        assert "documents.status" in statement
        assert "document_chunks.embedding_status" in statement
        assert "document_chunks.embedding IS NOT NULL" in statement

    asyncio.run(run_test())


def test_retrieval_repository_does_not_import_or_return_api_response_contracts() -> None:
    source = Path("app/modules/retrieval/repository.py").read_text()

    assert "ApiResponse" not in source
    assert "PagedResponse" not in source
    assert "success_response" not in source
    assert "error_response" not in source
