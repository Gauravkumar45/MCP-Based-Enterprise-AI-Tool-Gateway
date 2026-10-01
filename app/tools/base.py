"""Base class definition for enterprise tools."""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import UserContext
from app.schemas.common import ToolMetadata


class BaseEnterpriseTool(ABC):
    """Abstract base class for all enterprise gateway tools."""

    name: str
    description: str
    required_permission: str
    risk_level: str  # "low", "medium", "high"
    timeout_seconds: int = 10
    input_model: type[BaseModel]
    output_model: type[BaseModel]

    @abstractmethod
    async def execute(
        self,
        arguments: dict[str, Any],
        context: UserContext,
        session: AsyncSession,
    ) -> dict[str, Any]:
        """Execute the tool operation against services and repositories."""
        pass

    def get_metadata(self) -> ToolMetadata:
        """Export standardized tool discovery metadata."""
        return ToolMetadata(
            name=self.name,
            description=self.description,
            required_permission=self.required_permission,
            risk_level=self.risk_level,
            timeout_seconds=self.timeout_seconds,
            input_schema=self.input_model.model_json_schema(),
            output_schema=self.output_model.model_json_schema() if self.output_model else None,
        )

    def to_mcp_meta(self) -> dict[str, Any]:
        """Metadata attached to MCP protocol tool definition."""
        return {
            "required_permission": self.required_permission,
            "risk_level": self.risk_level,
            "timeout_seconds": self.timeout_seconds,
        }
