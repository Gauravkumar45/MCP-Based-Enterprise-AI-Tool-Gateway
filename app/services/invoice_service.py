"""Invoice service abstraction for financial records and billing tools."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories import InvoiceRepository


class InvoiceService:
    """Enterprise billing and invoice retrieval service."""

    def __init__(self, session: AsyncSession) -> None:
        self.repo = InvoiceRepository(session)

    async def get_invoice(self, invoice_id: str) -> dict[str, Any] | None:
        """Fetch single invoice by identifier."""
        invoice = await self.repo.get_by_invoice_id(invoice_id)
        if not invoice:
            return None

        return {
            "invoice_id": invoice.invoice_id,
            "customer_id": invoice.customer_id,
            "amount": invoice.amount,
            "currency": invoice.currency,
            "status": invoice.status,
            "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
            "issued_date": invoice.issued_date.isoformat() if invoice.issued_date else None,
        }

    async def get_customer_invoices(self, customer_id: str) -> list[dict[str, Any]]:
        """List all invoices associated with a specific customer."""
        invoices = await self.repo.list_by_customer_id(customer_id)
        return [
            {
                "invoice_id": inv.invoice_id,
                "customer_id": inv.customer_id,
                "amount": inv.amount,
                "currency": inv.currency,
                "status": inv.status,
                "due_date": inv.due_date.isoformat() if inv.due_date else None,
                "issued_date": inv.issued_date.isoformat() if inv.issued_date else None,
            }
            for inv in invoices
        ]
