"""Unit tests for tool timeout enforcement."""

import asyncio
from typing import Any

import pytest
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import UserContext
from app.core.errors import ToolTimeoutError
from app.mcp.registry import ToolRegistry
from app.tools.base import BaseEnterpriseTool


class SlowInput(BaseModel):
    sleep_seconds: float = 1.0


class SlowOutput(BaseModel):
    done: bool = True


class SimulatedSlowTool(BaseEnterpriseTool):
    """Simulated slow tool exceeding its configured timeout."""

    name = "slow_tool"
    description = "Tool simulating slow latency"
    required_permission = "database.read"
    risk_level = "low"
    timeout_seconds = 1  # 1-second timeout
    input_model = SlowInput
    output_model = SlowOutput

    async def execute(
        self,
        arguments: dict[str, Any],
        context: UserContext,
        session: AsyncSession,
    ) -> dict[str, Any]:
        sleep_time = arguments.get("sleep_seconds", 2.0)
        await asyncio.sleep(sleep_time)
        return {"done": True}


@pytest.mark.asyncio
async def test_tool_timeout_enforcement(
    db_session: AsyncSession, analyst_context: UserContext
) -> None:
    """Verify that a tool running longer than timeout_seconds raises ToolTimeoutError."""
    registry = ToolRegistry()
    slow_tool = SimulatedSlowTool()
    registry.register_tool(slow_tool)

    # Calling tool requesting 3s sleep when timeout is 1s
    with pytest.raises(ToolTimeoutError) as exc_info:
        await registry.execute_tool(
            tool_name="slow_tool",
            arguments={"sleep_seconds": 2.0},
            user_context=analyst_context,
            session=db_session,
        )

    assert exc_info.value.code.value == "TOOL_TIMEOUT"
    assert exc_info.value.status_code == 504
