"""Enterprise AI Analytics Copilot API integrating LangGraph and MCP Gateway."""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.agent.graph import EnterpriseAgent
from app.auth.jwt import get_current_user_context
from app.auth.models import UserContext

router = APIRouter(prefix="/agent", tags=["AI Analytics Copilot"])


class AgentChatRequest(BaseModel):
    """Payload for conversational interaction with Enterprise AI Agent."""

    query: str = Field(..., min_length=2, description="Natural language question or command")
    agent_id: str | None = Field(default=None, description="Optional custom agent identifier")


class AgentChatResponse(BaseModel):
    """Response containing synthesized answer, planner reasoning, and MCP tool traces."""

    query: str
    agent_id: str
    final_response: str | None
    plan: str | None
    selected_tools: list[dict[str, Any]]
    tool_results: list[dict[str, Any]]
    status: str
    execution_error: str | None = None


_agent_singleton: EnterpriseAgent | None = None


def get_enterprise_agent() -> EnterpriseAgent:
    """Get or create singleton instance of EnterpriseAgent."""
    global _agent_singleton
    if _agent_singleton is None:
        _agent_singleton = EnterpriseAgent()
    return _agent_singleton


@router.post("/chat", response_model=AgentChatResponse, summary="Chat with AI Analytics Copilot")
async def chat_with_agent(
    request: AgentChatRequest,
    user: UserContext = Depends(get_current_user_context),
) -> AgentChatResponse:
    """Interact with the LangGraph Copilot.

    The Copilot dynamically discovers and calls approved enterprise tools strictly via the MCP Gateway.
    All actions are audited, authorized against the calling user's permissions, and validated.
    """
    agent = get_enterprise_agent()
    # Propagate the user's authentic JWT token into the agent execution state
    result = await agent.run(
        query=request.query,
        auth_token=user.token or "",
        agent_id=request.agent_id,
    )
    return AgentChatResponse(**result)
