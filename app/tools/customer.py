"""Enterprise customer lookup tool."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import UserContext
from app.auth.permissions import PermissionName
from app.core.errors import ToolExecutionError
from app.schemas.tools import CustomerResponse, GetCustomerRequest
from app.services.customer_service import CustomerService
from app.tools.base import BaseEnterpriseTool


class CustomerTool(BaseEnterpriseTool):
    """MCP tool for retrieving customer information."""

    name = "get_customer"
    description = "Retrieve customer profile, tier, status, and lifetime value"
    required_permission = PermissionName.CUSTOMER_READ.value
    risk_level = "low"
    timeout_seconds = 5
    input_model = GetCustomerRequest
    output_model = CustomerResponse

    async def execute(
        self,
        arguments: dict[str, Any],
        context: UserContext,
        session: AsyncSession,
    ) -> dict[str, Any]:
        params = self.input_model.model_validate(arguments)
        cust_service = CustomerService(session)
        customer = await cust_service.get_customer(
            customer_id=params.customer_id,
            email=params.email,
        )
        if not customer:
            raise ToolExecutionError(
                tool_name=self.name,
                message=f"Customer not found with id='{params.customer_id}' or email='{params.email}'",
            )
        return customer
