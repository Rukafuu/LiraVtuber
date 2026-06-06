"""Configuração de servidores MCP e allowlist."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SERVERS_FILE = ROOT / "data" / "mcp_servers.json"
ALLOWLIST_FILE = ROOT / "data" / "mcp_allowlist.json"

DEFAULT_SERVERS: dict[str, Any] = {
    "servers": {
        "tavily": {
            "label": "Tavily Search",
            "enabled": True,
            "planned": False,
            "command": ["npx", "-y", "tavily-mcp"],
            "env": {"TAVILY_API_KEY": "${TAVILY_API_KEY}"},
            "cwd": None,
        },
        "github": {
            "label": "GitHub",
            "enabled": True,
            "planned": False,
            "command": ["npx", "-y", "@modelcontextprotocol/server-github"],
            "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}"},
            "cwd": None,
        },
        "filesystem": {
            "label": "Filesystem (LiraVT)",
            "enabled": True,
            "planned": False,
            "command": ["npx", "-y", "@modelcontextprotocol/server-filesystem", str(ROOT)],
            "env": {},
            "cwd": None,
        },
        "memory": {
            "label": "Memory (grafo MCP)",
            "enabled": True,
            "planned": False,
            "command": ["npx", "-y", "@modelcontextprotocol/server-memory"],
            "env": {},
            "cwd": None,
        },
        "puppeteer": {
            "label": "Puppeteer (browser)",
            "enabled": True,
            "planned": False,
            "command": ["npx", "-y", "@modelcontextprotocol/server-puppeteer"],
            "env": {},
            "cwd": None,
        },
    }
}

DEFAULT_ALLOWLIST: dict[str, Any] = {
    "allowed": [
        "tavily/*",
        "github/*",
        "filesystem/*",
        "memory/*",
        "puppeteer/*",
    ],
    "notes": "Use server/tool ou server/* (ex.: tavily/tavily-search, github/*).",
}


def _resolve_env_value(value: str) -> str:
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        return os.getenv(value[2:-1], "")
    return str(value)


def resolve_env_map(env: dict[str, str] | None) -> dict[str, str]:
    if not env:
        return {}
    return {k: _resolve_env_value(v) for k, v in env.items()}


def _ensure_file(path: Path, default: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.is_file():
        path.write_text(json.dumps(default, ensure_ascii=False, indent=2), encoding="utf-8")


def load_servers() -> dict[str, Any]:
    _ensure_file(SERVERS_FILE, DEFAULT_SERVERS)
    try:
        data = json.loads(SERVERS_FILE.read_text(encoding="utf-8"))
        return data.get("servers") or {}
    except Exception:
        return DEFAULT_SERVERS["servers"]


def save_servers(servers: dict[str, Any]) -> None:
    SERVERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SERVERS_FILE.write_text(
        json.dumps({"servers": servers}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_allowlist() -> dict[str, Any]:
    _ensure_file(ALLOWLIST_FILE, DEFAULT_ALLOWLIST)
    try:
        return json.loads(ALLOWLIST_FILE.read_text(encoding="utf-8"))
    except Exception:
        return DEFAULT_ALLOWLIST


def save_allowlist(data: dict[str, Any]) -> None:
    ALLOWLIST_FILE.parent.mkdir(parents=True, exist_ok=True)
    ALLOWLIST_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def is_allowed(server: str, tool: str, allowed: list[str]) -> bool:
    key = f"{server}/{tool}"
    if key in allowed:
        return True
    if f"{server}/*" in allowed:
        return True
    return False