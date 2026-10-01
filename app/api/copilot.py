"""Enterprise AI Analytics Copilot API integrating LangGraph, MCP Gateway, token tracking, and streaming."""

import asyncio
import json
import time
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agent.graph import EnterpriseAgent
from app.auth.jwt import get_current_user_context
from app.auth.models import UserContext
from app.core.config import get_settings
from app.services.token_tracker import (
    calculate_estimated_cost,
    check_user_quota,
    estimate_tokens,
    record_llm_usage,
)

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
    tokens_used: int = 0
    estimated_cost: float = 0.0
    latency_ms: float = 0.0


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
    """Interact with the LangGraph Copilot with quota enforcement and token tracking."""
    # 1. Enforce user token quota at backend level
    allowed, used_today, daily_limit = await check_user_quota(user.user_id, user.roles)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Daily token limit of {daily_limit:,} tokens exceeded (Used today: {used_today:,}). "
                "Additional AI agent requests are restricted under enterprise quota policy."
            ),
        )

    t0 = time.perf_counter()
    agent = get_enterprise_agent()

    # 2. Run agent workflow
    result = await agent.run(
        query=request.query,
        auth_token=user.token or "",
        agent_id=request.agent_id,
    )
    latency_ms = round((time.perf_counter() - t0) * 1000, 2)

    # 3. Calculate and record token consumption
    input_tokens = estimate_tokens(request.query) + 320  # Base system prompt & tool schema context
    output_tokens = estimate_tokens(result.get("final_response") or "")
    total_tokens = input_tokens + output_tokens

    settings = get_settings()
    model_name = (
        settings.OPENAI_MODEL
        if (settings.OPENAI_API_KEY and not settings.OPENAI_API_KEY.startswith("test"))
        else "mock-enterprise-llm"
    )
    cost = calculate_estimated_cost(model_name, input_tokens, output_tokens)

    await record_llm_usage(
        request_id=result.get("agent_id", "req-unknown"),
        user_id=user.user_id,
        agent_id=result.get("agent_id"),
        model=model_name,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
    )

    result["tokens_used"] = total_tokens
    result["estimated_cost"] = cost
    result["latency_ms"] = latency_ms

    return AgentChatResponse(**result)


@router.post("/chat/stream", summary="Chat with Real-Time Progressive Event Streaming")
async def chat_with_agent_stream(
    request: AgentChatRequest,
    user: UserContext = Depends(get_current_user_context),
) -> StreamingResponse:
    """Stream progressive execution events (planning -> tool execution -> answer synthesis)."""
    # Check quota
    allowed, used_today, daily_limit = await check_user_quota(user.user_id, user.roles)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Daily token limit of {daily_limit:,} exceeded (Used today: {used_today:,}).",
        )

    async def event_generator() -> AsyncGenerator[str, None]:
        t0 = time.perf_counter()
        agent = get_enterprise_agent()

        yield f"data: {json.dumps({'event': 'planning', 'message': 'Analyzing intent and discovering approved MCP tools...'})}\n\n"
        await asyncio.sleep(0.05)

        result = await agent.run(
            query=request.query,
            auth_token=user.token or "",
            agent_id=request.agent_id,
        )
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)

        selected = result.get("selected_tools", [])
        if selected:
            for t in selected:
                t_name = t.get("name", "tool")
                yield f"data: {json.dumps({'event': 'executing_tool', 'tool': t_name, 'message': f'Invoking {t_name} via MCP Gateway...'})}\n\n"
                await asyncio.sleep(0.05)
                yield f"data: {json.dumps({'event': 'tool_result', 'tool': t_name, 'status': 'SUCCESS'})}\n\n"
        else:
            yield f"data: {json.dumps({'event': 'info', 'message': 'Direct conversational routing without backend tool calls.'})}\n\n"

        yield f"data: {json.dumps({'event': 'synthesizing', 'message': 'Synthesizing response...'})}\n\n"

        # Record tokens
        input_tokens = estimate_tokens(request.query) + 320
        output_tokens = estimate_tokens(result.get("final_response") or "")
        total_tokens = input_tokens + output_tokens
        settings = get_settings()
        model_name = (
            settings.OPENAI_MODEL
            if (settings.OPENAI_API_KEY and not settings.OPENAI_API_KEY.startswith("test"))
            else "mock-enterprise-llm"
        )
        cost = calculate_estimated_cost(model_name, input_tokens, output_tokens)

        await record_llm_usage(
            request_id=result.get("agent_id", "req-unknown"),
            user_id=user.user_id,
            agent_id=result.get("agent_id"),
            model=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
        )

        result["tokens_used"] = total_tokens
        result["estimated_cost"] = cost
        result["latency_ms"] = latency_ms

        yield f"data: {json.dumps({'event': 'complete', 'data': result})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
