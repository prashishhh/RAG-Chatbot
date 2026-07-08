from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.workspaces.models import WorkspaceRole
from app.modules.workspaces.schemas import (
    AddWorkspaceMemberRequest,
    CreateWorkspaceRequest,
    UpdateWorkspaceMemberRoleRequest,
    UpdateWorkspaceRequest,
    WorkspaceListItemResponse,
    WorkspaceMemberListItemResponse,
    WorkspaceMemberResponse,
    WorkspaceResponse,
)


def test_create_workspace_request_trims_safe_fields() -> None:
    request = CreateWorkspaceRequest(name="  Acme Inc  ", description="  Internal docs  ")

    assert request.name == "Acme Inc"
    assert request.description == "Internal docs"


def test_create_workspace_request_rejects_blank_name() -> None:
    with pytest.raises(ValidationError, match="Workspace name is required"):
        CreateWorkspaceRequest(name="  ")


def test_update_workspace_request_requires_a_change() -> None:
    with pytest.raises(ValidationError, match="At least one workspace field"):
        UpdateWorkspaceRequest()


def test_workspace_response_exposes_only_api_safe_fields() -> None:
    response = WorkspaceResponse(
        workspaceId=uuid4(),
        name="Acme Inc",
        slug="acme-inc",
        description=None,
        currentUserRole=WorkspaceRole.OWNER,
        isActive=True,
        createdAt=datetime.now(UTC),
        updatedAt=datetime.now(UTC),
    )

    payload = response.model_dump(by_alias=True)

    assert "workspaceId" in payload
    assert payload["currentUserRole"] == WorkspaceRole.OWNER
    assert "id" not in payload
    assert "memberId" not in payload
    assert "createdByUserId" not in payload
    assert "workspaceMembers" not in payload


def test_workspace_list_item_does_not_expose_internal_membership_metadata() -> None:
    response = WorkspaceListItemResponse(
        workspaceId=uuid4(),
        name="Acme Inc",
        slug="acme-inc",
        currentUserRole=WorkspaceRole.ADMIN,
        isActive=True,
        createdAt=datetime.now(UTC),
    )

    payload = response.model_dump(by_alias=True)

    assert set(payload) == {
        "workspaceId",
        "name",
        "slug",
        "currentUserRole",
        "isActive",
        "createdAt",
    }


def test_add_workspace_member_request_accepts_email_and_role() -> None:
    request = AddWorkspaceMemberRequest(email="sita@example.com", role=WorkspaceRole.MEMBER)

    assert str(request.email) == "sita@example.com"
    assert request.role == WorkspaceRole.MEMBER


def test_add_workspace_member_request_rejects_invalid_role() -> None:
    with pytest.raises(ValidationError):
        AddWorkspaceMemberRequest(email="sita@example.com", role="SuperAdmin")


def test_update_workspace_member_role_request_uses_role_enum() -> None:
    request = UpdateWorkspaceMemberRoleRequest(role=WorkspaceRole.VIEWER)

    assert request.role == WorkspaceRole.VIEWER


def test_workspace_member_response_exposes_only_safe_user_fields() -> None:
    response = WorkspaceMemberResponse(
        workspaceId=uuid4(),
        userId=uuid4(),
        fullName="Sita Sharma",
        email="sita@example.com",
        role=WorkspaceRole.ADMIN,
        joinedAt=datetime.now(UTC),
    )

    payload = response.model_dump(by_alias=True)

    assert set(payload) == {
        "workspaceId",
        "userId",
        "fullName",
        "email",
        "role",
        "joinedAt",
    }
    assert "passwordHash" not in payload
    assert "isActive" not in payload
    assert "memberId" not in payload


def test_workspace_member_list_item_omits_workspace_and_internal_metadata() -> None:
    response = WorkspaceMemberListItemResponse(
        userId=uuid4(),
        fullName="Sita Sharma",
        email="sita@example.com",
        role=WorkspaceRole.VIEWER,
        joinedAt=datetime.now(UTC),
    )

    payload = response.model_dump(by_alias=True)

    assert set(payload) == {"userId", "fullName", "email", "role", "joinedAt"}
