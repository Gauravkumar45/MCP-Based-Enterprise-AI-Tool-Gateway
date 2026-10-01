"""Order service abstraction for e-commerce, fulfillment, and operations."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories import OrderRepository


class OrderService:
    """Enterprise order management and fulfillment query service."""

    def __init__(self, session: AsyncSession) -> None:
        self.repo = OrderRepository(session)

    async def get_order(self, order_id: str) -> dict[str, Any] | None:
        """Fetch single order by order identifier."""
        order = await self.repo.get_by_order_id(order_id)
        if not order:
            return None

        return {
            "order_id": order.order_id,
            "customer_id": order.customer_id,
            "total_amount": order.total_amount,
            "status": order.status,
            "items_count": order.items_count,
            "tracking_number": order.tracking_number,
            "created_at": order.created_at.isoformat() if order.created_at else None,
        }

    async def get_customer_orders(self, customer_id: str) -> list[dict[str, Any]]:
        """List orders placed by a specific customer."""
        orders = await self.repo.list_by_customer_id(customer_id)
        return [
            {
                "order_id": o.order_id,
                "customer_id": o.customer_id,
                "total_amount": o.total_amount,
                "status": o.status,
                "items_count": o.items_count,
                "tracking_number": o.tracking_number,
            }
            for o in orders
        ]
