"""Security tests for unauthorized tool invocation and privilege escalation."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import UserContext
from app.core.errors import AuthorizationError, ToolNotFoundError
from app.mcp.registry import create_default_registry


@pytest.mark.asyncio
async def test_viewer_cannot_execute_database_tool(
    db_session: AsyncSession, viewer_context: UserContext
) -> None:
    """Security test: Viewer without 'database.read' must be blocked before query execution."""
    registry = create_default_registry()
    with pytest.raises(AuthorizationError) as exc_info:
        await registry.execute_tool(
            tool_name="query_database",
            arguments={"query": "SELECT * FROM customers"},
            user_context=viewer_context,
            session=db_session,
        )
    assert exc_info.value.code.value == "AUTHORIZATION_FAILED"


@pytest.mark.asyncio
async def test_viewer_cannot_execute_invoice_tool(
    db_session: AsyncSession, viewer_context: UserContext
) -> None:
    """Security test: Viewer without 'invoice.read' must be blocked."""
    registry = create_default_registry()
    with pytest.raises(AuthorizationError):
        await registry.execute_tool(
            tool_name="get_invoice",
            arguments={"invoice_id": "INV-2024-001"},
            user_context=viewer_context,
            session=db_session,
        )


@pytest.mark.asyncio
async def test_invalid_tool_name_rejected(
    db_session: AsyncSession, analyst_context: UserContext
) -> None:
    """Security test: Invoking an unregistered or malicious tool name must raise ToolNotFoundError."""
    registry = create_default_registry()
    with pytest.raises(ToolNotFoundError):
        await registry.execute_tool(
            tool_name="../../etc/passwd",
            arguments={},
            user_context=analyst_context,
            session=db_session,
        )
