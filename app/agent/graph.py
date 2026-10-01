"""LangGraph agent workflow integrating MCP tool discovery, planning, authorization, and execution."""

import json
import uuid
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from app.agent.llm import get_llm
from app.agent.state import AgentState
from app.core.logging import logger
from app.mcp.client import EnterpriseMCPClient


async def discover_tools_node(state: AgentState) -> dict[str, Any]:
    """Node 1: Discover available tools from the MCP Gateway based on user permissions."""
    client = EnterpriseMCPClient(token=state["auth_token"], agent_id=state["agent_id"])
    discovered = await client.list_tools()
    logger.info(
        "Agent %s discovered %d authorized tools via MCP", state["agent_id"], len(discovered)
    )
    return {
        "discovered_tools": discovered,
        "status": "tools_discovered",
    }


async def planner_node(state: AgentState) -> dict[str, Any]:
    """Node 2: Plan actions and dynamically select MCP tool(s) based on user intent."""
    llm = get_llm()
    discovered_tools = state.get("discovered_tools", [])
    user_query = state["user_query"]

    # Format tool descriptions and schemas for LLM reasoning
    tools_summary = [
        {
            "name": t["name"],
            "description": t["description"],
            "input_schema": t.get("input_schema", {}),
        }
        for t in discovered_tools
    ]

    system_prompt = (
        "You are an Enterprise AI Agent operating within a secure MCP Tool Gateway architecture.\n"
        "Your task is to analyze the user request and select the most appropriate tool to answer it.\n"
        "Available discovered tools:\n"
        f"{json.dumps(tools_summary, indent=2)}\n\n"
        "Respond ONLY in valid JSON format with the following structure:\n"
        "{\n"
        '  "plan": "Detailed explanation of your reasoning",\n'
        '  "tool_calls": [{"name": "tool_name", "arguments": {"param1": "val1"}}]\n'
        "}\n"
        "If no tool is needed or user request cannot be fulfilled by available tools, return:\n"
        '{"plan": "No tool needed", "tool_calls": []}'
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_query),
    ]

    response = await llm.ainvoke(messages)
    content = str(response.content).strip()

    plan = "Execute planned tool"
    selected_tools: list[dict[str, Any]] = []

    try:
        # Try to parse JSON from LLM response
        json_match = content
        if "```json" in content:
            json_match = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            json_match = content.split("```")[1].split("```")[0].strip()

        parsed = json.loads(json_match)
        plan = parsed.get("plan", plan)
        selected_tools = parsed.get("tool_calls", [])
    except Exception as e:
        logger.warning(
            "Could not parse structured JSON from planner: %s. Raw content: %s", e, content
        )
        # Fallback to direct text if no tool calls parsed
        plan = content

    return {
        "plan": plan,
        "selected_tools": selected_tools,
        "messages": [AIMessage(content=f"Plan: {plan}")],
        "status": "planned",
    }


def should_execute_tools(state: AgentState) -> str:
    """Conditional router deciding whether to execute tools or jump straight to synthesis."""
    if state.get("selected_tools"):
        return "execute_mcp_tools"
    return "synthesize_answer"


async def execute_mcp_tools_node(state: AgentState) -> dict[str, Any]:
    """Node 3: Execute selected tools strictly through the Enterprise MCP Gateway."""
    client = EnterpriseMCPClient(token=state["auth_token"], agent_id=state["agent_id"])
    selected_tools = state.get("selected_tools", [])
    results: list[dict[str, Any]] = []
    has_error = False
    error_msg = None

    for tool_call in selected_tools:
        name = str(tool_call.get("name", ""))
        if not name:
            continue
        args = tool_call.get("arguments", {})
        logger.info("Agent %s invoking MCP tool '%s' with args %s", state["agent_id"], name, args)

        result = await client.call_tool(name=name, arguments=args)
        results.append({"tool": name, "arguments": args, "result": result})

        if isinstance(result, dict) and "error" in result:
            has_error = True
            error_msg = result.get("message", result.get("error"))

    return {
        "tool_results": results,
        "execution_error": error_msg if has_error else None,
        "status": "tools_executed",
    }


