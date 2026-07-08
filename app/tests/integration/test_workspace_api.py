from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.exceptions import (
    BusinessRuleException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
)
from app.core.responses import ApiResponse
from app.main import app
from app.modules.auth.dependencies import get_auth_repository
from app.modules.auth.models import User
from app.modules.auth.security import create_access_token
from app.modules.workspaces.dependencies import get_workspace_service
from app.modules.workspaces.models import WorkspaceRole
from app.modules.workspaces.schemas import (
    WorkspaceListItemResponse,
    WorkspaceMemberListItemResponse,
    WorkspaceMemberResponse,
    WorkspaceResponse,
)
from app.tests.conftest import auth_settings


class FakeAuthRepository:
    def __init__(self, user: User | None) -> None:
        self.user = user

    async def get_user_by_id(self, user_id):
        if self.user is not None and self.user.id == user_id:
            return self.user
        return None


class FakeWorkspaceService:
    def __init__(self) -> None:
        self.workspace_id = uuid4()
        self.member_user_id = uuid4()

    async def create_async(self, request, current_user):
        if request.name == "Duplicate":
            raise ConflictException("A workspace with this name already exists.")
        return ApiResponse.success_response(
            message="Workspace created successfully.",
            data=_workspace_response(self.workspace_id, request.name, WorkspaceRole.OWNER),
        )

    async def list_async(self, current_user):
        return ApiResponse.success_response(
            message="Workspaces retrieved successfully.",
            data=[
                WorkspaceListItemResponse(
                    workspaceId=self.workspace_id,
                    name="Acme Inc",
                    slug="acme-inc",
                    currentUserRole=WorkspaceRole.OWNER,
                    isActive=True,
                    createdAt=datetime(2026, 7, 8, tzinfo=UTC),
                )
            ],
        )

    async def get_by_id_async(self, workspace_id, current_user):
        if workspace_id != self.workspace_id:
            raise NotFoundException("Workspace not found.")
        return ApiResponse.success_response(
            message="Workspace retrieved successfully.",
            data=_workspace_response(workspace_id, "Acme Inc", WorkspaceRole.OWNER),
        )

    async def update_async(self, workspace_id, request, current_user):
        if request.name == "Forbidden":
            raise ForbiddenException("You do not have permission to manage this workspace.")
        return ApiResponse.success_response(
            message="Workspace updated successfully.",
            data=_workspace_response(workspace_id, request.name, WorkspaceRole.ADMIN),
        )

    async def archive_async(self, workspace_id, current_user):
        return ApiResponse.success_response(
            message="Workspace archived successfully.",
            data=None,
        )

    async def list_members_async(self, workspace_id, current_user):
        if workspace_id != self.workspace_id:
            raise NotFoundException("Workspace not found.")
        return ApiResponse.success_response(
            message="Workspace members retrieved successfully.",
            data=[
                WorkspaceMemberListItemResponse(
                    userId=self.member_user_id,
                    fullName="Sita Sharma",
                    email="sita@example.com",
                    role=WorkspaceRole.MEMBER,
                    joinedAt=datetime(2026, 7, 8, tzinfo=UTC),
                )
            ],
        )

    async def add_member_async(self, workspace_id, request, current_user):
        if request.email == "exists@example.com":
            raise ConflictException("User is already a workspace member.")
        if request.role == WorkspaceRole.OWNER:
            raise ForbiddenException("You do not have permission to manage this workspace.")
        return ApiResponse.success_response(
            message="Workspace member added successfully.",
            data=_member_response(workspace_id, self.member_user_id, request.email, request.role),
        )

    async def update_member_role_async(self, workspace_id, user_id, request, current_user):
        if user_id != self.member_user_id:
            raise NotFoundException("Workspace member not found.")
        if request.role == WorkspaceRole.OWNER:
            raise ForbiddenException("You do not have permission to manage this workspace.")
        return ApiResponse.success_response(
            message="Member role updated successfully.",
            data=_member_response(workspace_id, user_id, "sita@example.com", request.role),
        )

    async def remove_member_async(self, workspace_id, user_id, current_user):
        if user_id != self.member_user_id:
            raise NotFoundException("Workspace member not found.")
        if user_id == current_user.id:
            raise BusinessRuleException("Workspace must have at least one owner.")
        return ApiResponse.success_response(
            message="Workspace member removed successfully.",
            data=None,
        )


def _workspace_response(workspace_id, name: str, role: WorkspaceRole) -> WorkspaceResponse:
    return WorkspaceResponse(
        workspaceId=workspace_id,
        name=name,
        slug=name.lower().replace(" ", "-"),
        description=None,
        currentUserRole=role,
        isActive=True,
        createdAt=datetime(2026, 7, 8, tzinfo=UTC),
        updatedAt=datetime(2026, 7, 8, tzinfo=UTC),
    )


