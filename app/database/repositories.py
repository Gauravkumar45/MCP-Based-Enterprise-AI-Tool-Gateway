"""Repository layer encapsulating database queries and mutations."""

from collections.abc import Sequence

from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import (
    AuditLog,
    Customer,
    Document,
    Invoice,
    Order,
    Permission,
    Role,
    ToolExecution,
    User,
)


class UserRepository:
    """Repository for user management and RBAC resolution."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: str) -> User | None:
        stmt = (
            select(User)
            .options(selectinload(User.roles).selectinload(Role.permissions))
            .where(User.id == user_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        stmt = (
            select(User)
            .options(selectinload(User.roles).selectinload(Role.permissions))
            .where(User.username == username)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        stmt = (
            select(User)
            .options(selectinload(User.roles).selectinload(Role.permissions))
            .where(User.email == email)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()
        return user


class RoleRepository:
    """Repository for role management."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_name(self, name: str) -> Role | None:
        stmt = select(Role).options(selectinload(Role.permissions)).where(Role.name == name)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, role: Role) -> Role:
        self.session.add(role)
        await self.session.flush()
        return role


class PermissionRepository:
    """Repository for permission management."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_name(self, name: str) -> Permission | None:
        stmt = select(Permission).where(Permission.name == name)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, permission: Permission) -> Permission:
        self.session.add(permission)
        await self.session.flush()
        return permission


class AuditRepository:
    """Repository for immutable audit logs and tool traces."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record_audit_log(self, audit_log: AuditLog) -> AuditLog:
        self.session.add(audit_log)
        await self.session.flush()
        return audit_log

    async def record_tool_execution(self, execution: ToolExecution) -> ToolExecution:
        self.session.add(execution)
        await self.session.flush()
        return execution

    async def list_audit_logs(
        self,
        tool_name: str | None = None,
        user_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[AuditLog]:
        stmt = select(AuditLog).order_by(desc(AuditLog.timestamp))
        if tool_name:
            stmt = stmt.where(AuditLog.tool_name == tool_name)
        if user_id:
            stmt = stmt.where(AuditLog.user_id == user_id)
        if status:
            stmt = stmt.where(AuditLog.execution_status == status)
        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()


class DocumentRepository:
    """Repository for document searching and retrieval."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def search(
        self,
        query: str,
        category: str | None = None,
        limit: int = 5,
    ) -> Sequence[Document]:
        stmt = select(Document)
        if category:
            stmt = stmt.where(Document.category == category)

        words = [w.strip() for w in query.split() if len(w.strip()) > 1]
        if words:
            conditions = []
            for word in words:
                conditions.append(Document.title.ilike(f"%{word}%"))
                conditions.append(Document.content.ilike(f"%{word}%"))
            stmt = stmt.where(or_(*conditions))
        else:
            stmt = stmt.where(Document.title.ilike(f"%{query}%"))

        stmt = stmt.limit(limit * 2)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_document_id(self, document_id: str) -> Document | None:
        stmt = select(Document).where(Document.document_id == document_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, document: Document) -> Document:
        self.session.add(document)
        await self.session.flush()
        return document


class CustomerRepository:
    """Repository for customer entity queries."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_customer_id(self, customer_id: str) -> Customer | None:
        stmt = select(Customer).where(Customer.customer_id == customer_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Customer | None:
        stmt = select(Customer).where(Customer.email == email)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_top_customers(self, limit: int = 10) -> Sequence[Customer]:
        stmt = select(Customer).order_by(desc(Customer.lifetime_value)).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create(self, customer: Customer) -> Customer:
        self.session.add(customer)
        await self.session.flush()
        return customer


class InvoiceRepository:
    """Repository for invoice queries."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_invoice_id(self, invoice_id: str) -> Invoice | None:
        stmt = select(Invoice).where(Invoice.invoice_id == invoice_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_customer_id(self, customer_id: str) -> Sequence[Invoice]:
        stmt = (
            select(Invoice)
            .where(Invoice.customer_id == customer_id)
            .order_by(desc(Invoice.issued_date))
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create(self, invoice: Invoice) -> Invoice:
        self.session.add(invoice)
        await self.session.flush()
        return invoice


class OrderRepository:
    """Repository for order queries."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_order_id(self, order_id: str) -> Order | None:
        stmt = select(Order).where(Order.order_id == order_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_customer_id(self, customer_id: str) -> Sequence[Order]:
        stmt = (
            select(Order).where(Order.customer_id == customer_id).order_by(desc(Order.created_at))
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create(self, order: Order) -> Order:
        self.session.add(order)
        await self.session.flush()
        return order
