"""Customer service abstraction for enterprise client intelligence."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories import CustomerRepository


class CustomerService:
    """Enterprise customer data retrieval and CRM abstraction."""

    def __init__(self, session: AsyncSession) -> None:
        self.repo = CustomerRepository(session)

    async def get_customer(
        self, customer_id: str | None = None, email: str | None = None
    ) -> dict[str, Any] | None:
        """Fetch customer profile by customer_id or email address."""
        if customer_id:
            customer = await self.repo.get_by_customer_id(customer_id)
        elif email:
            customer = await self.repo.get_by_email(email)
        else:
            return None

        if not customer:
            return None

        return {
            "customer_id": customer.customer_id,
            "name": customer.name,
            "email": customer.email,
            "tier": customer.tier,
            "lifetime_value": customer.lifetime_value,
            "status": customer.status,
            "created_at": customer.created_at.isoformat() if customer.created_at else None,
        }

    async def get_top_customers(self, limit: int = 5) -> list[dict[str, Any]]:
        """Retrieve highest revenue customers."""
        customers = await self.repo.list_top_customers(limit=limit)
        return [
            {
                "customer_id": c.customer_id,
                "name": c.name,
                "email": c.email,
                "tier": c.tier,
                "lifetime_value": c.lifetime_value,
                "status": c.status,
            }
            for c in customers
        ]
