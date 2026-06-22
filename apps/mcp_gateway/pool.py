"""Pool de sessões MCP (um subprocesso por servidor habilitado)."""
from __future__ import annotations

import logging
import shutil
import sys
import threading
from typing import Any

from apps.mcp_gateway.config import is_allowed, load_allowlist, load_servers, resolve_env_map
from apps.mcp_gateway.mcp_stdio import McpStdioSession

logger = logging.getLogger(__name__)


def _resolve_command(command: list[str]) -> list[str]:
    """Windows: npx/node precisam de .cmd ou caminho absoluto."""
    if not command:
        return command
    out = list(command)
    exe = out[0]
    if exe in ("npx", "node", "npm"):
        found = None
        if sys.platform == "win32":
            found = shutil.which(f"{exe}.cmd")
        found = found or shutil.which(exe)
        if not found:
            raise FileNotFoundError(
                f"'{exe}' não encontrado no PATH. Instale Node.js: https://nodejs.org/"
            )
        out[0] = found
    return out


class McpGatewayPool:
    def __init__(self):
        self._sessions: dict[str, McpStdioSession] = {}
        self._lock = threading.RLock()

    def _get_server_cfg(self, server_id: str) -> dict[str, Any]:
        servers = load_servers()
        cfg = servers.get(server_id)
        if not cfg:
            raise KeyError(f"servidor MCP desconhecido: {server_id}")
        return cfg

    def _session(self, server_id: str) -> McpStdioSession:
        with self._lock:
            stale = self._sessions.get(server_id)
            if stale and not stale.running:
                try:
                    stale.stop()
                except Exception:
                    pass
                self._sessions.pop(server_id, None)
            if server_id in self._sessions and self._sessions[server_id].running:
                return self._sessions[server_id]

            cfg = self._get_server_cfg(server_id)
            if not cfg.get("enabled"):
                raise RuntimeError(f"servidor '{server_id}' está desligado no painel")

            command = list(cfg.get("command") or [])
            if not command:
                raise RuntimeError(f"comando vazio para '{server_id}'")
            command = _resolve_command(command)

            env = resolve_env_map(cfg.get("env"))
            cwd = cfg.get("cwd")
            session = McpStdioSession(server_id, command, env=env, cwd=cwd)
            session.start()
            self._sessions[server_id] = session
            return session

    def stop_server(self, server_id: str) -> None:
        with self._lock:
            sess = self._sessions.pop(server_id, None)
            if sess:
                sess.stop()

    def stop_all(self) -> None:
        with self._lock:
            for sid in list(self._sessions):
                self._sessions[sid].stop()
            self._sessions.clear()

    def status(self) -> dict[str, Any]:
        servers = load_servers()
        out = []
        for sid, cfg in servers.items():
            sess = self._sessions.get(sid)
            out.append(
                {
                    "id": sid,
                    "label": cfg.get("label", sid),
                    "enabled": bool(cfg.get("enabled")),
                    "planned": bool(cfg.get("planned")),
                    "running": bool(sess and sess.running),
                    "last_error": sess.last_error if sess else None,
                }
            )
        return {"servers": out, "gateway": "ok"}

    def list_tools(self, server_id: str, refresh: bool = False) -> list[dict]:
        try:
            sess = self._session(server_id)
            tools = sess.list_tools(refresh=refresh)
        except Exception as e:
            logger.warning("[MCP] list_tools %s falhou, reiniciando sessao: %s", server_id, e)
            self.stop_server(server_id)
            sess = self._session(server_id)
            tools = sess.list_tools(refresh=refresh)
        normalized = []
        for t in tools:
            name = t.get("name", "")
            normalized.append(
                {
                    "name": name,
                    "qualified": f"{server_id}/{name}",
                    "description": (t.get("description") or "")[:400],
                    "inputSchema": t.get("inputSchema"),
                }
            )
        return normalized

    def discover_all(self) -> dict[str, list[dict]]:
        servers = load_servers()
        result: dict[str, list[dict]] = {}
        for sid, cfg in servers.items():
            if not cfg.get("enabled"):
                continue
            try:
                result[sid] = self.list_tools(sid, refresh=True)
            except Exception as e:
                logger.warning("[MCP] discovery %s: %s", sid, e)
                result[sid] = []
        return result

    def _resolve_tool_name(self, server_id: str, requested: str) -> str:
        sess = self._session(server_id)
        names = [t.get("name", "") for t in sess.list_tools()]
        if requested in names:
            return requested
        candidates = [
            requested,
            requested.replace("-", "_"),
            requested.replace("_", "-"),
            f"{server_id}_{requested}",
            f"{server_id}-{requested}",
        ]
        for cand in candidates:
            if cand in names:
                return cand
        if len(names) == 1:
            return names[0]
        raise ValueError(f"tool '{requested}' não encontrada; disponíveis: {', '.join(names)}")

    def call(self, server_id: str, tool_name: str, arguments: dict[str, Any]) -> str:
        resolved = self._resolve_tool_name(server_id, tool_name)
        allowed = load_allowlist().get("allowed") or []
        if not is_allowed(server_id, resolved, allowed):
            raise PermissionError(f"tool não permitida: {server_id}/{resolved}")

        sess = self._session(server_id)
        return sess.call_tool(resolved, arguments)


pool = McpGatewayPool()