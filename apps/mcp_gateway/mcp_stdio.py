"""Cliente MCP mínimo (JSON-RPC via stdio, framing Content-Length)."""
from __future__ import annotations

import json
import logging
import subprocess
import sys
import threading
from typing import Any

logger = logging.getLogger(__name__)

_MCP_PROTOCOL = "2024-11-05"


def _read_message(stream) -> dict[str, Any] | None:
    """MCP stdio via @modelcontextprotocol/sdk: uma linha JSON por mensagem."""
    while True:
        line = stream.readline()
        if not line:
            return None
        decoded = line.decode("utf-8", errors="replace").strip()
        if not decoded:
            continue
        return json.loads(decoded)


def _write_message(stream, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False) + "\n"
    stream.write(body.encode("utf-8"))
    stream.flush()


class McpStdioSession:
    """Uma sessão MCP com um servidor (subprocesso Node)."""

    def __init__(self, server_id: str, command: list[str], env: dict[str, str] | None = None, cwd: str | None = None):
        self.server_id = server_id
        self.command = command
        self.env = env or {}
        self.cwd = cwd
        self._proc: subprocess.Popen | None = None
        self._lock = threading.RLock()
        self._request_id = 0
        self._initialized = False
        self._tools_cache: list[dict] | None = None
        self.last_error: str | None = None
        self._stderr_lines: list[str] = []

    @property
    def running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def start(self) -> None:
        if self.running:
            return
        merged_env = None
        if self.env:
            import os

            merged_env = os.environ.copy()
            merged_env.update(self.env)

        kwargs: dict[str, Any] = {
            "stdin": subprocess.PIPE,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "env": merged_env,
            "cwd": self.cwd,
        }
        if sys.platform == "win32":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        self._proc = subprocess.Popen(self.command, **kwargs)
        self._stderr_lines = []
        if self._proc.stderr:
            threading.Thread(
                target=self._drain_stderr,
                name=f"mcp-stderr-{self.server_id}",
                daemon=True,
            ).start()
        self._initialized = False
        self._tools_cache = None
        self._handshake()

    def _invalidate(self, reason: str | None = None) -> None:
        if reason:
            self.last_error = reason
        self._proc = None
        self._initialized = False
        self._tools_cache = None

    def _drain_stderr(self) -> None:
        assert self._proc and self._proc.stderr
        try:
            for raw in self._proc.stderr:
                line = raw.decode("utf-8", errors="replace").rstrip()
                if line:
                    self._stderr_lines.append(line)
                    if len(self._stderr_lines) > 50:
                        self._stderr_lines.pop(0)
                    logger.debug("[%s stderr] %s", self.server_id, line[:300])
        except Exception:
            pass

    def stop(self) -> None:
        if not self._proc:
            return
        try:
            if self._proc.poll() is None:
                self._proc.terminate()
                try:
                    self._proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self._proc.kill()
        except Exception:
            pass
        self._invalidate()

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _handshake(self) -> None:
        assert self._proc and self._proc.stdout and self._proc.stdin
        init_resp = self._request(
            "initialize",
            {
                "protocolVersion": _MCP_PROTOCOL,
                "capabilities": {},
                "clientInfo": {"name": "lira-mcp-gateway", "version": "1.0"},
            },
            timeout=25.0,
        )
        if not init_resp or "error" in init_resp:
            err = (init_resp or {}).get("error", {})
            raise RuntimeError(f"initialize falhou: {err}")
        _write_message(
            self._proc.stdin,
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
        )
        self._initialized = True

    def _request(self, method: str, params: dict | None = None, timeout: float = 30.0) -> dict[str, Any] | None:
        if not self._proc or not self._proc.stdout or not self._proc.stdin:
            raise RuntimeError("processo MCP não está ativo")
        req_id = self._next_id()
        payload: dict[str, Any] = {"jsonrpc": "2.0", "id": req_id, "method": method}
        if params is not None:
            payload["params"] = params
        with self._lock:
            _write_message(self._proc.stdin, payload)
            # Leitura até achar resposta com id correspondente (ignora notificações)
            import time

            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if self._proc.poll() is not None:
                    code = self._proc.returncode
                    tail = "; ".join(self._stderr_lines[-3:])
                    self._invalidate(f"processo MCP encerrou (code={code})")
                    raise RuntimeError(f"processo MCP '{self.server_id}' morreu: {tail or code}")
                try:
                    msg = _read_message(self._proc.stdout)
                except (ConnectionResetError, BrokenPipeError, ValueError) as pipe_err:
                    self._invalidate(str(pipe_err))
                    raise RuntimeError(f"pipe MCP '{self.server_id}' quebrou: {pipe_err}") from pipe_err
                if not msg:
                    continue
                if msg.get("id") == req_id:
                    return msg
        return None

    def list_tools(self, refresh: bool = False) -> list[dict]:
        if self._tools_cache is not None and not refresh:
            return self._tools_cache
        if not self.running:
            self.start()
        resp = self._request("tools/list", {})
        if not resp or "error" in resp:
            err = (resp or {}).get("error", {})
            raise RuntimeError(f"tools/list: {err}")
        tools = (resp.get("result") or {}).get("tools") or []
        self._tools_cache = tools
        return tools

    def call_tool(self, tool_name: str, arguments: dict[str, Any], timeout: float = 45.0) -> str:
        if not self.running:
            self.start()
        resp = self._request(
            "tools/call",
            {"name": tool_name, "arguments": arguments or {}},
            timeout=timeout,
        )
        if not resp:
            raise RuntimeError("sem resposta do servidor MCP")
        if "error" in resp:
            raise RuntimeError(resp["error"])
        result = resp.get("result") or {}
        content = result.get("content") or []
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(str(block.get("text", "")))
                else:
                    parts.append(json.dumps(block, ensure_ascii=False))
        if not parts and result:
            parts.append(json.dumps(result, ensure_ascii=False, indent=2))
        return "\n".join(p for p in parts if p.strip()) or "(resultado vazio)"