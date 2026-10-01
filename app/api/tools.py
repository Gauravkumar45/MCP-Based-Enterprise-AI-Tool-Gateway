"""Management REST API for tool discovery and execution inspection."""

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import get_current_user_context
from app.auth.models import UserContext
from app.core.errors import GatewayException
from app.database.session import get_db
from app.mcp.server import get_mcp_server
from app.schemas.common import ToolMetadata

router = APIRouter(prefix="/tools", tags=["Tool Management"])


@router.get("", response_model=list[ToolMetadata], summary="List Authorized Tools")
async def list_tools(user: UserContext = Depends(get_current_user_context)) -> list[ToolMetadata]:
    """Discover all enterprise tools authorized for the calling user's permissions."""
    mcp_server = get_mcp_server()
    return mcp_server.registry.list_tools(user_context=user)


@router.get("/{tool_name}", response_model=ToolMetadata, summary="Get Tool Details")
async def get_tool_details(
    tool_name: str,
    user: UserContext = Depends(get_current_user_context),
) -> ToolMetadata:
    """Retrieve metadata and schema for a specific enterprise tool."""
    mcp_server = get_mcp_server()
    try:
        tool = mcp_server.registry.get_tool(tool_name)
        # Check authorization to inspect tool
        mcp_server.registry.authorize_tool(tool, user)
        return tool.get_metadata()
    except GatewayException as ge:
        raise HTTPException(status_code=ge.status_code, detail=ge.to_dict()) from ge


@router.post("/{tool_name}/execute", summary="Execute Tool via Gateway")
async def execute_tool_endpoint(
    tool_name: str,
    payload: dict[str, Any] = Body(default_factory=dict),
    user: UserContext = Depends(get_current_user_context),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Execute tool through the gateway pipeline (RBAC check, rate limiting, validation, execution, and audit log)."""
    mcp_server = get_mcp_server()
    arguments = payload.get("arguments", payload)
    try:
        result = await mcp_server.registry.execute_tool(
            tool_name=tool_name,
            arguments=arguments,
            user_context=user,
            session=db,
        )
        return result
    except GatewayException as ge:
        raise HTTPException(status_code=ge.status_code, detail=ge.to_dict()) from ge
