"""System status and telemetry service abstraction."""

import os
import platform
import time
from typing import Any

import redis.asyncio as aioredis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_START_TIME = time.time()


class SystemService:
    """Internal system health, dependency checks, and runtime telemetry."""

    def __init__(self, session: AsyncSession, redis_client: aioredis.Redis | None = None) -> None:
        self.session = session
        self.redis = redis_client

    async def get_system_status(self, component: str | None = None) -> dict[str, Any]:
        """Collect diagnostic and health metrics for the gateway and dependencies."""
        now = time.time()
        uptime_seconds = round(now - _START_TIME, 2)

        # 1. Database check
        db_status = "unknown"
        db_latency_ms = None
        try:
            t0 = time.perf_counter()
            await self.session.execute(text("SELECT 1"))
            db_latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            db_status = "healthy"
        except Exception as e:
            db_status = f"unhealthy: {e!s}"

        # 2. Redis check
        redis_status = "disabled"
        redis_latency_ms = None
        if self.redis:
            try:
                t0 = time.perf_counter()
                await self.redis.ping()
                redis_latency_ms = round((time.perf_counter() - t0) * 1000, 2)
                redis_status = "healthy"
            except Exception as e:
                redis_status = f"unhealthy: {e!s}"

        status_data: dict[str, Any] = {
            "status": "healthy" if db_status == "healthy" else "degraded",
            "uptime_seconds": uptime_seconds,
            "environment": os.getenv("APP_ENV", "development"),
            "python_version": platform.python_version(),
            "dependencies": {
                "database": {"status": db_status, "latency_ms": db_latency_ms},
                "redis": {"status": redis_status, "latency_ms": redis_latency_ms},
            },
        }

        if component and component in status_data["dependencies"]:
            return {component: status_data["dependencies"][component]}

        return status_data
