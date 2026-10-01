"""Analytics and Observability API for System Metrics, LLM Usage, and Tool Telemetry."""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import get_current_user_context
from app.auth.models import UserContext
from app.database.models import AuditLog, LLMUsage
from app.database.session import get_db
from app.mcp.server import get_mcp_server
from app.services.token_tracker import DEFAULT_DAILY_LIMIT, DEFAULT_ROLE_LIMITS, MODEL_PRICING

router = APIRouter(prefix="/analytics", tags=["Analytics & Observability"])


class DashboardMetricsResponse(BaseModel):
    """Aggregated system and AI platform metrics."""

    total_tool_calls: int
    successful_tool_calls: int
    failed_tool_calls: int
    active_tools: int
    avg_tool_latency_ms: float
    total_tokens_used: int
    estimated_llm_cost: float
    tool_usage_counts: dict[str, int]
    tool_execution_trend: list[dict[str, Any]]
    status_breakdown: dict[str, int]
    latency_by_tool: dict[str, float]
    token_usage_trend: list[dict[str, Any]]


class UserUsageResponse(BaseModel):
    """User-specific token consumption, quota status, and cost metrics."""

    username: str
    user_id: str
    roles: list[str]
    today_tokens: int
    month_tokens: int
    total_requests: int
    avg_tokens_per_request: float
    estimated_cost: float
    daily_limit: int
    tokens_remaining: int
    percent_used: float
    is_warning: bool
    is_exceeded: bool
    usage_by_model: dict[str, int]
    daily_history: list[dict[str, Any]]
    pricing_catalog: dict[str, dict[str, float]]


class ToolStatItem(BaseModel):
    """Detailed analytics and metadata for an MCP tool."""

    name: str
    description: str
    risk_level: str
    required_permission: str
    timeout_seconds: int
    execution_count: int
    avg_latency_ms: float
    success_rate: float
    input_schema: dict[str, Any]


class ToolExecutionItem(BaseModel):
    """Individual execution ledger entry."""

    id: str
    request_id: str
    user_id: str | None
    agent_id: str | None
    tool_name: str
    timestamp: str
    execution_status: str
    latency_ms: float
    error_code: str | None


@router.get(
    "/dashboard", response_model=DashboardMetricsResponse, summary="Get Platform Dashboard Metrics"
)
async def get_dashboard_metrics(
    user: UserContext = Depends(get_current_user_context),
    db: AsyncSession = Depends(get_db),
) -> DashboardMetricsResponse:
    """Retrieve verified platform-level operational KPIs, charts, and trends."""
    registry = get_mcp_server().registry
    active_tools_count = len(registry.list_tools())

    # 1. Audit KPIs
    stmt_total = select(func.count(AuditLog.id))
    total_calls = (await db.execute(stmt_total)).scalar_one() or 0

    stmt_success = select(func.count(AuditLog.id)).where(AuditLog.execution_status == "SUCCESS")
    success_calls = (await db.execute(stmt_success)).scalar_one() or 0

    failed_calls = max(0, total_calls - success_calls)

    stmt_avg_lat = select(func.coalesce(func.avg(AuditLog.latency_ms), 0.0))
    avg_latency = float((await db.execute(stmt_avg_lat)).scalar_one() or 0.0)

    # 2. Token & Cost KPIs
    stmt_tokens = select(func.coalesce(func.sum(LLMUsage.total_tokens), 0))
    total_tokens = int((await db.execute(stmt_tokens)).scalar_one() or 0)

    stmt_cost = select(func.coalesce(func.sum(LLMUsage.estimated_cost), 0.0))
    total_cost = float((await db.execute(stmt_cost)).scalar_one() or 0.0)

    # 3. Tool Usage Counts
    stmt_tool_counts = (
        select(AuditLog.tool_name, func.count(AuditLog.id))
        .group_by(AuditLog.tool_name)
        .order_by(desc(func.count(AuditLog.id)))
    )
    tool_counts_res = (await db.execute(stmt_tool_counts)).all()
    tool_usage_counts = {str(row[0]): int(row[1]) for row in tool_counts_res}

    # 4. Status Breakdown
    stmt_status = select(AuditLog.execution_status, func.count(AuditLog.id)).group_by(
        AuditLog.execution_status
    )
    status_res = (await db.execute(stmt_status)).all()
    status_breakdown = {str(row[0]): int(row[1]) for row in status_res}

    # 5. Latency by Tool
    stmt_tool_lat = select(AuditLog.tool_name, func.avg(AuditLog.latency_ms)).group_by(
        AuditLog.tool_name
    )
    tool_lat_res = (await db.execute(stmt_tool_lat)).all()
    latency_by_tool = {str(row[0]): round(float(row[1]), 2) for row in tool_lat_res}

    # 6. Tool Execution Trend (last 10 recent time buckets)
    stmt_trend = (
        select(
            func.to_char(AuditLog.timestamp, "YYYY-MM-DD HH24:00"),
            func.count(AuditLog.id),
        )
        .group_by(func.to_char(AuditLog.timestamp, "YYYY-MM-DD HH24:00"))
        .order_by(func.to_char(AuditLog.timestamp, "YYYY-MM-DD HH24:00"))
        .limit(24)
    )
    try:
        trend_res = (await db.execute(stmt_trend)).all()
        tool_trend = [{"time": str(row[0]), "executions": int(row[1])} for row in trend_res]
    except Exception:
        tool_trend = []

    # 7. Token Usage Trend
    stmt_token_trend = (
        select(
            func.to_char(LLMUsage.created_at, "YYYY-MM-DD"),
            func.sum(LLMUsage.input_tokens),
            func.sum(LLMUsage.output_tokens),
            func.sum(LLMUsage.total_tokens),
            func.sum(LLMUsage.estimated_cost),
        )
        .group_by(func.to_char(LLMUsage.created_at, "YYYY-MM-DD"))
        .order_by(func.to_char(LLMUsage.created_at, "YYYY-MM-DD"))
        .limit(14)
    )
    try:
        token_trend_res = (await db.execute(stmt_token_trend)).all()
        token_trend = [
            {
                "date": str(row[0]),
                "input_tokens": int(row[1] or 0),
                "output_tokens": int(row[2] or 0),
                "total_tokens": int(row[3] or 0),
                "cost": round(float(row[4] or 0.0), 4),
            }
            for row in token_trend_res
        ]
    except Exception:
        token_trend = []

    return DashboardMetricsResponse(
        total_tool_calls=total_calls,
        successful_tool_calls=success_calls,
        failed_tool_calls=failed_calls,
        active_tools=active_tools_count,
        avg_tool_latency_ms=round(avg_latency, 2),
        total_tokens_used=total_tokens,
        estimated_llm_cost=round(total_cost, 4),
        tool_usage_counts=tool_usage_counts,
        tool_execution_trend=tool_trend,
        status_breakdown=status_breakdown,
        latency_by_tool=latency_by_tool,
        token_usage_trend=token_trend,
    )


