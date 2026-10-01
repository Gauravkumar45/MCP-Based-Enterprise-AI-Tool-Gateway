"""Centralized LLM token usage tracking, cost calculation, and quota enforcement."""

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.database.models import LLMUsage
from app.database.session import session_scope

# Centralized pricing per 1 Million tokens (USD)
MODEL_PRICING: dict[str, dict[str, float]] = {
    "gpt-4o-mini": {"input_per_1m": 0.15, "output_per_1m": 0.60},
    "gpt-4o": {"input_per_1m": 2.50, "output_per_1m": 10.00},
    "gpt-3.5-turbo": {"input_per_1m": 0.50, "output_per_1m": 1.50},
    "mock-enterprise-llm": {"input_per_1m": 0.05, "output_per_1m": 0.15},
}

# Role-based daily token limits (configurable)
DEFAULT_ROLE_LIMITS: dict[str, int] = {
    "admin": 500_000,
    "analyst": 100_000,
    "viewer": 25_000,
    "agent": 250_000,
}
DEFAULT_DAILY_LIMIT = 50_000


def calculate_estimated_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate estimated cost in USD based on input and output token consumption."""
    pricing = MODEL_PRICING.get(
        model,
        MODEL_PRICING.get("mock-enterprise-llm", {"input_per_1m": 0.05, "output_per_1m": 0.15}),
    )
    cost = (input_tokens / 1_000_000.0 * pricing["input_per_1m"]) + (
        output_tokens / 1_000_000.0 * pricing["output_per_1m"]
    )
    return round(cost, 6)


def estimate_tokens(text: str) -> int:
    """Estimate token count for a text string using standard word heuristics."""
    if not text:
        return 0
    words = len(text.split())
    return max(1, int(words * 1.33))


async def record_llm_usage(
    request_id: str,
    user_id: str | None,
    agent_id: str | None,
    model: str,
    input_tokens: int,
    output_tokens: int,
    latency_ms: float = 0.0,
    session: AsyncSession | None = None,
) -> LLMUsage:
    """Persist an LLM token usage record to the database."""
    total_tokens = input_tokens + output_tokens
    cost = calculate_estimated_cost(model, input_tokens, output_tokens)

    async def _insert(s: AsyncSession) -> LLMUsage:
        usage = LLMUsage(
            request_id=request_id,
            user_id=user_id,
            agent_id=agent_id,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            estimated_cost=cost,
            latency_ms=latency_ms,
        )
        s.add(usage)
        await s.flush()
        logger.info(
            "Recorded LLM usage: req=%s user=%s model=%s tokens=%d cost=$%.6f latency=%.2fms",
            request_id,
            user_id,
            model,
            total_tokens,
            cost,
            latency_ms,
        )
        return usage

    if session is not None:
        return await _insert(session)
    async with session_scope() as new_session:
        return await _insert(new_session)


async def get_user_daily_token_usage(
    user_id: str,
    session: AsyncSession | None = None,
) -> int:
    """Calculate total tokens consumed by user today in UTC."""
    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

    async def _query(s: AsyncSession) -> int:
        stmt = (
            select(func.coalesce(func.sum(LLMUsage.total_tokens), 0))
            .where(LLMUsage.user_id == user_id)
            .where(LLMUsage.created_at >= today_start)
        )
        result = await s.execute(stmt)
        return int(result.scalar_one())

    if session is not None:
        return await _query(session)
    async with session_scope() as new_session:
        return await _query(new_session)


async def check_user_quota(
    user_id: str,
    roles: list[str],
    session: AsyncSession | None = None,
) -> tuple[bool, int, int]:
    """Check if user has remaining token quota for today.

    Returns (is_allowed, used_today, daily_limit).
    """
    role_limits = [
        DEFAULT_ROLE_LIMITS[r.lower()] for r in roles if r.lower() in DEFAULT_ROLE_LIMITS
    ]
    limit = max(role_limits) if role_limits else DEFAULT_DAILY_LIMIT

    used_today = await get_user_daily_token_usage(user_id, session=session)
    is_allowed = used_today < limit
    return is_allowed, used_today, limit
