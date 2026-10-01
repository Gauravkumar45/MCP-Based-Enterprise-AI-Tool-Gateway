"""Unit tests for LLM token usage tracking, cost estimation, and quota enforcement."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import LLMUsage
from app.services.token_tracker import (
    calculate_estimated_cost,
    check_user_quota,
    get_user_daily_token_usage,
    record_llm_usage,
)


def test_calculate_estimated_cost() -> None:
    """Verify accurate pricing calculation across model tiers."""
    # gpt-4o-mini: $0.15/1M input, $0.60/1M output
    cost_mini = calculate_estimated_cost(
        "gpt-4o-mini", input_tokens=1_000_000, output_tokens=1_000_000
    )
    assert cost_mini == pytest.approx(0.75, rel=1e-3)

    # gpt-4o: $2.50/1M input, $10.00/1M output
    cost_4o = calculate_estimated_cost("gpt-4o", input_tokens=10_000, output_tokens=5_000)
    # (10000 * 2.50 + 5000 * 10.00) / 1M = (0.025 + 0.050) = 0.075
    assert cost_4o == pytest.approx(0.075, rel=1e-3)

    # unknown model falls back to mock enterprise tier
    cost_unknown = calculate_estimated_cost("unknown-llm", input_tokens=1_000, output_tokens=1_000)
    assert cost_unknown > 0


@pytest.mark.asyncio
async def test_record_llm_usage_persistence(db_session: AsyncSession) -> None:
    """Verify that record_llm_usage persists valid usage data with cost calculations."""
    rec = await record_llm_usage(
        request_id="req-token-001",
        user_id="user-analyst-2",
        agent_id="enterprise-copilot-v1",
        model="gpt-4o-mini",
        input_tokens=1200,
        output_tokens=300,
        latency_ms=210.5,
        session=db_session,
    )
    await db_session.commit()

    assert rec.id is not None
    assert rec.total_tokens == 1500
    assert rec.estimated_cost > 0.0
    assert rec.latency_ms == 210.5

    # Query back
    stmt = select(LLMUsage).where(LLMUsage.request_id == "req-token-001")
    result = await db_session.execute(stmt)
    persisted = result.scalar_one_or_none()
    assert persisted is not None
    assert persisted.user_id == "user-analyst-2"
    assert persisted.total_tokens == 1500


@pytest.mark.asyncio
async def test_get_user_daily_token_usage(db_session: AsyncSession) -> None:
    """Verify user daily token calculation aggregates multiple invocations."""
    # Seed two usages for analyst
    await record_llm_usage(
        request_id="req-agg-1",
        user_id="user-analyst-2",
        agent_id="copilot",
        model="gpt-4o-mini",
        input_tokens=500,
        output_tokens=500,
        latency_ms=100.0,
        session=db_session,
    )
    await record_llm_usage(
        request_id="req-agg-2",
        user_id="user-analyst-2",
        agent_id="copilot",
        model="gpt-4o-mini",
        input_tokens=700,
        output_tokens=300,
        latency_ms=120.0,
        session=db_session,
    )
    await db_session.commit()

    today_usage = await get_user_daily_token_usage("user-analyst-2", session=db_session)
    assert today_usage >= 2000


@pytest.mark.asyncio
async def test_check_user_quota_limits(db_session: AsyncSession) -> None:
    """Verify quota checking returns appropriate warning flags and blocks excessive calls."""
    # Viewer limit is 25,000
    is_allowed, used, limit = await check_user_quota(
        user_id="user-viewer-new", roles=["viewer"], session=db_session
    )
    assert is_allowed is True
    assert used == 0
    assert limit == 25000

    # Seed heavy usage for viewer to exceed limit
    await record_llm_usage(
        request_id="req-heavy-1",
        user_id="user-viewer-heavy",
        agent_id="copilot",
        model="gpt-4o-mini",
        input_tokens=15_000,
        output_tokens=15_000,  # 30,000 > 25,000
        latency_ms=250.0,
        session=db_session,
    )
    await db_session.commit()

    is_allowed2, used2, limit2 = await check_user_quota(
        user_id="user-viewer-heavy", roles=["viewer"], session=db_session
    )
    assert is_allowed2 is False
    assert used2 == 30000
    assert limit2 == 25000
