"""Enterprise Model Context Protocol (MCP) Server implementing standard protocol specs."""

import contextvars
import inspect
import uuid
from typing import Any

from mcp.server.mcpserver import Context, MCPServer

from app.auth.models import UserContext
from app.core.config import get_settings
from app.core.errors import AuthenticationError, GatewayException
from app.core.logging import logger, request_id_ctx, user_id_ctx
from app.core.security import decode_access_token
from app.database.session import session_scope
from app.mcp.registry import ToolRegistry, create_default_registry
from app.tools.base import BaseEnterpriseTool

# Context variable to support in-process and agent-propagated user contexts
current_mcp_user_ctx: contextvars.ContextVar[UserContext | None] = contextvars.ContextVar(
    "current_mcp_user", default=None
)
current_agent_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_agent_id", default=None
)


def extract_user_context_from_mcp(ctx: Context | None = None) -> UserContext:
    """Extract authenticated UserContext from MCP context headers or ambient contextvar."""
    # 1. Ambient contextvar (from agent or request scope)
    ambient_user = current_mcp_user_ctx.get()
    if ambient_user is not None:
        return ambient_user

    # 2. Extract from MCP HTTP headers
    if ctx and hasattr(ctx, "headers") and ctx.headers:
        auth_header = ctx.headers.get("authorization") or ctx.headers.get("Authorization")
        if auth_header and auth_header.lower().startswith("bearer "):
            token = auth_header[7:].strip()
            payload = decode_access_token(token)
            return UserContext(
                user_id=str(payload.get("sub", "")),
                username=str(payload.get("username", "")),
                roles=list(payload.get("roles", [])),
                permissions=list(payload.get("permissions", [])),
                token=token,
            )

    raise AuthenticationError(
        message="Authentication required: No valid Bearer token provided in MCP request",
        details={"hint": "Provide 'Authorization: Bearer <jwt_token>' header"},
    )


class EnterpriseMCPServer:
    """Enterprise MCP Gateway server managing protocol transport and policy execution."""

    def __init__(self, registry: ToolRegistry | None = None) -> None:
        settings = get_settings()
        self.registry = registry or create_default_registry()
        self.mcp = MCPServer(
            name=settings.MCP_SERVER_NAME,
            version=settings.MCP_SERVER_VERSION,
        )
        self._register_mcp_tools()

    def _register_mcp_tools(self) -> None:
        """Dynamically bind all registered tools from ToolRegistry to the MCP Server."""
        for tool_name, tool in self.registry._tools.items():
            self._bind_tool(tool_name, tool)

    def _bind_tool(self, tool_name: str, tool: BaseEnterpriseTool) -> None:
        """Create and bind an MCP tool handler with dynamic signature matching the tool's Pydantic model."""

        async def _handler(ctx: Context, **kwargs: Any) -> dict[str, Any]:
            request_id = str(uuid.uuid4())
            request_id_ctx.set(request_id)

            try:
                # 1. Extract user context
                user_context = extract_user_context_from_mcp(ctx)
                user_id_ctx.set(user_context.user_id)
                agent_id = current_agent_id_ctx.get()

                # 2. Execute within database session scope
                async with session_scope() as session:
                    result = await self.registry.execute_tool(
                        tool_name=tool_name,
                        arguments=kwargs,
                        user_context=user_context,
                        session=session,
                        request_id=request_id,
                        agent_id=agent_id,
                    )
                    return result

            except GatewayException as ge:
                logger.warning(
                    "Gateway error during MCP tool execution '%s': %s", tool_name, ge.to_dict()
                )
                return ge.to_dict()
            except Exception as e:
                logger.error("Unexpected error in MCP tool '%s': %s", tool_name, e, exc_info=True)
                return {
                    "error": "INTERNAL_ERROR",
                    "message": f"Tool execution failed: {e!s}",
                }

        # Build dynamic inspect.Signature from tool.input_model so MCP reflects accurate schema
        params = [
            inspect.Parameter("ctx", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=Context)
        ]
        for f_name, f_info in tool.input_model.model_fields.items():
            default_val = inspect.Parameter.empty if f_info.is_required() else f_info.default
            params.append(
                inspect.Parameter(
                    f_name,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    default=default_val,
                    annotation=f_info.annotation,
                )
            )

        _handler.__signature__ = inspect.Signature(params)  # type: ignore[attr-defined]
        _handler.__name__ = tool_name
        _handler.__doc__ = tool.description

        # Register on MCPServer
        self.mcp.add_tool(
            _handler,
            name=tool.name,
            description=tool.description,
            meta=tool.to_mcp_meta(),
        )

    def get_sse_app(self) -> Any:
        """Return ASGI application for mounting MCP SSE transport."""
        return self.mcp.sse_app()


_server_instance: EnterpriseMCPServer | None = None


def get_mcp_server() -> EnterpriseMCPServer:
    """Singleton getter for the Enterprise MCP Server."""
    global _server_instance
    if _server_instance is None:
        _server_instance = EnterpriseMCPServer()
    return _server_instance
