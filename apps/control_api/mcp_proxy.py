"""Proxy HTTP Control API (8042) → MCP Gateway (8045)."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


def _base() -> str:
    return os.getenv("MCP_GATEWAY_URL", "http://127.0.0.1:8045").rstrip("/")


def _request(method: str, path: str, body: dict | None = None, timeout: float = 30.0) -> Any:
    url = f"{_base()}{path}"
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(detail)
        except json.JSONDecodeError:
            parsed = {"detail": detail}
        return {"status": "error", "http_status": e.code, **parsed}
    except Exception as e:
        return {"status": "error", "message": str(e), "gateway": _base()}


def get_status() -> dict:
    return _request("GET", "/mcp/status")


def get_servers() -> dict:
    return _request("GET", "/mcp/servers")


def patch_server(server_id: str, enabled: bool) -> dict:
    return _request("PATCH", f"/mcp/servers/{server_id}", {"enabled": enabled})


def get_tools(server: str | None = None, refresh: bool = False) -> dict:
    q = f"?refresh=true" if refresh else ""
    if server:
        return _request("GET", f"/mcp/tools?server={server}{'&refresh=true' if refresh else ''}")
    return _request("GET", f"/mcp/tools{q}")


def get_allowlist() -> dict:
    return _request("GET", "/mcp/allowlist")


def put_allowlist(allowed: list[str]) -> dict:
    return _request("PUT", "/mcp/allowlist", {"allowed": allowed})


def post_call(server: str, tool: str, arguments: dict) -> dict:
    return _request(
        "POST",
        "/mcp/call",
        {
            "server": server,
            "tool": tool,
            "arguments": arguments,
            "caller": {
                "channel": "control_center",
                "is_owner": True,
            },
        },
        timeout=55.0,
    )