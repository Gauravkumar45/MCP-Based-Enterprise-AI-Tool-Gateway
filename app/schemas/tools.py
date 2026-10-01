"""Strongly-typed Pydantic v2 schemas for MCP tool inputs and outputs."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class DatabaseQueryRequest(BaseModel):
    """Input payload for query_database tool."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(..., min_length=5, description="Safe read-only SELECT SQL query to execute")
    limit: int = Field(
        default=100, ge=1, le=1000, description="Maximum number of rows to return (capped at 1000)"
    )
    timeout_seconds: int = Field(
        default=10, ge=1, le=30, description="Query execution timeout in seconds"
    )


class DatabaseQueryResponse(BaseModel):
    """Output payload for query_database tool."""

    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    limit_applied: int
    execution_time_ms: float
    sanitized_query: str


class DocumentSearchRequest(BaseModel):
    """Input payload for search_documents tool."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(..., min_length=2, max_length=200, description="Search terms or keywords")
    top_k: int = Field(
        default=5, ge=1, le=20, description="Maximum number of relevant documents to retrieve"
    )
    category: str | None = Field(default=None, description="Optional document category filter")


class DocumentItem(BaseModel):
    """Single scored document search match."""

    document_id: str
    title: str
    content: str
    score: float
    source: str
    category: str | None = None


class DocumentSearchResponse(BaseModel):
    """Output payload for search_documents tool."""

    results: list[DocumentItem]
    query: str
    total_found: int


class GetCustomerRequest(BaseModel):
    """Input payload for get_customer tool."""

    model_config = ConfigDict(extra="forbid")

    customer_id: str | None = Field(
        default=None, description="Unique customer identifier (e.g. CUST-1001)"
    )
    email: str | None = Field(default=None, description="Customer email address")


class CustomerResponse(BaseModel):
    """Output payload for get_customer tool."""

    customer_id: str
    name: str
    email: str
    tier: str
    lifetime_value: float
    status: str
    created_at: str | None = None


class GetInvoiceRequest(BaseModel):
    """Input payload for get_invoice tool."""

    model_config = ConfigDict(extra="forbid")

    invoice_id: str = Field(..., min_length=3, description="Invoice identifier (e.g. INV-2024-001)")


class InvoiceResponse(BaseModel):
    """Output payload for get_invoice tool."""

    invoice_id: str
    customer_id: str
    amount: float
    currency: str
    status: str
    due_date: str | None = None
    issued_date: str | None = None


class GetOrderRequest(BaseModel):
    """Input payload for get_order tool."""

    model_config = ConfigDict(extra="forbid")

    order_id: str = Field(..., min_length=3, description="Order identifier (e.g. ORD-9001)")


class OrderResponse(BaseModel):
    """Output payload for get_order tool."""

    order_id: str
    customer_id: str
    total_amount: float
    status: str
    items_count: int
    tracking_number: str | None = None
    created_at: str | None = None


class GetSystemStatusRequest(BaseModel):
    """Input payload for get_system_status tool."""

    model_config = ConfigDict(extra="forbid")

    component: Literal["database", "redis"] | None = Field(
        default=None, description="Optional specific component check"
    )


class SystemStatusResponse(BaseModel):
    """Output payload for get_system_status tool."""

    status: str
    uptime_seconds: float
    environment: str
    python_version: str
    dependencies: dict[str, Any]


class CalculateKpiRequest(BaseModel):
    """Input payload for calculate_kpi tool."""

    model_config = ConfigDict(extra="forbid")

    metric_name: str = Field(
        ...,
        description="KPI to calculate: 'revenue', 'mrr', 'aov', 'active_customers', 'churn_rate'",
    )
    period: str = Field(
        default="last_month", description="Reporting period (e.g. 'last_month', 'q3', 'ytd')"
    )


class CalculateKpiResponse(BaseModel):
    """Output payload for calculate_kpi tool."""

    metric: str
    value: float | int | None
    currency: str | None = None
    unit: str | None = None
    period: str
    trend: str | None = None
    error: str | None = None
