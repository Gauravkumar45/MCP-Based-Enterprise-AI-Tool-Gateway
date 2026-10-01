"""Integration tests for all enterprise tool implementations against seeded database."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import UserContext
from app.tools.customer import CustomerTool
from app.tools.database import DatabaseQueryTool
from app.tools.documents import DocumentSearchTool
from app.tools.invoice import InvoiceTool
from app.tools.kpi import CalculateKpiTool
from app.tools.order import OrderTool
from app.tools.system import SystemStatusTool


@pytest.mark.asyncio
async def test_database_query_tool_integration(
    db_session: AsyncSession, analyst_context: UserContext
) -> None:
    """Test DatabaseQueryTool executing a safe SELECT on customer table."""
    tool = DatabaseQueryTool()
    result = await tool.execute(
        {"query": "SELECT customer_id, name, lifetime_value FROM customers", "limit": 10},
        context=analyst_context,
        session=db_session,
    )
    assert result["row_count"] >= 1
    assert "columns" in result
    assert "rows" in result
    assert result["limit_applied"] == 10


@pytest.mark.asyncio
async def test_document_search_tool_integration(
    db_session: AsyncSession, analyst_context: UserContext
) -> None:
    """Test DocumentSearchTool retrieving relevant documentation."""
    tool = DocumentSearchTool()
    result = await tool.execute(
        {"query": "security policy rbac", "top_k": 3},
        context=analyst_context,
        session=db_session,
    )
    assert result["total_found"] >= 1
    top_doc = result["results"][0]
    assert "Enterprise Security Policy" in top_doc["title"]
    assert top_doc["score"] > 0.0


@pytest.mark.asyncio
async def test_customer_tool_integration(
    db_session: AsyncSession, analyst_context: UserContext
) -> None:
    """Test CustomerTool looking up customer profile."""
    tool = CustomerTool()
    result = await tool.execute(
        {"customer_id": "CUST-1001"},
        context=analyst_context,
        session=db_session,
    )
    assert result["customer_id"] == "CUST-1001"
    assert result["name"] == "Acme Corp"
    assert result["tier"] == "enterprise"


@pytest.mark.asyncio
async def test_invoice_tool_integration(
    db_session: AsyncSession, analyst_context: UserContext
) -> None:
    """Test InvoiceTool looking up invoice by id."""
    tool = InvoiceTool()
    result = await tool.execute(
        {"invoice_id": "INV-2024-001"},
        context=analyst_context,
        session=db_session,
    )
    assert result["invoice_id"] == "INV-2024-001"
    assert result["customer_id"] == "CUST-1001"
    assert result["amount"] == 50000.0


@pytest.mark.asyncio
async def test_order_tool_integration(
    db_session: AsyncSession, analyst_context: UserContext
) -> None:
    """Test OrderTool looking up order by id."""
    tool = OrderTool()
    result = await tool.execute(
        {"order_id": "ORD-9001"},
        context=analyst_context,
        session=db_session,
    )
    assert result["order_id"] == "ORD-9001"
    assert result["customer_id"] == "CUST-1001"
    assert result["total_amount"] == 50000.0


@pytest.mark.asyncio
async def test_system_status_tool_integration(
    db_session: AsyncSession, admin_context: UserContext
) -> None:
    """Test SystemStatusTool reporting database latency."""
    tool = SystemStatusTool()
    result = await tool.execute(
        {},
        context=admin_context,
        session=db_session,
    )
    assert result["status"] == "healthy"
    assert "dependencies" in result


@pytest.mark.asyncio
async def test_calculate_kpi_tool_integration(
    db_session: AsyncSession, analyst_context: UserContext
) -> None:
    """Test CalculateKpiTool calculating total revenue."""
    tool = CalculateKpiTool()
    result = await tool.execute(
        {"metric_name": "revenue", "period": "last_month"},
        context=analyst_context,
        session=db_session,
    )
    assert result["metric"] == "Total Revenue"
    assert result["value"] == 50000.0
