"""Enterprise KPI calculation tool."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import UserContext
from app.auth.permissions import PermissionName
from app.schemas.tools import CalculateKpiRequest, CalculateKpiResponse
from app.services.kpi_service import KpiService
from app.tools.base import BaseEnterpriseTool


class CalculateKpiTool(BaseEnterpriseTool):
    """MCP tool for executive metric and KPI calculations."""

    name = "calculate_kpi"
    description = "Calculate strategic executive KPIs like revenue, MRR, AOV, and churn rate"
    required_permission = PermissionName.KPI_CALCULATE.value
    risk_level = "low"
    timeout_seconds = 5
    input_model = CalculateKpiRequest
    output_model = CalculateKpiResponse

    async def execute(
        self,
        arguments: dict[str, Any],
        context: UserContext,
        session: AsyncSession,
    ) -> dict[str, Any]:
        params = self.input_model.model_validate(arguments)
        kpi_service = KpiService(session)
        result = await kpi_service.calculate_kpi(
            metric_name=params.metric_name,
            period=params.period,
        )
        return result
