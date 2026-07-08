from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.modules.workspaces.models import WorkspaceRole


class CreateWorkspaceRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=500)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        name = value.strip()
        if not name:
            raise ValueError("Workspace name is required.")
        return name

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        description = value.strip()
        return description or None


class UpdateWorkspaceRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=500)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        name = value.strip()
        if not name:
            raise ValueError("Workspace name is required.")
        return name

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        description = value.strip()
        return description or None

    @model_validator(mode="after")
    def validate_has_update(self) -> "UpdateWorkspaceRequest":
        if self.name is None and self.description is None:
            raise ValueError("At least one workspace field must be provided.")
        return self


class WorkspaceResponse(BaseModel):
    workspace_id: UUID = Field(alias="workspaceId")
    name: str
    slug: str
    description: str | None = None
    current_user_role: WorkspaceRole = Field(alias="currentUserRole")
    is_active: bool = Field(alias="isActive")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True)


class WorkspaceListItemResponse(BaseModel):
    workspace_id: UUID = Field(alias="workspaceId")
    name: str
    slug: str
    current_user_role: WorkspaceRole = Field(alias="currentUserRole")
    is_active: bool = Field(alias="isActive")
    created_at: datetime = Field(alias="createdAt")

    model_config = ConfigDict(populate_by_name=True)


class AddWorkspaceMemberRequest(BaseModel):
    email: EmailStr
    role: WorkspaceRole


class UpdateWorkspaceMemberRoleRequest(BaseModel):
    role: WorkspaceRole


class WorkspaceMemberResponse(BaseModel):
    workspace_id: UUID = Field(alias="workspaceId")
    user_id: UUID = Field(alias="userId")
    full_name: str = Field(alias="fullName")
    email: EmailStr
    role: WorkspaceRole
    joined_at: datetime = Field(alias="joinedAt")

    model_config = ConfigDict(populate_by_name=True)


class WorkspaceMemberListItemResponse(BaseModel):
    user_id: UUID = Field(alias="userId")
    full_name: str = Field(alias="fullName")
    email: EmailStr
    role: WorkspaceRole
    joined_at: datetime = Field(alias="joinedAt")

    model_config = ConfigDict(populate_by_name=True)
