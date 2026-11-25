"""Authentication guards: JWT revocation list and failed-login throttling.

Both use Redis when it is reachable so state is shared across gateway replicas, and fall back
to process-local memory when Redis is down, mirroring the rate limiter's behaviour.
"""

import time
from collections import defaultdict

import redis.asyncio as aioredis

from app.core.config import get_settings
from app.core.logging import logger
from app.services.rate_limit import get_redis_client

_REVOKED_PREFIX = "auth:revoked_jti:"
_LOGIN_FAILURE_PREFIX = "auth:login_failures:"

_memory_revoked: dict[str, float] = {}
_memory_login_failures: dict[str, list[float]] = defaultdict(list)


class TokenRevocationList:
    """Deny-list of revoked JWT IDs (``jti``), kept only until each token would expire."""

    def __init__(self, redis_client: aioredis.Redis | None = None) -> None:
        self.redis = redis_client

    def _client(self) -> aioredis.Redis | None:
        return self.redis or get_redis_client()

    async def revoke(self, jti: str, expires_at: float) -> None:
        """Revoke a token until its expiry timestamp (seconds since epoch)."""
        ttl = max(int(expires_at - time.time()) + 1, 1)
        _memory_revoked[jti] = expires_at
        redis = self._client()
        if redis is not None:
            try:
                await redis.set(f"{_REVOKED_PREFIX}{jti}", "1", ex=ttl)
            except Exception as e:
                logger.warning("Redis revoke failed (%s); token revoked in memory only.", e)

    async def is_revoked(self, jti: str) -> bool:
        """Return True if the token ID has been revoked and has not yet expired."""
        expires_at = _memory_revoked.get(jti)
        if expires_at is not None:
            if expires_at > time.time():
                return True
            _memory_revoked.pop(jti, None)

        redis = self._client()
        if redis is not None:
            try:
                return bool(await redis.exists(f"{_REVOKED_PREFIX}{jti}"))
            except Exception as e:
                logger.warning("Redis revocation lookup failed (%s); using memory only.", e)
        return False


class LoginThrottle:
    """Locks a username out after too many failed logins inside a sliding window."""

    def __init__(
        self,
        redis_client: aioredis.Redis | None = None,
        max_failures: int | None = None,
        window_seconds: int | None = None,
    ) -> None:
        settings = get_settings()
        self.redis = redis_client
        self.max_failures = max_failures or settings.LOGIN_MAX_FAILED_ATTEMPTS
        self.window_seconds = window_seconds or settings.LOGIN_LOCKOUT_WINDOW_SECONDS

    def _client(self) -> aioredis.Redis | None:
        return self.redis or get_redis_client()

    @staticmethod
    def _key(username: str) -> str:
        return f"{_LOGIN_FAILURE_PREFIX}{username.strip().lower()}"

    async def failure_count(self, username: str) -> int:
        """Number of failed attempts for this username inside the current window."""
        key = self._key(username)
        window_start = time.time() - self.window_seconds
        redis = self._client()
        if redis is not None:
            try:
                await redis.zremrangebyscore(key, 0, window_start)
                return int(await redis.zcard(key))
            except Exception as e:
                logger.warning("Redis login throttle read failed (%s); using memory.", e)
        _memory_login_failures[key] = [t for t in _memory_login_failures[key] if t > window_start]
        return len(_memory_login_failures[key])

    async def is_locked(self, username: str) -> bool:
        return await self.failure_count(username) >= self.max_failures

    async def record_failure(self, username: str) -> None:
        key = self._key(username)
        now = time.time()
        _memory_login_failures[key].append(now)
        redis = self._client()
        if redis is not None:
            try:
                pipe = redis.pipeline()
                pipe.zadd(key, {f"{now}": now})
                pipe.expire(key, self.window_seconds + 1)
                await pipe.execute()
            except Exception as e:
                logger.warning("Redis login throttle write failed (%s); using memory.", e)

    async def reset(self, username: str) -> None:
        key = self._key(username)
        _memory_login_failures.pop(key, None)
        redis = self._client()
        if redis is not None:
            try:
                await redis.delete(key)
            except Exception:
                pass


_revocation_list: TokenRevocationList | None = None


def get_revocation_list() -> TokenRevocationList:
    """Process-wide revocation list singleton."""
    global _revocation_list
    if _revocation_list is None:
        _revocation_list = TokenRevocationList()
    return _revocation_list
