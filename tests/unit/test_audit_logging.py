"""Unit tests for audit trail creation and sensitive data redaction."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import AuditLog
from app.services.audit import (
    AuditService,
    compute_input_hash,
    sanitize_payload,
)


def test_sanitize_payload_redaction() -> None:
    """Verify that credentials and secrets are redacted from audit entries."""
    raw = {
        "username": "admin",
        "password": "ClearTextPassword123!",
        "api_key": "sk-1234567890",
        "authorization": "Bearer eyJhbGci...",
        "nested": {
            "jwt_secret": "my-secret",
            "safe_param": "visible",
        },
        "query": "SELECT * FROM customers",
    }
    sanitized = sanitize_payload(raw)

    assert sanitized["password"] == "[REDACTED]"
    assert sanitized["api_key"] == "[REDACTED]"
    assert sanitized["authorization"] == "[REDACTED]"
    assert sanitized["nested"]["jwt_secret"] == "[REDACTED]"
    assert sanitized["nested"]["safe_param"] == "visible"
    assert sanitized["query"] == "SELECT * FROM customers"


def test_compute_input_hash_deterministic() -> None:
    """Verify that input hash is deterministic regardless of key order."""
    payload1 = {"b": 2, "a": 1}
    payload2 = {"a": 1, "b": 2}
    assert compute_input_hash(payload1) == compute_input_hash(payload2)


async def test_audit_log_database_persistence(db_session: AsyncSession) -> None:
    """Verify that AuditService correctly writes records to database."""
    service = AuditService(session=db_session)
    await service.log_tool_invocation(
        request_id="req-unit-123",
        tool_name="query_database",
        execution_status="SUCCESS",
        latency_ms=45.2,
        user_id="user-456",
        raw_inputs={"query": "SELECT 1"},
    )
    await db_session.commit()

    stmt = select(AuditLog).where(AuditLog.request_id == "req-unit-123")
    res = await db_session.execute(stmt)
    record = res.scalar_one_or_none()

    assert record is not None
    assert record.tool_name == "query_database"
    assert record.execution_status == "SUCCESS"
    assert record.user_id == "user-456"
    assert record.input_hash is not None
