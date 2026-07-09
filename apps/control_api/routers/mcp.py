import asyncio
import logging
from fastapi import APIRouter
from pydantic import BaseModel

from apps.control_api import mcp_proxy

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mcp", tags=["mcp"])


class McpAllowlistBody(BaseModel):
    allowed: list[str]


class McpServerToggleBody(BaseModel):
    enabled: bool


class McpCallBody(BaseModel):
    server: str
    tool: str
    arguments: dict | None = None


@router.get("/status")
async def api_mcp_status():
    return await asyncio.to_thread(mcp_proxy.get_status)


@router.get("/servers")
async def api_mcp_servers():
    return await asyncio.to_thread(mcp_proxy.get_servers)


@router.patch("/servers/{server_id}")
async def api_mcp_server_toggle(server_id: str, body: McpServerToggleBody):
    return await asyncio.to_thread(mcp_proxy.patch_server, server_id, body.enabled)


@router.get("/tools")
async def api_mcp_tools(server: str | None = None, refresh: bool = False):
    return await asyncio.to_thread(mcp_proxy.get_tools, server, refresh)


@router.get("/allowlist")
async def api_mcp_allowlist():
    return await asyncio.to_thread(mcp_proxy.get_allowlist)


@router.put("/allowlist")
async def api_mcp_allowlist_put(body: McpAllowlistBody):
    return await asyncio.to_thread(mcp_proxy.put_allowlist, body.allowed)


@router.post("/call")
async def api_mcp_call(body: McpCallBody):
    return await asyncio.to_thread(
        mcp_proxy.post_call, body.server, body.tool, body.arguments or {}
    )
