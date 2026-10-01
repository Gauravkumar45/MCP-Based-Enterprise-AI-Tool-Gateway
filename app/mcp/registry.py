"""Enterprise tool registry managing discovery, authorization, validation, and execution."""

import asyncio
import time
import uuid
from typing import Any

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import UserContext
from app.core.errors import (
    AuthorizationError,
    ErrorCode,
    GatewayException,
    InvalidToolInputError,
    ToolNotFoundError,
    ToolTimeoutError,
)
from app.core.logging import logger, request_id_ctx, tool_name_ctx, user_id_ctx
from app.schemas.common import ToolMetadata
from app.services.audit import AuditService
from app.services.rate_limit import RateLimiter
from app.tools.base import BaseEnterpriseTool


class ToolRegistry:
    """Central registry and policy enforcement engine for enterprise tools."""

    def __init__(
        self,
        audit_service: AuditService | None = None,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        self._tools: dict[str, BaseEnterpriseTool] = {}
        self.audit_service = audit_service or AuditService()
        self.rate_limiter = rate_limiter or RateLimiter()

    def register_tool(self, tool: BaseEnterpriseTool) -> None:
        """Register a new enterprise tool."""
        self._tools[tool.name] = tool
        logger.info(
            "Registered tool: %s (permission: %s, risk: %s)",
            tool.name,
            tool.required_permission,
            tool.risk_level,
        )

    def unregister_tool(self, tool_name: str) -> None:
        """Unregister an existing tool."""
        if tool_name in self._tools:
            del self._tools[tool_name]
            logger.info("Unregistered tool: %s", tool_name)

    def get_tool(self, tool_name: str) -> BaseEnterpriseTool:
        """Retrieve tool by name, raising ToolNotFoundError if missing."""
        tool = self._tools.get(tool_name)
        if not tool:
            raise ToolNotFoundError(tool_name=tool_name)
        return tool

    def list_tools(self, user_context: UserContext | None = None) -> list[ToolMetadata]:
        """Discover tools. If user_context is provided, filters by user permissions."""
        discovered: list[ToolMetadata] = []
        for tool in self._tools.values():
            if user_context is None or user_context.has_permission(tool.required_permission):
                discovered.append(tool.get_metadata())
        return discovered

    def authorize_tool(self, tool: BaseEnterpriseTool, user_context: UserContext) -> None:
        """Enforce strict RBAC policy before tool invocation."""
        if not user_context.has_permission(tool.required_permission):
            raise AuthorizationError(
                message=f"User '{user_context.username}' lacks required permission '{tool.required_permission}' for tool '{tool.name}'",
                details={
                    "user_id": user_context.user_id,
                    "tool_name": tool.name,
                    "required_permission": tool.required_permission,
                    "user_permissions": user_context.permissions,
                },
            )

    async def execute_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        user_context: UserContext,
        session: AsyncSession,
        request_id: str | None = None,
        agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Full enterprise tool execution pipeline:

        1. Lookup tool in registry
        2. Set contextual tracing vars
        3. Authorize user permissions (RBAC)
        4. Enforce rate limiting
        5. Validate strongly typed input schema
        6. Execute with configurable timeout
        7. Persist audit log
        8. Return structured output
        """
        req_id = request_id or str(uuid.uuid4())
        request_id_ctx.set(req_id)
        user_id_ctx.set(user_context.user_id)
        tool_name_ctx.set(tool_name)

        t0 = time.perf_counter()
        status = "SUCCESS"
        error_code = None
        error_message = None
        result_data: dict[str, Any] = {}

        try:
            # Step 1: Tool Lookup
            tool = self.get_tool(tool_name)

            # Step 2: Tool-Level Authorization
            self.authorize_tool(tool, user_context)

            # Step 3: Rate Limiting
            await self.rate_limiter.check_rate_limit(
                identifier=user_context.user_id,
                tool_name=tool_name,
            )

            # Step 4: Input Validation
            try:
                validated_params = tool.input_model.model_validate(arguments)
                valid_args = validated_params.model_dump()
            except ValidationError as ve:
                raise InvalidToolInputError(
                    message=f"Input validation failed for tool '{tool_name}': {ve.errors()}",
                    details={"validation_errors": ve.errors()},
                ) from ve

            # Step 5: Execution under hard timeout
            try:
                result_data = await asyncio.wait_for(
                    tool.execute(valid_args, user_context, session),
                    timeout=float(tool.timeout_seconds),
                )
            except TimeoutError as te:
                raise ToolTimeoutError(
                    tool_name=tool_name, timeout_seconds=tool.timeout_seconds
                ) from te

            return result_data

        except GatewayException as ge:
            status = "DENIED" if isinstance(ge, AuthorizationError) else "FAILED"
            error_code = ge.code.value
            error_message = ge.message
            raise

        except Exception as exc:
            status = "FAILED"
            error_code = ErrorCode.INTERNAL_ERROR.value
            error_message = str(exc)
            raise

        finally:
            latency_ms = (time.perf_counter() - t0) * 1000
            # Step 6: Immutable Audit Logging in PostgreSQL
            try:
                await self.audit_service.log_tool_invocation(
                    request_id=req_id,
                    tool_name=tool_name,
                    execution_status=status,
                    latency_ms=latency_ms,
                    user_id=user_context.user_id,
                    agent_id=agent_id,
                    raw_inputs=arguments,
                    error_code=error_code,
                    result_summary=str(result_data)[:200] if result_data else None,
                    error_message=error_message,
                )
            except Exception as audit_err:
                logger.error("Audit log persistence failed: %s", audit_err)


def create_default_registry() -> ToolRegistry:
    """Instantiate and register all default enterprise tools."""
    from app.tools.customer import CustomerTool
    from app.tools.database import DatabaseQueryTool
    from app.tools.documents import DocumentSearchTool
    from app.tools.invoice import InvoiceTool
    from app.tools.kpi import CalculateKpiTool
    from app.tools.order import OrderTool
    from app.tools.system import SystemStatusTool

    registry = ToolRegistry()
    registry.register_tool(DatabaseQueryTool())
    registry.register_tool(DocumentSearchTool())
    registry.register_tool(CustomerTool())
    registry.register_tool(InvoiceTool())
    registry.register_tool(OrderTool())
    registry.register_tool(SystemStatusTool())
    registry.register_tool(CalculateKpiTool())
    return registry
