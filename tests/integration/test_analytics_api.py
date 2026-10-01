"""Integration tests for Analytics and Observability API endpoints."""

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import UserContext
from app.database.session import get_db
from app.main import app
from app.services.token_tracker import record_llm_usage


@pytest.mark.asyncio
async def test_analytics_dashboard_endpoint(
    db_session: AsyncSession, analyst_context: UserContext
) -> None:
    """Test GET /analytics/dashboard returns full operational metrics and trends."""
    app.dependency_overrides[get_db] = lambda: db_session

    # Seed an LLM usage record
    await record_llm_usage(
        request_id="req-dash-1",
        user_id=analyst_context.user_id,
        agent_id="copilot",
        model="gpt-4o-mini",
        input_tokens=1000,
        output_tokens=250,
        latency_ms=180.0,
        session=db_session,
    )
    await db_session.commit()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/analytics/dashboard",
            headers={"Authorization": f"Bearer {analyst_context.token}"},
        )
        assert resp.status_code == 200
        data = resp.json()

        assert "total_tool_calls" in data
        assert "successful_tool_calls" in data
        assert "failed_tool_calls" in data
        assert "active_tools" in data
        assert "total_tokens_used" in data
        assert data["total_tokens_used"] >= 1250
        assert "estimated_llm_cost" in data
        assert "tool_usage_counts" in data
        assert "tool_execution_trend" in data
        assert "status_breakdown" in data
        assert "latency_by_tool" in data
        assert "token_usage_trend" in data

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_analytics_user_usage_endpoint(
    db_session: AsyncSession, analyst_context: UserContext
) -> None:
    """Test GET /analytics/user-usage returns user quota and consumption details."""
    app.dependency_overrides[get_db] = lambda: db_session

    await record_llm_usage(
        request_id="req-user-1",
        user_id=analyst_context.user_id,
        agent_id="copilot",
        model="gpt-4o-mini",
        input_tokens=400,
        output_tokens=100,
        latency_ms=90.0,
        session=db_session,
    )
    await db_session.commit()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/analytics/user-usage",
            headers={"Authorization": f"Bearer {analyst_context.token}"},
        )
        assert resp.status_code == 200
        data = resp.json()

        assert data["user_id"] == analyst_context.user_id
        assert data["today_tokens"] >= 500
        assert "daily_limit" in data
        assert "tokens_remaining" in data
        assert "is_warning" in data
        assert "is_exceeded" in data
        assert "usage_by_model" in data
        assert "daily_history" in data

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_analytics_tool_stats_endpoint(
    db_session: AsyncSession, analyst_context: UserContext
) -> None:
    """Test GET /analytics/tool-stats returns all registered MCP tools with schema and telemetry."""
    app.dependency_overrides[get_db] = lambda: db_session

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/analytics/tool-stats",
            headers={"Authorization": f"Bearer {analyst_context.token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        tool_names = [t["name"] for t in data]
        assert "query_database" in tool_names
        assert "search_documents" in tool_names

        for item in data:
            assert "name" in item
            assert "description" in item
            assert "execution_count" in item
            assert "avg_latency_ms" in item
            assert "success_rate" in item
            assert "risk_level" in item
            assert "input_schema" in item

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_analytics_executions_filter_endpoint(
    db_session: AsyncSession, admin_context: UserContext
) -> None:
    """Test GET /analytics/executions returns filterable execution history."""
    app.dependency_overrides[get_db] = lambda: db_session

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/analytics/executions?limit=10",
            headers={"Authorization": f"Bearer {admin_context.token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    app.dependency_overrides.clear()
