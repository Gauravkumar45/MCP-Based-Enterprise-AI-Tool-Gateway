"""Enterprise order lookup tool."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import UserContext
from app.auth.permissions import PermissionName
from app.core.errors import ToolExecutionError
from app.schemas.tools import GetOrderRequest, OrderResponse
from app.services.order_service import OrderService
from app.tools.base import BaseEnterpriseTool


class OrderTool(BaseEnterpriseTool):
    """MCP tool for retrieving customer order and fulfillment data."""

    name = "get_order"
    description = "Retrieve customer order details, fulfillment status, and items"
    required_permission = PermissionName.ORDER_READ.value
    risk_level = "low"
    timeout_seconds = 5
    input_model = GetOrderRequest
    output_model = OrderResponse

    async def execute(
        self,
        arguments: dict[str, Any],
        context: UserContext,
        session: AsyncSession,
    ) -> dict[str, Any]:
        params = self.input_model.model_validate(arguments)
        order_service = OrderService(session)
        order = await order_service.get_order(order_id=params.order_id)
        if not order:
            raise ToolExecutionError(
                tool_name=self.name,
                message=f"Order not found with id='{params.order_id}'",
            )
        return order
