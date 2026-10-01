"""Enterprise invoice lookup tool."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import UserContext
from app.auth.permissions import PermissionName
from app.core.errors import ToolExecutionError
from app.schemas.tools import GetInvoiceRequest, InvoiceResponse
from app.services.invoice_service import InvoiceService
from app.tools.base import BaseEnterpriseTool


class InvoiceTool(BaseEnterpriseTool):
    """MCP tool for retrieving billing invoice details."""

    name = "get_invoice"
    description = "Retrieve enterprise invoice status and financial amounts"
    required_permission = PermissionName.INVOICE_READ.value
    risk_level = "low"
    timeout_seconds = 5
    input_model = GetInvoiceRequest
    output_model = InvoiceResponse

    async def execute(
        self,
        arguments: dict[str, Any],
        context: UserContext,
        session: AsyncSession,
    ) -> dict[str, Any]:
        params = self.input_model.model_validate(arguments)
        inv_service = InvoiceService(session)
        invoice = await inv_service.get_invoice(invoice_id=params.invoice_id)
        if not invoice:
            raise ToolExecutionError(
                tool_name=self.name,
                message=f"Invoice not found with id='{params.invoice_id}'",
            )
        return invoice
