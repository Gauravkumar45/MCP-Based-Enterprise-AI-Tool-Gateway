"""Unit tests for Role-Based Access Control (RBAC) and permission matrices."""

from app.auth.models import UserContext
from app.auth.permissions import DEFAULT_ROLE_PERMISSIONS, PermissionName, RoleName


def test_user_context_has_permission() -> None:
    """Test UserContext permission evaluation."""
    analyst = UserContext(
        user_id="u1",
        username="analyst_user",
        roles=["analyst"],
        permissions=["database.read", "customer.read"],
    )
    assert analyst.has_permission("database.read") is True
    assert analyst.has_permission("customer.read") is True
    assert analyst.has_permission("system.status") is False


def test_admin_role_bypass() -> None:
    """Test that users with the admin role inherently hold all permissions."""
    admin = UserContext(
        user_id="u0",
        username="admin_user",
        roles=["admin"],
        permissions=[],
    )
    assert admin.has_permission("database.read") is True
    assert admin.has_permission("any.arbitrary.permission") is True


def test_default_role_matrix_completeness() -> None:
    """Verify that all default roles have strictly defined permission lists."""
    for role_enum in RoleName:
        role_val = role_enum.value
        assert role_val in DEFAULT_ROLE_PERMISSIONS
        assert isinstance(DEFAULT_ROLE_PERMISSIONS[role_val], list)

    # Viewer role must not have database.read or invoice.read
    viewer_perms = DEFAULT_ROLE_PERMISSIONS[RoleName.VIEWER.value]
    assert PermissionName.DATABASE_READ.value not in viewer_perms
    assert PermissionName.INVOICE_READ.value not in viewer_perms
    assert PermissionName.DOCUMENTS_SEARCH.value in viewer_perms
