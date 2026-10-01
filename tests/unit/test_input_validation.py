"""Unit tests for strongly typed Pydantic v2 tool input schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.tools import (
    CalculateKpiRequest,
    DatabaseQueryRequest,
    DocumentSearchRequest,
    GetInvoiceRequest,
    GetOrderRequest,
)


def test_database_query_request_valid() -> None:
    """Test valid database query request."""
    req = DatabaseQueryRequest(query="SELECT 1", limit=10, timeout_seconds=5)
    assert req.limit == 10
    assert req.timeout_seconds == 5


def test_database_query_request_excessive_limit() -> None:
    """Test that limits above 1000 fail validation."""
    with pytest.raises(ValidationError):
        DatabaseQueryRequest(query="SELECT 1", limit=2000)


def test_database_query_request_extra_field_forbidden() -> None:
    """Test that extra unmapped fields are forbidden."""
    with pytest.raises(ValidationError):
        DatabaseQueryRequest(query="SELECT 1", malicious_extra="injected_payload")  # type: ignore[call-arg]


def test_document_search_request_validation() -> None:
    """Test document search schema constraints."""
    # Min length check (query must be at least 2 chars)
    with pytest.raises(ValidationError):
        DocumentSearchRequest(query="a")

    # Valid search
    valid_req = DocumentSearchRequest(query="security policy", top_k=10)
    assert valid_req.top_k == 10


def test_invoice_and_order_request_validation() -> None:
    """Test invoice and order id minimum length validation."""
    with pytest.raises(ValidationError):
        GetInvoiceRequest(invoice_id="1")

    valid_inv = GetInvoiceRequest(invoice_id="INV-001")
    assert valid_inv.invoice_id == "INV-001"

    valid_ord = GetOrderRequest(order_id="ORD-001")
    assert valid_ord.order_id == "ORD-001"


def test_kpi_request_validation() -> None:
    """Test KPI calculation parameter schema."""
    req = CalculateKpiRequest(metric_name="revenue", period="q3")
    assert req.metric_name == "revenue"
    assert req.period == "q3"
