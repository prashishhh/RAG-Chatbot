from app.modules.workspaces.models import Workspace, WorkspaceMember, WorkspaceRole


def test_workspace_has_required_security_constraints() -> None:
    constraint_names = {constraint.name for constraint in Workspace.__table__.constraints}
    index_names = {index.name for index in Workspace.__table__.indexes}

    assert "uq_workspaces_slug" in constraint_names
    assert "ix_workspaces_slug" in index_names
    assert "ix_workspaces_created_by_user_id" in index_names
    assert Workspace.__table__.c.created_by_user_id.nullable is False


def test_workspace_member_has_tenant_isolation_constraints() -> None:
    constraint_names = {constraint.name for constraint in WorkspaceMember.__table__.constraints}
    index_names = {index.name for index in WorkspaceMember.__table__.indexes}

    assert "uq_workspace_members_workspace_user" in constraint_names
    assert "ck_workspace_members_role" in constraint_names
    assert "ix_workspace_members_workspace_id" in index_names
    assert "ix_workspace_members_user_id" in index_names
    assert WorkspaceMember.__table__.c.workspace_id.nullable is False
    assert WorkspaceMember.__table__.c.user_id.nullable is False
    assert WorkspaceMember.__table__.c.created_at.nullable is False


def test_workspace_roles_are_explicit() -> None:
    assert {role.value for role in WorkspaceRole} == {"Owner", "Admin", "Member", "Viewer"}
