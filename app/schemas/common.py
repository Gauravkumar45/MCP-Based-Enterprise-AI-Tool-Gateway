"""Common API request/response models."""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """Standard unified response wrapper for REST APIs."""

    success: bool = True
    data: T | None = None
    error: str | None = None
    message: str | None = None


class ToolMetadata(BaseModel):
    """MCP tool metadata model."""

    name: str
    description: str
    required_permission: str
    risk_level: str = Field(..., description="low, medium, high")
    timeout_seconds: int = 10
    input_schema: dict[str, Any]
    output_schema: dict[str, Any] | None = None


class HealthResponse(BaseModel):
    """Health check response schema."""

    status: str
    service: str
    version: str
    timestamp: str