def _member_response(
    workspace_id,
    user_id,
    email: str,
    role: WorkspaceRole,
) -> WorkspaceMemberResponse:
    return WorkspaceMemberResponse(
        workspaceId=workspace_id,
        userId=user_id,
        fullName="Sita Sharma",
        email=email,
        role=role,
        joinedAt=datetime(2026, 7, 8, tzinfo=UTC),
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
    app.dependency_overrides[get_workspace_service] = FakeWorkspaceService
    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


def test_create_workspace_success_returns_201_standard_response() -> None:
    response = authenticated_client().post("/api/v1/workspaces", json={"name": "Acme Inc"})

    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Workspace created successfully."
    assert body["data"]["name"] == "Acme Inc"
    assert body["data"]["currentUserRole"] == "Owner"
    assert "memberId" not in body["data"]


def test_workspace_routes_require_authentication() -> None:
    app.dependency_overrides[get_workspace_service] = FakeWorkspaceService
    client = TestClient(app)

    response = client.get("/api/v1/workspaces")

    assert response.status_code == 401


def test_workspace_routes_reject_inactive_user() -> None:
    response = authenticated_client(make_user(is_active=False)).get("/api/v1/workspaces")

    assert response.status_code == 403
    assert response.json()["message"] == "User account is inactive."


def test_duplicate_workspace_rejected_without_internal_details() -> None:
    response = authenticated_client().post("/api/v1/workspaces", json={"name": "Duplicate"})

    assert response.status_code == 409
    body = response.json()
    assert body["success"] is False
    assert body["data"] is None
    assert "traceback" not in str(body).lower()


def test_list_workspaces_returns_current_user_workspaces() -> None:
    response = authenticated_client().get("/api/v1/workspaces")

    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) == 1
    assert body["data"][0]["currentUserRole"] == "Owner"


def test_get_workspace_hides_missing_workspace() -> None:
    response = authenticated_client().get(f"/api/v1/workspaces/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["message"] == "Workspace not found."


def test_update_workspace_rejects_non_management_role() -> None:
    client = authenticated_client()
    service = FakeWorkspaceService()
    app.dependency_overrides[get_workspace_service] = lambda: service

    response = client.patch(
        f"/api/v1/workspaces/{service.workspace_id}",
        json={"name": "Forbidden"},
    )

    assert response.status_code == 403


def test_archive_workspace_success() -> None:
    service = FakeWorkspaceService()
    client = authenticated_client()
    app.dependency_overrides[get_workspace_service] = lambda: service

    response = client.delete(f"/api/v1/workspaces/{service.workspace_id}")

    assert response.status_code == 200
    assert response.json()["message"] == "Workspace archived successfully."


def test_list_workspace_members_success() -> None:
    service = FakeWorkspaceService()
    client = authenticated_client()
    app.dependency_overrides[get_workspace_service] = lambda: service

    response = client.get(f"/api/v1/workspaces/{service.workspace_id}/members")

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Workspace members retrieved successfully."
    assert body["data"][0]["email"] == "sita@example.com"
    assert "passwordHash" not in body["data"][0]


def test_add_workspace_member_success_returns_201() -> None:
    service = FakeWorkspaceService()
    client = authenticated_client()
    app.dependency_overrides[get_workspace_service] = lambda: service

    response = client.post(
        f"/api/v1/workspaces/{service.workspace_id}/members",
        json={"email": "sita@example.com", "role": "Member"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["message"] == "Workspace member added successfully."
    assert body["data"]["role"] == "Member"


def test_add_workspace_member_rejects_duplicate_member() -> None:
    service = FakeWorkspaceService()
    client = authenticated_client()
    app.dependency_overrides[get_workspace_service] = lambda: service

    response = client.post(
        f"/api/v1/workspaces/{service.workspace_id}/members",
        json={"email": "exists@example.com", "role": "Member"},
    )

    assert response.status_code == 409


def test_add_workspace_member_rejects_invalid_role() -> None:
    service = FakeWorkspaceService()
    client = authenticated_client()
    app.dependency_overrides[get_workspace_service] = lambda: service

    response = client.post(
        f"/api/v1/workspaces/{service.workspace_id}/members",
        json={"email": "sita@example.com", "role": "SuperAdmin"},
    )

    assert response.status_code == 422


def test_update_workspace_member_role_rejects_forbidden_owner_change() -> None:
    service = FakeWorkspaceService()
    client = authenticated_client()
    app.dependency_overrides[get_workspace_service] = lambda: service

    response = client.patch(
        f"/api/v1/workspaces/{service.workspace_id}/members/{service.member_user_id}/role",
        json={"role": "Owner"},
    )

    assert response.status_code == 403


def test_update_workspace_member_role_hides_missing_member() -> None:
    service = FakeWorkspaceService()
    client = authenticated_client()
    app.dependency_overrides[get_workspace_service] = lambda: service

    response = client.patch(
        f"/api/v1/workspaces/{service.workspace_id}/members/{uuid4()}/role",
        json={"role": "Viewer"},
    )

    assert response.status_code == 404


def test_update_workspace_member_role_success() -> None:
    service = FakeWorkspaceService()
    client = authenticated_client()
    app.dependency_overrides[get_workspace_service] = lambda: service

    response = client.patch(
        f"/api/v1/workspaces/{service.workspace_id}/members/{service.member_user_id}/role",
        json={"role": "Viewer"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["role"] == "Viewer"


def test_remove_workspace_member_hides_missing_member() -> None:
    service = FakeWorkspaceService()
    client = authenticated_client()
    app.dependency_overrides[get_workspace_service] = lambda: service

    response = client.delete(f"/api/v1/workspaces/{service.workspace_id}/members/{uuid4()}")

    assert response.status_code == 404


def test_remove_workspace_member_success() -> None:
    service = FakeWorkspaceService()
    client = authenticated_client()
    app.dependency_overrides[get_workspace_service] = lambda: service

    response = client.delete(
        f"/api/v1/workspaces/{service.workspace_id}/members/{service.member_user_id}"
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Workspace member removed successfully."
