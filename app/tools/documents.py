"""Enterprise document search tool supporting keyword and vector abstractions."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import UserContext
from app.auth.permissions import PermissionName
from app.schemas.tools import DocumentSearchRequest, DocumentSearchResponse
from app.services.document_service import DocumentService
from app.tools.base import BaseEnterpriseTool


class DocumentSearchTool(BaseEnterpriseTool):
    """MCP tool for querying indexed corporate documentation."""

    name = "search_documents"
    description = (
        "Search enterprise documents and knowledge base using keyword and vector abstractions"
    )
    required_permission = PermissionName.DOCUMENTS_SEARCH.value
    risk_level = "low"
    timeout_seconds = 5
    input_model = DocumentSearchRequest
    output_model = DocumentSearchResponse

    async def execute(
        self,
        arguments: dict[str, Any],
        context: UserContext,
        session: AsyncSession,
    ) -> dict[str, Any]:
        params = self.input_model.model_validate(arguments)
        doc_service = DocumentService(session)
        result = await doc_service.search_documents(
            query=params.query,
            top_k=params.top_k,
            category=params.category,
        )
        return result
