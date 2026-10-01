"""Audit log inspection API."""

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import require_permission
from app.auth.models import UserContext
from app.auth.permissions import PermissionName
from app.database.repositories import AuditRepository
from app.database.session import get_db

router = APIRouter(prefix="/audit", tags=["Audit & Compliance"])


@router.get("/logs", summary="List Audit Logs")
async def list_audit_logs(
    tool_name: str | None = Query(None, description="Filter by tool name"),
    user_id: str | None = Query(None, description="Filter by user id"),
    status: str | None = Query(
        None, description="Filter by execution status (SUCCESS, FAILED, DENIED, TIMEOUT)"
    ),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: UserContext = Depends(require_permission(PermissionName.AUDIT_READ.value)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve immutable audit logs and tool traces (Restricted to auditors and administrators)."""
    repo = AuditRepository(db)
    logs = await repo.list_audit_logs(
        tool_name=tool_name,
        user_id=user_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return {
        "total": len(logs),
        "limit": limit,
        "offset": offset,
        "items": [
            {
                "id": log_entry.id,
                "request_id": log_entry.request_id,
                "user_id": log_entry.user_id,
                "agent_id": log_entry.agent_id,
                "tool_name": log_entry.tool_name,
                "timestamp": log_entry.timestamp.isoformat() if log_entry.timestamp else None,
                "input_hash": log_entry.input_hash,
                "execution_status": log_entry.execution_status,
                "latency_ms": log_entry.latency_ms,
                "error_code": log_entry.error_code,
            }
            for log_entry in logs
        ],
    }
