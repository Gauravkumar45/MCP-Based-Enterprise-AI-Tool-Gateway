"""Enterprise database query tool with strict read-only and AST validation."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import UserContext
from app.auth.permissions import PermissionName
from app.schemas.tools import DatabaseQueryRequest, DatabaseQueryResponse
from app.services.database_service import DatabaseService
from app.tools.base import BaseEnterpriseTool


class DatabaseQueryTool(BaseEnterpriseTool):
    """MCP tool for executing verified, read-only SQL queries."""

    name = "query_database"
    description = "Execute an approved read-only database query with AST safety verification"
    required_permission = PermissionName.DATABASE_READ.value
    risk_level = "medium"
    timeout_seconds = 10
    input_model = DatabaseQueryRequest
    output_model = DatabaseQueryResponse

    async def execute(
        self,
        arguments: dict[str, Any],
        context: UserContext,
        session: AsyncSession,
    ) -> dict[str, Any]:
        params = self.input_model.model_validate(arguments)
        db_service = DatabaseService(session)
        result = await db_service.execute_query(
            query=params.query,
            limit=params.limit,
            timeout_seconds=params.timeout_seconds,
        )
        return result
