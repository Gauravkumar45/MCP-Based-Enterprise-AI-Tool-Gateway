"""Security tests for rate limit enforcement preventing brute force and denial of service."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import UserContext
from app.core.errors import RateLimitExceededError
from app.mcp.registry import ToolRegistry
from app.services.rate_limit import RateLimiter
from app.tools.kpi import CalculateKpiTool


@pytest.mark.asyncio
async def test_tool_rate_limit_flood_blocked(
    db_session: AsyncSession, analyst_context: UserContext
) -> None:
    """Security test: Rapid tool invocations exceeding configured window trigger TOOL_RATE_LIMITED."""
    limiter = RateLimiter(redis_client=None, max_requests=5, window_seconds=60)
    await limiter.reset(analyst_context.user_id, tool_name="calculate_kpi")

    registry = ToolRegistry(rate_limiter=limiter)
    registry.register_tool(CalculateKpiTool())

    # 5 allowed executions
    for _ in range(5):
        await registry.execute_tool(
            tool_name="calculate_kpi",
            arguments={"metric_name": "revenue"},
            user_context=analyst_context,
            session=db_session,
        )

    # 6th execution must be blocked with RateLimitExceededError
    with pytest.raises(RateLimitExceededError) as exc_info:
        await registry.execute_tool(
            tool_name="calculate_kpi",
            arguments={"metric_name": "revenue"},
            user_context=analyst_context,
            session=db_session,
        )

    assert exc_info.value.code.value == "TOOL_RATE_LIMITED"
    assert exc_info.value.status_code == 429
