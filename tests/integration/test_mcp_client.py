"""Integration tests for EnterpriseMCPClient."""

import pytest

from app.auth.models import UserContext
from app.mcp.client import EnterpriseMCPClient


@pytest.mark.asyncio
async def test_mcp_client_tool_discovery_filtering(
    analyst_context: UserContext, viewer_context: UserContext
) -> None:
    """Test that MCPClient list_tools respects user permissions."""
    client_analyst = EnterpriseMCPClient(token=analyst_context.token or "")
    tools_analyst = await client_analyst.list_tools()
    analyst_names = [t["name"] for t in tools_analyst]
    assert "query_database" in analyst_names
    assert "get_invoice" in analyst_names

    client_viewer = EnterpriseMCPClient(token=viewer_context.token or "")
    tools_viewer = await client_viewer.list_tools()
    viewer_names = [t["name"] for t in tools_viewer]
    assert "search_documents" in viewer_names
    assert "query_database" not in viewer_names


@pytest.mark.asyncio
async def test_mcp_client_call_tool_denied(viewer_context: UserContext) -> None:
    """Test that unauthorized tool call through MCPClient returns structured AUTHORIZATION_FAILED error."""
    client_viewer = EnterpriseMCPClient(token=viewer_context.token or "")
    result = await client_viewer.call_tool("query_database", {"query": "SELECT 1"})
    assert result.get("error") == "AUTHORIZATION_FAILED"
    assert "lacks required permission" in result.get("message", "")
