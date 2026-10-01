"""Unit tests for tool registration, discovery, and policy checks."""

import pytest

from app.auth.models import UserContext
from app.core.errors import AuthorizationError, ToolNotFoundError
from app.mcp.registry import ToolRegistry, create_default_registry
from app.tools.customer import CustomerTool
from app.tools.database import DatabaseQueryTool


def test_registry_registration_and_lookup() -> None:
    """Test registering and retrieving tools."""
    registry = ToolRegistry()
    tool = DatabaseQueryTool()
    registry.register_tool(tool)

    assert registry.get_tool("query_database") is tool

    with pytest.raises(ToolNotFoundError):
        registry.get_tool("non_existent_tool")


def test_registry_unregistration() -> None:
    """Test unregistering a tool."""
    registry = ToolRegistry()
    tool = CustomerTool()
    registry.register_tool(tool)
    assert registry.get_tool("get_customer") is tool

    registry.unregister_tool("get_customer")
    with pytest.raises(ToolNotFoundError):
        registry.get_tool("get_customer")


def test_registry_authorization_check() -> None:
    """Test authorize_tool strictly enforces permissions."""
    registry = ToolRegistry()
    db_tool = DatabaseQueryTool()
    registry.register_tool(db_tool)

    user_with_perm = UserContext(
        user_id="u1", username="bob", roles=["analyst"], permissions=["database.read"]
    )
    user_without_perm = UserContext(
        user_id="u2", username="charlie", roles=["viewer"], permissions=["documents.search"]
    )

    # Authorized user passes
    registry.authorize_tool(db_tool, user_with_perm)

    # Unauthorized user raises AuthorizationError
    with pytest.raises(AuthorizationError) as exc_info:
        registry.authorize_tool(db_tool, user_without_perm)
    assert exc_info.value.code.value == "AUTHORIZATION_FAILED"


def test_registry_list_tools_filtering() -> None:
    """Test list_tools returns only authorized tools for a given user context."""
    registry = create_default_registry()

    viewer = UserContext(
        user_id="u3",
        username="dave",
        roles=["viewer"],
        permissions=["documents.search", "system.status"],
    )
    discovered = registry.list_tools(user_context=viewer)

    names = [t.name for t in discovered]
    assert "search_documents" in names
    assert "get_system_status" in names
    assert "query_database" not in names
    assert "get_invoice" not in names