async def synthesizer_node(state: AgentState) -> dict[str, Any]:
    """Node 4: Synthesize final enterprise response from tool outputs or explain access denial."""
    llm = get_llm()
    user_query = state["user_query"]
    tool_results = state.get("tool_results", [])
    error = state.get("execution_error")

    if error:
        final_answer = (
            f"### Action Restricted\n\n"
            f"The requested enterprise tool operation could not be completed:\n\n"
            f"**Error Details**: `{error}`\n\n"
            f"Please verify your role permissions with your enterprise administrator."
        )
    elif tool_results:
        summary_prompt = (
            "You are an Enterprise AI Analytics Copilot.\n"
            f"User Query: {user_query}\n"
            f"TOOL_RESULTS:\n{json.dumps(tool_results, indent=2, default=str)}\n\n"
            "Provide a clear, professional, executive-level summary answering the user query based on the data above. "
            "Highlight key numbers, metrics, or findings accurately."
        )
        response = await llm.ainvoke([HumanMessage(content=summary_prompt)])
        final_answer = str(response.content)
    else:
        conversational_prompt = (
            "You are an Enterprise AI Analytics Copilot powered by a secure Model Context Protocol (MCP) Tool Gateway.\n"
            f"User Query: {user_query}\n"
            f"Planner Analysis: {state.get('plan')}\n\n"
            "Respond politely and professionally as an Enterprise AI Copilot. "
            "If the user is greeting or asking for help, introduce yourself and explain what you can do (database queries, customer data, invoices, policy document search, and KPI calculations). "
            "Invite them to ask an analytical or business question."
        )
        response = await llm.ainvoke([HumanMessage(content=conversational_prompt)])
        final_answer = str(response.content)

    return {
        "final_response": final_answer,
        "messages": [AIMessage(content=final_answer)],
        "status": "completed",
    }


def build_enterprise_agent_graph() -> Any:
    """Build and compile the LangGraph enterprise agent workflow."""
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("discover_tools", discover_tools_node)
    workflow.add_node("plan_and_select", planner_node)
    workflow.add_node("execute_mcp_tools", execute_mcp_tools_node)
    workflow.add_node("synthesize_answer", synthesizer_node)

    # Add edges
    workflow.add_edge(START, "discover_tools")
    workflow.add_edge("discover_tools", "plan_and_select")
    workflow.add_conditional_edges(
        "plan_and_select",
        should_execute_tools,
        {
            "execute_mcp_tools": "execute_mcp_tools",
            "synthesize_answer": "synthesize_answer",
        },
    )
    workflow.add_edge("execute_mcp_tools", "synthesize_answer")
    workflow.add_edge("synthesize_answer", END)

    return workflow.compile()


class EnterpriseAgent:
    """High-level AI Agent interface orchestrating LangGraph and MCP Gateway."""

    def __init__(self) -> None:
        self.graph = build_enterprise_agent_graph()

    async def run(self, query: str, auth_token: str, agent_id: str | None = None) -> dict[str, Any]:
        """Execute agent workflow for a given user query and JWT token."""
        aid = agent_id or f"copilot-{uuid.uuid4().hex[:6]}"
        initial_state: AgentState = {
            "user_query": query,
            "auth_token": auth_token,
            "agent_id": aid,
            "messages": [HumanMessage(content=query)],
            "discovered_tools": [],
            "plan": None,
            "selected_tools": [],
            "tool_results": [],
            "final_response": None,
            "status": "initiated",
            "execution_error": None,
        }

        final_state = await self.graph.ainvoke(initial_state)
        return {
            "query": query,
            "agent_id": aid,
            "final_response": final_state.get("final_response"),
            "plan": final_state.get("plan"),
            "selected_tools": final_state.get("selected_tools"),
            "tool_results": final_state.get("tool_results"),
            "status": final_state.get("status"),
            "execution_error": final_state.get("execution_error"),
        }
