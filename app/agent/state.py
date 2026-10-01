"""LangGraph typed agent state schema."""

import operator
from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    """Execution state passed through the LangGraph reasoning workflow."""

    user_query: str
    auth_token: str
    agent_id: str
    messages: Annotated[list[BaseMessage], operator.add]
    discovered_tools: list[dict[str, Any]]
    plan: str | None
    selected_tools: list[dict[str, Any]]
    tool_results: list[dict[str, Any]]
    final_response: str | None
    status: str
    execution_error: str | None
