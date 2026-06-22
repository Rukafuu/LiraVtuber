"""
Entrypoint: python apps/mcp_gateway/main.py

MCP Gateway HTTP na porta 8045 (subprocessos Node MCP).
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
_CORE_PKG = ROOT / "packages" / "lira-core"
if _CORE_PKG.is_dir() and str(_CORE_PKG) not in sys.path:
    sys.path.insert(0, str(_CORE_PKG))

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

load_dotenv(ROOT / ".env", encoding="utf-8-sig")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("mcp_gateway")

from apps.mcp_gateway.config import load_allowlist, load_servers, save_allowlist, save_servers
from apps.mcp_gateway.pool import pool


def _win_asyncio_exception_handler(loop: asyncio.AbstractEventLoop, context: dict) -> None:
    """Windows: cliente HTTP que fecha antes da resposta (HUD/proxy) gera 10054 ruidoso."""
    exc = context.get("exception")
    if isinstance(exc, ConnectionResetError):
        logger.debug("[MCP Gateway] cliente desconectou: %s", context.get("message", ""))
        return
    loop.default_exception_handler(context)


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    if sys.platform == "win32":
        asyncio.get_running_loop().set_exception_handler(_win_asyncio_exception_handler)
    yield
    await asyncio.to_thread(pool.stop_all)


app = FastAPI(title="Lira MCP Gateway", version="1.0", lifespan=_lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class McpCallerPayload(BaseModel):
    channel: str = ""
    user_id: str = ""
    user_name: str = ""
    jid: str = ""
    is_owner: bool | None = None


class McpCallRequest(BaseModel):
    server: str
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    caller: McpCallerPayload | None = None


class AllowlistUpdate(BaseModel):
    allowed: list[str]


class ServerToggle(BaseModel):
    enabled: bool


@app.get("/health")
async def health():
    return {"status": "ok", "service": "mcp_gateway"}


@app.get("/mcp/status")
async def mcp_status():
    return await asyncio.to_thread(pool.status)


@app.get("/mcp/servers")
async def mcp_servers():
    servers = load_servers()
    st = (await asyncio.to_thread(pool.status))["servers"]
    by_id = {s["id"]: s for s in st}
    items = []
    for sid, cfg in servers.items():
        run = by_id.get(sid, {})
        items.append({**cfg, "id": sid, "running": run.get("running", False)})
    return {"servers": items}


@app.patch("/mcp/servers/{server_id}")
async def mcp_server_toggle(server_id: str, body: ServerToggle):
    servers = load_servers()
    if server_id not in servers:
        raise HTTPException(404, "Servidor não encontrado")
    servers[server_id]["enabled"] = body.enabled
    save_servers(servers)
    if not body.enabled:
        await asyncio.to_thread(pool.stop_server, server_id)
    return {"status": "ok", "server_id": server_id, "enabled": body.enabled}


@app.get("/mcp/tools")
async def mcp_tools(server: str | None = None, refresh: bool = False):
    if server:
        try:
            tools = await asyncio.to_thread(pool.list_tools, server, refresh)
        except Exception as e:
            raise HTTPException(400, str(e)) from e
        return {"server": server, "tools": tools}
    return {"discovery": await asyncio.to_thread(pool.discover_all)}


@app.get("/mcp/allowlist")
async def mcp_get_allowlist():
    return load_allowlist()


@app.put("/mcp/allowlist")
async def mcp_put_allowlist(body: AllowlistUpdate):
    data = load_allowlist()
    data["allowed"] = body.allowed
    save_allowlist(data)
    return data


@app.post("/mcp/call")
async def mcp_call(body: McpCallRequest):
    try:
        from lira_core.tools.mcp_access import check_mcp_server_access

        denied = check_mcp_server_access(
            body.server,
            body.caller.model_dump() if body.caller else None,
        )
        if denied:
            raise PermissionError(denied[0])

        text = await asyncio.to_thread(pool.call, body.server, body.tool, body.arguments)

        if body.server.strip().lower() == "tavily":
            from lira_core.tools.mcp_access import spend_tavily_gems

            spend_tavily_gems(body.caller.model_dump() if body.caller else None)

        return {
            "status": "ok",
            "server": body.server,
            "tool": body.tool,
            "result": text,
        }
    except PermissionError as e:
        raise HTTPException(403, str(e)) from e
    except KeyError as e:
        raise HTTPException(404, str(e)) from e
    except Exception as e:
        logger.exception("[MCP] call %s/%s", body.server, body.tool)
        raise HTTPException(500, str(e)) from e


def main():
    host = os.getenv("MCP_GATEWAY_HOST", "127.0.0.1")
    port = int(os.getenv("MCP_GATEWAY_PORT", "8045"))
    print(f"[MCP Gateway] http://{host}:{port}", flush=True)
    uvicorn.run(app, host=host, port=port, log_level="info", loop="asyncio")


if __name__ == "__main__":
    main()