@router.get(
    "/user-usage", response_model=UserUsageResponse, summary="Get Current User AI Usage & Quota"
)
async def get_user_usage(
    user: UserContext = Depends(get_current_user_context),
    db: AsyncSession = Depends(get_db),
) -> UserUsageResponse:
    """Retrieve token metrics, daily quota consumption, and cost for the authenticated user."""
    now = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    uid = user.user_id

    # Today's tokens
    stmt_today = (
        select(func.coalesce(func.sum(LLMUsage.total_tokens), 0))
        .where(LLMUsage.user_id == uid)
        .where(LLMUsage.created_at >= today_start)
    )
    today_tokens = int((await db.execute(stmt_today)).scalar_one() or 0)

    # Month's tokens
    stmt_month = (
        select(func.coalesce(func.sum(LLMUsage.total_tokens), 0))
        .where(LLMUsage.user_id == uid)
        .where(LLMUsage.created_at >= month_start)
    )
    month_tokens = int((await db.execute(stmt_month)).scalar_one() or 0)

    # Total requests
    stmt_reqs = select(func.count(LLMUsage.id)).where(LLMUsage.user_id == uid)
    total_reqs = int((await db.execute(stmt_reqs)).scalar_one() or 0)

    # Average tokens
    stmt_avg = select(func.coalesce(func.avg(LLMUsage.total_tokens), 0.0)).where(
        LLMUsage.user_id == uid
    )
    avg_tokens = float((await db.execute(stmt_avg)).scalar_one() or 0.0)

    # Total user cost
    stmt_cost = select(func.coalesce(func.sum(LLMUsage.estimated_cost), 0.0)).where(
        LLMUsage.user_id == uid
    )
    user_cost = float((await db.execute(stmt_cost)).scalar_one() or 0.0)

    # Determine daily limit
    daily_limit = DEFAULT_DAILY_LIMIT
    for r in user.roles:
        r_clean = r.lower()
        if r_clean in DEFAULT_ROLE_LIMITS and DEFAULT_ROLE_LIMITS[r_clean] > daily_limit:
            daily_limit = DEFAULT_ROLE_LIMITS[r_clean]

    tokens_remaining = max(0, daily_limit - today_tokens)
    percent_used = round((today_tokens / daily_limit) * 100.0, 1) if daily_limit > 0 else 0.0
    is_warning = percent_used >= 80.0
    is_exceeded = today_tokens >= daily_limit

    # Usage by model
    stmt_models = (
        select(LLMUsage.model, func.sum(LLMUsage.total_tokens))
        .where(LLMUsage.user_id == uid)
        .group_by(LLMUsage.model)
    )
    models_res = (await db.execute(stmt_models)).all()
    usage_by_model = {str(row[0]): int(row[1]) for row in models_res}

    # Daily history
    stmt_history = (
        select(
            func.to_char(LLMUsage.created_at, "YYYY-MM-DD"),
            func.sum(LLMUsage.total_tokens),
            func.sum(LLMUsage.estimated_cost),
        )
        .where(LLMUsage.user_id == uid)
        .group_by(func.to_char(LLMUsage.created_at, "YYYY-MM-DD"))
        .order_by(func.to_char(LLMUsage.created_at, "YYYY-MM-DD"))
        .limit(14)
    )
    try:
        hist_res = (await db.execute(stmt_history)).all()
        daily_history = [
            {
                "date": str(row[0]),
                "tokens": int(row[1] or 0),
                "cost": round(float(row[2] or 0.0), 4),
            }
            for row in hist_res
        ]
    except Exception:
        daily_history = []

    return UserUsageResponse(
        username=user.username,
        user_id=uid,
        roles=user.roles,
        today_tokens=today_tokens,
        month_tokens=month_tokens,
        total_requests=total_reqs,
        avg_tokens_per_request=round(avg_tokens, 1),
        estimated_cost=round(user_cost, 4),
        daily_limit=daily_limit,
        tokens_remaining=tokens_remaining,
        percent_used=percent_used,
        is_warning=is_warning,
        is_exceeded=is_exceeded,
        usage_by_model=usage_by_model,
        daily_history=daily_history,
        pricing_catalog=MODEL_PRICING,
    )


