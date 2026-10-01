"""Redis-backed rate limiting with sliding window algorithm and in-memory fallback."""

import time
from collections import defaultdict

import redis.asyncio as aioredis

from app.core.config import get_settings
from app.core.errors import RateLimitExceededError
from app.core.logging import logger

_in_memory_windows: dict[str, list[float]] = defaultdict(list)
_redis_client: aioredis.Redis | None = None


def get_redis_client() -> aioredis.Redis | None:
    """Get or create singleton Redis client."""
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        try:
            _redis_client = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_timeout=2.0,
            )
        except Exception as e:
            logger.warning("Failed to initialize Redis client: %s. Using memory fallback.", e)
            _redis_client = None
    return _redis_client


class RateLimiter:
    """Sliding-window rate limiter ensuring quota fairness and DoS prevention."""

    def __init__(
        self,
        redis_client: aioredis.Redis | None = None,
        max_requests: int | None = None,
        window_seconds: int | None = None,
    ) -> None:
        settings = get_settings()
        self.redis = redis_client
        self.max_requests = max_requests or settings.RATE_LIMIT_REQUESTS
        self.window_seconds = window_seconds or settings.RATE_LIMIT_WINDOW_SECONDS

    async def check_rate_limit(
        self,
        identifier: str,
        tool_name: str | None = None,
        custom_limit: int | None = None,
        custom_window: int | None = None,
    ) -> None:
        """Evaluate rate limit quota for user/agent identifier.

        Raises:
            RateLimitExceededError if requests exceed allowed threshold.
        """
        limit = custom_limit or self.max_requests
        window = custom_window or self.window_seconds
        key = f"ratelimit:{identifier}" if not tool_name else f"ratelimit:{identifier}:{tool_name}"
        now = time.time()
        window_start = now - window

        # 1. Attempt Redis sliding window with ZREMRANGEBYSCORE and ZADD
        redis = self.redis or get_redis_client()
        if redis is not None:
            try:
                pipe = redis.pipeline()
                pipe.zremrangebyscore(key, 0, window_start)
                pipe.zcard(key)
                pipe.zadd(key, {str(now): now})
                pipe.expire(key, window + 1)
                results = await pipe.execute()

                current_count = results[1]
                if current_count >= limit:
                    logger.warning(
                        "Rate limit exceeded for key %s (count: %d, limit: %d)",
                        key,
                        current_count,
                        limit,
                    )
                    raise RateLimitExceededError(key=key, retry_after=window)
                return
            except RateLimitExceededError:
                raise
            except Exception as e:
                logger.warning(
                    "Redis rate limit check error: %s. Falling back to in-memory window.", e
                )

        # 2. In-memory sliding window fallback
        timestamps = _in_memory_windows[key]
        # Discard expired timestamps
        _in_memory_windows[key] = [t for t in timestamps if t > window_start]
        if len(_in_memory_windows[key]) >= limit:
            logger.warning("In-memory rate limit exceeded for key %s", key)
            raise RateLimitExceededError(key=key, retry_after=window)

        _in_memory_windows[key].append(now)

    async def reset(self, identifier: str, tool_name: str | None = None) -> None:
        """Reset rate limit counter for a given key (used in tests)."""
        key = f"ratelimit:{identifier}" if not tool_name else f"ratelimit:{identifier}:{tool_name}"
        if key in _in_memory_windows:
            _in_memory_windows[key].clear()
        redis = self.redis or get_redis_client()
        if redis is not None:
            try:
                await redis.delete(key)
            except Exception:
                pass
