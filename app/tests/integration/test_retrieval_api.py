from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.exceptions import NotFoundException
from app.core.responses import ApiResponse
from app.main import app
from app.modules.auth.dependencies import get_auth_repository
from app.modules.auth.models import User
from app.modules.auth.security import create_access_token
from app.modules.retrieval.dependencies import get_retrieval_service
from app.modules.retrieval.schemas import RetrievalSearchResponse, RetrievalSearchResult
from app.tests.conftest import auth_settings


class FakeAuthRepository:
    def __init__(self, user: User | None) -> None:
        self.user = user

    async def get_user_by_id(self, user_id: UUID) -> User | None:
        if self.user is not None and self.user.id == user_id:
            return self.user
        return None


class FakeRetrievalService:
    def __init__(self) -> None:
        self.workspace_id = uuid4()
        self.missing_workspace_id = uuid4()

    async def search_async(self, workspace_id, request, current_user):
        if workspace_id == self.missing_workspace_id:
            raise NotFoundException("Workspace not found.")

        return ApiResponse.success_response(
            message="Retrieval search completed successfully.",
            data=RetrievalSearchResponse(
                results=[
                    RetrievalSearchResult(
                        documentId=uuid4(),
                        documentName="Report.pdf",
                        chunkId=uuid4(),
                        pageNumber=1,
                        snippet=f"Result for {request.query}",
                        score=0.82,
                    )
                ]
            ),
        )


def make_user(*, is_active: bool = True) -> User:
    return User(
        id=uuid4(),
        email="ram@example.com",
        full_name="Ram Sharma",
        password_hash="$argon2id$hash",  # noqa: S106
        is_active=is_active,
        is_verified=False,
    )


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def authenticated_client(user: User | None = None) -> TestClient:
    current_user = user or make_user()
    token = create_access_token(user_id=current_user.id, settings=auth_settings())
    app.dependency_overrides[get_auth_repository] = lambda: FakeAuthRepository(current_user)
    app.dependency_overrides[get_settings] = auth_settings
    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


def test_retrieval_search_requires_authentication() -> None:
    service = FakeRetrievalService()
    app.dependency_overrides[get_retrieval_service] = lambda: service
    client = TestClient(app)

    response = client.post(
        f"/api/v1/workspaces/{service.workspace_id}/retrieval/search",
        json={"query": "policy"},
    )

    assert response.status_code == 401


def test_retrieval_search_success_returns_safe_standard_response() -> None:
    service = FakeRetrievalService()
    client = authenticated_client()
    app.dependency_overrides[get_retrieval_service] = lambda: service

    response = client.post(
        f"/api/v1/workspaces/{service.workspace_id}/retrieval/search",
        json={"query": "policy", "topK": 3},
    )

    assert response.status_code == 200
    body = response.json()
    result = body["data"]["results"][0]
    assert body["message"] == "Retrieval search completed successfully."
    assert result["documentName"] == "Report.pdf"
    assert result["snippet"] == "Result for policy"
    assert result["score"] == 0.82
    assert "embedding" not in result
    assert "vector" not in result
    assert "objectKey" not in result
    assert "content" not in result


def test_retrieval_search_rejects_inactive_user() -> None:
    service = FakeRetrievalService()
    client = authenticated_client(make_user(is_active=False))
    app.dependency_overrides[get_retrieval_service] = lambda: service

    response = client.post(
        f"/api/v1/workspaces/{service.workspace_id}/retrieval/search",
        json={"query": "policy"},
    )

    assert response.status_code == 403
    assert response.json()["message"] == "User account is inactive."


def test_retrieval_search_validates_request() -> None:
    service = FakeRetrievalService()
    client = authenticated_client()
    app.dependency_overrides[get_retrieval_service] = lambda: service

    response = client.post(
        f"/api/v1/workspaces/{service.workspace_id}/retrieval/search",
        json={"query": "policy", "topK": 21},
    )

    assert response.status_code == 422
    assert response.json()["success"] is False


def test_retrieval_search_hides_missing_workspace() -> None:
    service = FakeRetrievalService()
    client = authenticated_client()
    app.dependency_overrides[get_retrieval_service] = lambda: service

    response = client.post(
        f"/api/v1/workspaces/{service.missing_workspace_id}/retrieval/search",
        json={"query": "policy"},
    )

    assert response.status_code == 404
    assert response.json()["message"] == "Workspace not found."
