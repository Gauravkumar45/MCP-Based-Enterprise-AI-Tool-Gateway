"""Health, readiness, and liveness probe endpoints."""

import time
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.database.session import get_db
from app.schemas.common import HealthResponse
from app.services.rate_limit import get_redis_client

router = APIRouter(tags=["System Probes"])


@router.get("/health", response_model=HealthResponse, summary="Liveness Probe")
async def health() -> HealthResponse:
    """Basic service liveness check."""
    settings = get_settings()
    return HealthResponse(
        status="healthy",
        service=settings.APP_NAME,
        version=settings.MCP_SERVER_VERSION,
        timestamp=datetime.now(UTC).isoformat(),
    )


@router.get("/ready", summary="Readiness Probe")
async def ready(db: AsyncSession = Depends(get_db)) -> JSONResponse:
    """Deep readiness check validating database and redis connectivity."""
    settings = get_settings()
    checks: dict[str, Any] = {}
    is_ready = True

    # 1. Database check
    try:
        t0 = time.perf_counter()
        await db.execute(text("SELECT 1"))
        latency = round((time.perf_counter() - t0) * 1000, 2)
        checks["database"] = {"status": "connected", "latency_ms": latency}
    except Exception as e:
        is_ready = False
        checks["database"] = {"status": "unhealthy", "error": str(e)}

    # 2. Redis check
    redis = get_redis_client()
    if redis is not None:
        try:
            t0 = time.perf_counter()
            await redis.ping()
            latency = round((time.perf_counter() - t0) * 1000, 2)
            checks["redis"] = {"status": "connected", "latency_ms": latency}
        except Exception as e:
            checks["redis"] = {"status": "degraded", "error": str(e)}
    else:
        checks["redis"] = {"status": "in_memory_fallback"}

    status_code = status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if is_ready else "not_ready",
            "service": settings.APP_NAME,
            "checks": checks,
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )
