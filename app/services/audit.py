"""Audit logging service capturing immutable invocation traces in PostgreSQL."""

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.database.models import AuditLog, ToolExecution
from app.database.repositories import AuditRepository
from app.database.session import session_scope

SENSITIVE_KEYS = {"password", "secret", "token", "jwt", "authorization", "api_key", "credential"}


def sanitize_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Sanitize payload by redacting sensitive fields."""
    if not payload:
        return {}
    sanitized: dict[str, Any] = {}
    for k, v in payload.items():
        if any(sens in k.lower() for sens in SENSITIVE_KEYS):
            sanitized[k] = "[REDACTED]"
        elif isinstance(v, dict):
            sanitized[k] = sanitize_payload(v)
        else:
            sanitized[k] = v
    return sanitized


def compute_input_hash(payload: dict[str, Any] | None) -> str:
    """Compute deterministic SHA-256 hash of sanitized input arguments."""
    sanitized = sanitize_payload(payload)
    serialized = json.dumps(sanitized, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class AuditService:
    """Enterprise audit trail service recording security and operational traces."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        self.session = session

    async def log_tool_invocation(
        self,
        request_id: str,
        tool_name: str,
        execution_status: str,
        latency_ms: float,
        user_id: str | None = None,
        agent_id: str | None = None,
        raw_inputs: dict[str, Any] | None = None,
        error_code: str | None = None,
        result_summary: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """Record audit log and tool execution trace into database."""
        input_hash = compute_input_hash(raw_inputs)
        sanitized_inputs = sanitize_payload(raw_inputs)
        now = datetime.now(UTC)

        audit_log = AuditLog(
            request_id=request_id,
            user_id=user_id,
            agent_id=agent_id,
            tool_name=tool_name,
            timestamp=now,
            input_hash=input_hash,
            execution_status=execution_status,
            latency_ms=round(latency_ms, 2),
            error_code=error_code,
        )

        tool_exec = ToolExecution(
            request_id=request_id,
            tool_name=tool_name,
            user_id=user_id,
            start_time=now,
            end_time=now,
            status=execution_status,
            input_params=sanitized_inputs,
            result_summary=result_summary[:1000] if result_summary else None,
            error_message=error_message[:1000] if error_message else None,
        )

        try:
            if self.session is not None:
                repo = AuditRepository(self.session)
                await repo.record_audit_log(audit_log)
                await repo.record_tool_execution(tool_exec)
            else:
                # Use standalone session scope if no session provided
                async with session_scope() as session:
                    repo = AuditRepository(session)
                    await repo.record_audit_log(audit_log)
                    await repo.record_tool_execution(tool_exec)

            logger.info(
                "AUDIT: request_id=%s tool=%s user=%s status=%s latency=%.2fms",
                request_id,
                tool_name,
                user_id or "anonymous",
                execution_status,
                latency_ms,
                extra={
                    "request_id": request_id,
                    "tool_name": tool_name,
                    "user_id": user_id,
                    "status": execution_status,
                    "latency_ms": latency_ms,
                    "error_code": error_code,
                },
            )
        except Exception as e:
            logger.error("Failed to persist audit log: %s", e)
