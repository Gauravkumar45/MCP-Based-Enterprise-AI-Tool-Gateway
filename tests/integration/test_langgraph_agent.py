"""Integration tests for LangGraph AI Agent executing tools via MCP."""

import pytest

from app.agent.graph import EnterpriseAgent
from app.auth.models import UserContext


@pytest.mark.asyncio
async def test_langgraph_agent_full_workflow(analyst_context: UserContext) -> None:
    """Test full LangGraph Agent workflow: user query -> planner -> discovery -> execution -> synthesis."""
    agent = EnterpriseAgent()
    query = "What were the top 5 customers by revenue last month?"

    result = await agent.run(query=query, auth_token=analyst_context.token or "")

    assert result["status"] == "completed"
    assert result["plan"] is not None
    assert len(result["selected_tools"]) >= 1
    assert result["selected_tools"][0]["name"] == "query_database"
    assert len(result["tool_results"]) >= 1
    assert result["final_response"] is not None
    assert "Executive Analytics Report" in result["final_response"]


@pytest.mark.asyncio
async def test_langgraph_agent_unauthorized_restriction(viewer_context: UserContext) -> None:
    """Test that LangGraph Agent gracefully handles and reports backend tool denial."""
    agent = EnterpriseAgent()
    query = "Show me the top 5 customers by revenue"

    result = await agent.run(query=query, auth_token=viewer_context.token or "")

    assert result["execution_error"] is not None
    assert "Action Restricted" in str(result["final_response"])
