"""FastAPI application entry point with MCP SSE mount, middleware, and lifecycle management."""

import time
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.audit import router as audit_router
from app.api.auth import router as auth_router
from app.api.copilot import router as copilot_router
from app.api.health import router as health_router
from app.api.tools import router as tools_router
from app.core.config import get_settings
from app.core.errors import GatewayException
from app.core.logging import (
    logger,
    request_id_ctx,
    setup_logging,
    trace_id_ctx,
)
from app.database.session import get_engine, get_readonly_engine
from app.mcp.server import get_mcp_server
from app.services.rate_limit import get_redis_client


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan managing resource initialization and graceful shutdown."""
    settings = get_settings()
    setup_logging(log_level=settings.LOG_LEVEL)
    logger.info(
        "Initializing %s (version: %s, env: %s)...",
        settings.APP_NAME,
        settings.MCP_SERVER_VERSION,
        settings.APP_ENV,
    )

    # Initialize MCP Server singleton
    mcp_server = get_mcp_server()
    logger.info("MCP Server initialized with %d registered tools", len(mcp_server.registry._tools))

    yield

    # Graceful shutdown: dispose engines and close redis
    logger.info("Shutting down %s...", settings.APP_NAME)
    engine = get_engine()
    await engine.dispose()
    ro_engine = get_readonly_engine()
    await ro_engine.dispose()
    redis = get_redis_client()
    if redis is not None:
        await redis.aclose()
    logger.info("Shutdown complete.")


def create_app() -> FastAPI:
    """Application factory for the Enterprise MCP Tool Gateway."""
    settings = get_settings()

    app = FastAPI(
        title="Enterprise MCP Tool Gateway",
        description=(
            "Centralized Model Context Protocol (MCP) gateway enabling AI agents to discover "
            "and securely execute enterprise tools with RBAC authorization, SQL safety verification, "
            "rate limiting, and immutable PostgreSQL audit logging."
        ),
        version=settings.MCP_SERVER_VERSION,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Tracing & Context Middleware
    @app.middleware("http")
    async def request_tracing_middleware(request: Request, call_next: Any) -> Any:
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        trace_id = request.headers.get("X-Trace-ID") or str(uuid.uuid4())
        request_id_ctx.set(req_id)
        trace_id_ctx.set(trace_id)

        t0 = time.perf_counter()
        try:
            response = await call_next(request)
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            response.headers["X-Request-ID"] = req_id
            response.headers["X-Trace-ID"] = trace_id

            # Avoid logging excessive noise for high-frequency health probes
            if not request.url.path.startswith("/health"):
                logger.info(
                    "%s %s -> %d (%.2fms)",
                    request.method,
                    request.url.path,
                    response.status_code,
                    latency_ms,
                    extra={
                        "request_id": req_id,
                        "trace_id": trace_id,
                        "latency_ms": latency_ms,
                        "status_code": response.status_code,
                    },
                )
            return response
        except Exception as exc:
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            logger.error(
                "Unhandled error during request %s %s: %s",
                request.method,
                request.url.path,
                exc,
                exc_info=True,
                extra={"request_id": req_id, "trace_id": trace_id, "latency_ms": latency_ms},
            )
            raise

    # Gateway Exception Handler
    @app.exception_handler(GatewayException)
    async def gateway_exception_handler(request: Request, exc: GatewayException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_dict(),
        )

    # Mount the official Model Context Protocol (MCP) SSE Transport App
    mcp_server = get_mcp_server()
    app.mount("/mcp", mcp_server.get_sse_app())

    # Include REST routers
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(tools_router)
    app.include_router(audit_router)
    app.include_router(copilot_router)

    return app


app = create_app()
