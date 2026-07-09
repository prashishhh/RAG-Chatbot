import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.core.exceptions import ExternalProviderException, ForbiddenException, NotFoundException
from app.core.responses import ApiResponse
from app.modules.auth.models import User
from app.modules.retrieval.repository import RetrievalSearchRow
from app.modules.retrieval.schemas import RetrievalSearchRequest
from app.modules.retrieval.service import RetrievalService
from app.modules.workspaces.models import Workspace, WorkspaceMember, WorkspaceRole


class FakeRetrievalRepository:
    def __init__(self, rows: list[RetrievalSearchRow] | None = None) -> None:
        self.rows = rows or []
        self.calls: list[tuple[UUID, list[float], int]] = []

    async def search_chunks(
        self,
        workspace_id: UUID,
        query_embedding: list[float],
        top_k: int,
    ) -> list[RetrievalSearchRow]:
        self.calls.append((workspace_id, query_embedding, top_k))
        return self.rows


class FakeWorkspaceRepository:
    def __init__(self) -> None:
        self.workspaces: dict[UUID, Workspace] = {}
        self.members: dict[tuple[UUID, UUID], WorkspaceMember] = {}

    async def get_workspace_by_id(self, workspace_id: UUID) -> Workspace | None:
        return self.workspaces.get(workspace_id)

    async def get_member(self, workspace_id: UUID, user_id: UUID) -> WorkspaceMember | None:
        return self.members.get((workspace_id, user_id))


class FakeEmbeddingProvider:
    def __init__(
        self,
        *,
        vectors: list[list[float]] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.calls: list[list[str]] = []
        self.vectors = [[0.1, 0.2]] if vectors is None else vectors
        self.error = error

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        if self.error is not None:
            raise self.error
        return self.vectors


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
        created_at=datetime(2026, 7, 9, tzinfo=UTC),
        updated_at=datetime(2026, 7, 9, tzinfo=UTC),
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
        created_at=datetime(2026, 7, 9, tzinfo=UTC),
    )


def make_service(
    workspace_repository: FakeWorkspaceRepository,
    retrieval_repository: FakeRetrievalRepository | None = None,
    embedding_provider: FakeEmbeddingProvider | None = None,
) -> tuple[RetrievalService, FakeRetrievalRepository, FakeEmbeddingProvider]:
    retrieval = retrieval_repository or FakeRetrievalRepository()
    provider = embedding_provider or FakeEmbeddingProvider()
    service = RetrievalService(
        retrieval,  # type: ignore[arg-type]
        workspace_repository,  # type: ignore[arg-type]
        provider,  # type: ignore[arg-type]
    )
    return service, retrieval, provider


def test_search_allows_viewer_and_returns_safe_results() -> None:
    async def run_test() -> None:
        user = make_user()
        workspace_repository = FakeWorkspaceRepository()
        workspace = make_workspace(user.id)
        workspace_repository.workspaces[workspace.id] = workspace
        add_member(workspace_repository, workspace, user, WorkspaceRole.VIEWER)
        row = RetrievalSearchRow(
            document_id=uuid4(),
            document_name="Report.pdf",
            chunk_id=uuid4(),
            page_number=1,
            snippet="Relevant excerpt",
            score=0.82,
        )
        service, retrieval, provider = make_service(
            workspace_repository,
            FakeRetrievalRepository(rows=[row]),
        )

        response = await service.search_async(
            workspace.id,
            RetrievalSearchRequest(query="policy", topK=3),
            user,
        )

        assert isinstance(response, ApiResponse)
        assert response.data is not None
        assert response.data.results[0].document_id == row.document_id
        assert response.data.results[0].snippet == "Relevant excerpt"
        assert provider.calls == [["policy"]]
        assert retrieval.calls == [(workspace.id, [0.1, 0.2], 3)]

    asyncio.run(run_test())


def test_search_requires_active_workspace_member() -> None:
    async def run_test() -> None:
        user = make_user()
        workspace_repository = FakeWorkspaceRepository()
        service, _, _ = make_service(workspace_repository)

        with pytest.raises(NotFoundException):
            await service.search_async(
                uuid4(),
                RetrievalSearchRequest(query="policy"),
                user,
            )

    asyncio.run(run_test())


def test_search_rejects_inactive_user() -> None:
    async def run_test() -> None:
        user = make_user(is_active=False)
        workspace_repository = FakeWorkspaceRepository()
        workspace = make_workspace(user.id)
        workspace_repository.workspaces[workspace.id] = workspace
        add_member(workspace_repository, workspace, user, WorkspaceRole.ADMIN)
        service, _, _ = make_service(workspace_repository)

        with pytest.raises(ForbiddenException):
            await service.search_async(
                workspace.id,
                RetrievalSearchRequest(query="policy"),
                user,
            )

    asyncio.run(run_test())


def test_search_rejects_inactive_workspace() -> None:
    async def run_test() -> None:
        user = make_user()
        workspace_repository = FakeWorkspaceRepository()
        workspace = make_workspace(user.id, is_active=False)
        workspace_repository.workspaces[workspace.id] = workspace
        add_member(workspace_repository, workspace, user, WorkspaceRole.ADMIN)
        service, _, _ = make_service(workspace_repository)

        with pytest.raises(NotFoundException):
            await service.search_async(
                workspace.id,
                RetrievalSearchRequest(query="policy"),
                user,
            )

    asyncio.run(run_test())


def test_search_rejects_invalid_embedding_response() -> None:
    async def run_test() -> None:
        user = make_user()
        workspace_repository = FakeWorkspaceRepository()
        workspace = make_workspace(user.id)
        workspace_repository.workspaces[workspace.id] = workspace
        add_member(workspace_repository, workspace, user, WorkspaceRole.MEMBER)
        service, retrieval, _ = make_service(
            workspace_repository,
            embedding_provider=FakeEmbeddingProvider(vectors=[]),
        )

        with pytest.raises(ExternalProviderException):
            await service.search_async(
                workspace.id,
                RetrievalSearchRequest(query="policy"),
                user,
            )

        assert retrieval.calls == []

    asyncio.run(run_test())


def test_retrieval_service_does_not_expose_vectors_or_full_content() -> None:
    async def run_test() -> None:
        user = make_user()
        workspace_repository = FakeWorkspaceRepository()
        workspace = make_workspace(user.id)
        workspace_repository.workspaces[workspace.id] = workspace
        add_member(workspace_repository, workspace, user, WorkspaceRole.MEMBER)
        row = RetrievalSearchRow(
            document_id=uuid4(),
            document_name="Report.pdf",
            chunk_id=uuid4(),
            page_number=None,
            snippet="Short excerpt",
            score=0.8,
        )
        service, _, _ = make_service(
            workspace_repository,
            FakeRetrievalRepository(rows=[row]),
        )

        response = await service.search_async(
            workspace.id,
            RetrievalSearchRequest(query="policy"),
            user,
        )

        payload = response.model_dump(by_alias=True)
        assert "embedding" not in str(payload)
        assert "vector" not in str(payload)
        assert "full content" not in str(payload)

    asyncio.run(run_test())
