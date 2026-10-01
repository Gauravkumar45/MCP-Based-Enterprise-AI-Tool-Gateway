"""Unit tests for sliding window rate limiting."""

import pytest

from app.core.errors import RateLimitExceededError
from app.services.rate_limit import RateLimiter


@pytest.mark.asyncio
async def test_in_memory_rate_limiter_threshold() -> None:
    """Test that requests exceeding threshold within window raise RateLimitExceededError."""
    limiter = RateLimiter(redis_client=None, max_requests=3, window_seconds=10)
    user_id = "test_user_rate_limit"
    await limiter.reset(user_id)

    # 3 allowed requests
    for _ in range(3):
        await limiter.check_rate_limit(user_id)

    # 4th request must trigger rate limit exception
    with pytest.raises(RateLimitExceededError) as exc_info:
        await limiter.check_rate_limit(user_id)

    assert exc_info.value.code.value == "TOOL_RATE_LIMITED"
    assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_rate_limiter_per_tool_isolation() -> None:
    """Test that rate limits can be tracked per-tool independently."""
    limiter = RateLimiter(redis_client=None, max_requests=2, window_seconds=10)
    user_id = "test_user_iso"
    await limiter.reset(user_id, tool_name="query_database")
    await limiter.reset(user_id, tool_name="search_documents")

    # Consume quota for query_database
    await limiter.check_rate_limit(user_id, tool_name="query_database")
    await limiter.check_rate_limit(user_id, tool_name="query_database")

    with pytest.raises(RateLimitExceededError):
        await limiter.check_rate_limit(user_id, tool_name="query_database")

    # search_documents should still have quota available
    await limiter.check_rate_limit(user_id, tool_name="search_documents")
