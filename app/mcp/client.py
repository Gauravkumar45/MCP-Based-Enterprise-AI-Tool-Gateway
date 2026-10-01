"""Enterprise MCP Client for AI agent tool discovery and execution."""

import json
import uuid
from typing import Any, cast

import httpx

from app.auth.models import UserContext
from app.core.errors import GatewayException
from app.core.logging import logger
from app.core.security import decode_access_token
from app.mcp.server import (
    EnterpriseMCPServer,
    current_agent_id_ctx,
    current_mcp_user_ctx,
    get_mcp_server,
)


class EnterpriseMCPClient:
    """Client for connecting to the Enterprise MCP Gateway.

    Supports both in-process high-performance execution and remote HTTP/SSE transport.
    Ensures AI agents access services strictly via MCP protocol abstraction.
    """

    def __init__(
        self,
        token: str,
        server: EnterpriseMCPServer | None = None,
        base_url: str | None = None,
        agent_id: str | None = None,
    ) -> None:
        self.token = token
        self.agent_id = agent_id or f"agent-{uuid.uuid4().hex[:8]}"
        self.server = server or get_mcp_server()
        self.base_url = base_url
        self._cached_user_context: UserContext | None = None

    def _get_user_context(self) -> UserContext:
        """Decode and cache user context from bearer token."""
        if self._cached_user_context is None:
            payload = decode_access_token(self.token)
            self._cached_user_context = UserContext(
                user_id=str(payload.get("sub", "")),
                username=str(payload.get("username", "")),
                roles=list(payload.get("roles", [])),
                permissions=list(payload.get("permissions", [])),
                token=self.token,
            )
        return self._cached_user_context

    async def list_tools(self) -> list[dict[str, Any]]:
        """Discover tools available via the MCP gateway.

        Returns only tools authorized for the client's current credentials.
        """
        user_ctx = self._get_user_context()
        metadata_list = self.server.registry.list_tools(user_context=user_ctx)
        return [
            {
                "name": meta.name,
                "description": meta.description,
                "required_permission": meta.required_permission,
                "risk_level": meta.risk_level,
                "timeout_seconds": meta.timeout_seconds,
                "input_schema": meta.input_schema,
                "output_schema": meta.output_schema,
            }
            for meta in metadata_list
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute a tool via the MCP Gateway.

        Propagates user identity, enforces RBAC, rate-limits, validates, and logs execution.
        """
        user_ctx = self._get_user_context()

        # Set ambient context variables for in-process MCP bridge
        token_ctx = current_mcp_user_ctx.set(user_ctx)
        agent_ctx = current_agent_id_ctx.set(self.agent_id)

        try:
            # If a remote base_url is specified, execute via HTTP/REST bridge
            if self.base_url:
                async with httpx.AsyncClient(timeout=30.0) as http_client:
                    resp = await http_client.post(
                        f"{self.base_url.rstrip('/')}/tools/{name}/execute",
                        json={"arguments": arguments},
                        headers={"Authorization": f"Bearer {self.token}"},
                    )
                    return cast(dict[str, Any], resp.json())

            # In-process MCP execution path:
            # Call tool through the MCP Server interface
            call_result = await self.server.mcp.call_tool(name=name, arguments=arguments)

            # Check if structured result or TextContent was returned
            if hasattr(call_result, "content") and call_result.content:
                first = call_result.content[0]
                if hasattr(first, "text"):
                    try:
                        return cast(dict[str, Any], json.loads(first.text))
                    except Exception:
                        return {"result": first.text}

            if hasattr(call_result, "structured_content") and call_result.structured_content:
                return cast(dict[str, Any], call_result.structured_content)

            return {"result": str(call_result)}

        except GatewayException as ge:
            return ge.to_dict()
        except Exception as e:
            logger.error("Client call_tool failed for '%s': %s", name, e)
            return {"error": "TOOL_EXECUTION_FAILED", "message": str(e)}
        finally:
            current_mcp_user_ctx.reset(token_ctx)
            current_agent_id_ctx.reset(agent_ctx)
