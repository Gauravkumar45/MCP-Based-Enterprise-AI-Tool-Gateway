"""Enterprise system health and telemetry tool."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import UserContext
from app.auth.permissions import PermissionName
from app.schemas.tools import GetSystemStatusRequest, SystemStatusResponse
from app.services.rate_limit import get_redis_client
from app.services.system_service import SystemService
from app.tools.base import BaseEnterpriseTool


class SystemStatusTool(BaseEnterpriseTool):
    """MCP tool for inspecting gateway operational health."""

    name = "get_system_status"
    description = "Inspect system health, database latency, and infrastructure status"
    required_permission = PermissionName.SYSTEM_STATUS.value
    risk_level = "low"
    timeout_seconds = 5
    input_model = GetSystemStatusRequest
    output_model = SystemStatusResponse

    async def execute(
        self,
        arguments: dict[str, Any],
        context: UserContext,
        session: AsyncSession,
    ) -> dict[str, Any]:
        params = self.input_model.model_validate(arguments)
        redis_client = get_redis_client()
        sys_service = SystemService(session, redis_client=redis_client)
        result = await sys_service.get_system_status(component=params.component)
        return result