@router.get(
    "/tool-stats", response_model=list[ToolStatItem], summary="Get MCP Tool Performance Statistics"
)
async def get_tool_statistics(
    user: UserContext = Depends(get_current_user_context),
    db: AsyncSession = Depends(get_db),
) -> list[ToolStatItem]:
    """Retrieve live metrics for every registered MCP tool."""
    registry = get_mcp_server().registry
    tools = registry.list_tools()

    # Query aggregates from audit_logs
    stmt = select(
        AuditLog.tool_name,
        func.count(AuditLog.id),
        func.avg(AuditLog.latency_ms),
        func.count(AuditLog.id).filter(AuditLog.execution_status == "SUCCESS"),
    ).group_by(AuditLog.tool_name)
    stats_map: dict[str, dict[str, Any]] = {}
    for row in (await db.execute(stmt)).all():
        t_name = str(row[0])
        total = int(row[1])
        avg_lat = round(float(row[2] or 0.0), 1)
        succ = int(row[3] or 0)
        rate = round((succ / total) * 100.0, 1) if total > 0 else 100.0
        stats_map[t_name] = {"count": total, "avg_latency": avg_lat, "success_rate": rate}

    results: list[ToolStatItem] = []
    for tool in tools:
        t_stat = stats_map.get(tool.name, {"count": 0, "avg_latency": 0.0, "success_rate": 100.0})
        results.append(
            ToolStatItem(
                name=tool.name,
                description=tool.description,
                risk_level=tool.risk_level,
                required_permission=tool.required_permission,
                timeout_seconds=tool.timeout_seconds,
                execution_count=t_stat["count"],
                avg_latency_ms=t_stat["avg_latency"],
                success_rate=t_stat["success_rate"],
                input_schema=tool.input_schema or {},
            )
        )
    return results


@router.get("/executions", response_model=list[ToolExecutionItem], summary="Filter Tool Executions")
async def get_tool_executions(
    tool_name: str | None = Query(None, description="Filter by tool name"),
    status: str | None = Query(None, description="Filter by status (SUCCESS, FAILED, DENIED)"),
    user_id: str | None = Query(None, description="Filter by user id"),
    limit: int = Query(50, ge=1, le=200, description="Max rows to return"),
    user: UserContext = Depends(get_current_user_context),
    db: AsyncSession = Depends(get_db),
) -> list[ToolExecutionItem]:
    """Retrieve filtered execution traces from immutable audit ledger."""
    stmt = select(AuditLog).order_by(desc(AuditLog.timestamp))
    if tool_name:
        stmt = stmt.where(AuditLog.tool_name == tool_name)
    if status:
        stmt = stmt.where(AuditLog.execution_status == status.upper())
    if user_id:
        stmt = stmt.where(AuditLog.user_id == user_id)

    stmt = stmt.limit(limit)
    rows = (await db.execute(stmt)).scalars().all()

    return [
        ToolExecutionItem(
            id=r.id,
            request_id=r.request_id,
            user_id=r.user_id,
            agent_id=r.agent_id,
            tool_name=r.tool_name,
            timestamp=r.timestamp.isoformat(),
            execution_status=r.execution_status,
            latency_ms=round(r.latency_ms, 2),
            error_code=r.error_code,
        )
        for r in rows
    ]
