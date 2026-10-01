"""Integration tests for EnterpriseMCPServer adhering to Model Context Protocol."""

import pytest

from app.auth.models import UserContext
from app.mcp.server import EnterpriseMCPServer, current_mcp_user_ctx


@pytest.mark.asyncio
async def test_mcp_server_lists_all_tools() -> None:
    """Verify that MCPServer exposes tools via MCP list_tools protocol."""
    server = EnterpriseMCPServer()
    tools = await server.mcp.list_tools()
    tool_names = [t.name for t in tools]

    assert "query_database" in tool_names
    assert "search_documents" in tool_names
    assert "get_customer" in tool_names
    assert "get_invoice" in tool_names
    assert "get_order" in tool_names
    assert "get_system_status" in tool_names
    assert "calculate_kpi" in tool_names


@pytest.mark.asyncio
async def test_mcp_server_call_tool_authorized(analyst_context: UserContext) -> None:
    """Verify executing tool through MCPServer protocol with ambient auth context."""
    server = EnterpriseMCPServer()
    token = current_mcp_user_ctx.set(analyst_context)
    try:
        call_res = await server.mcp.call_tool("calculate_kpi", {"metric_name": "revenue"})
        assert call_res is not None
        assert getattr(call_res, "is_error", False) is False
    finally:
        current_mcp_user_ctx.reset(token)
