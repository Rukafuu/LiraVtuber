"""
Cliente HTTP para o MCP Gateway (porta 8045).
"""
from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.request
from typing import Any

from lira_core.tools.mcp_access import McpCallerContext, check_mcp_server_access

logger = logging.getLogger(__name__)

_DEFAULT_BASE = "http://127.0.0.1:8045"
_TIMEOUT = float(os.getenv("MCP_CALL_TIMEOUT", "50"))


def gateway_base_url() -> str:
    return os.getenv("MCP_GATEWAY_URL", _DEFAULT_BASE).rstrip("/")


def parse_mcp_payload(raw: str) -> tuple[str, str, dict[str, Any]] | None:
    """
    Formato da tag <mcp>:
      tavily/search
      query em texto na linha seguinte
    ou JSON na mesma tag:
      tavily/search
      {"query": "..."}
    """
    text = (raw or "").strip()
    if not text or "/" not in text.split("\n", 1)[0]:
        return None
    first_line, *rest = text.split("\n", 1)
    path = first_line.strip()
    server, tool = path.split("/", 1)
    server, tool = server.strip(), tool.strip()
    if not server or not tool:
        return None
    body = rest[0].strip() if rest else ""
    if body.startswith("{"):
        try:
            args = json.loads(body)
            if not isinstance(args, dict):
                args = {"input": args}
        except json.JSONDecodeError:
            args = {"query": body}
    elif body:
        if tool in ("search", "tavily_search", "tavily-search", "web_search", "tavily-search"):
            args = {"query": body}
        else:
            args = {"input": body}
    else:
        args = {}
    return server, tool, args


def call_mcp(
    server: str,
    tool: str,
    arguments: dict[str, Any] | None = None,
    *,
    caller_context: McpCallerContext | dict[str, Any] | None = None,
) -> tuple[str, str]:
    """Retorna (bloco_sistema, resumo_tts)."""
    denied = check_mcp_server_access(server, caller_context)
    if denied:
        logger.warning("[MCP] Acesso negado a %s/%s (caller=%s)", server, tool, caller_context)
        return denied

    url = f"{gateway_base_url()}/mcp/call"
    caller_payload: dict[str, Any] | None = None
    if caller_context is not None:
        if isinstance(caller_context, McpCallerContext):
            caller_payload = {
                "channel": caller_context.channel,
                "user_id": caller_context.user_id,
                "user_name": caller_context.user_name,
                "jid": caller_context.jid,
                "is_owner": caller_context.is_owner,
            }
        else:
            caller_payload = dict(caller_context)

    payload = json.dumps(
        {
            "server": server,
            "tool": tool,
            "arguments": arguments or {},
            "caller": caller_payload,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:500]
        logger.warning("[MCP] HTTP %s: %s", e.code, detail)
        return (
            f"--- MCP ERRO ({server}/{tool}) ---\n{detail}\n--- FIM ---",
            "Não consegui usar a ferramenta externa agora.",
        )
    except Exception as e:
        logger.warning("[MCP] indisponível: %s", e)
        return (
            f"--- MCP OFFLINE ---\nGateway em {gateway_base_url()} não respondeu: {e}\n--- FIM ---",
            "O gateway MCP não está ligado.",
        )

    if (server or "").strip().lower() == "tavily":
        from lira_core.tools.mcp_access import spend_tavily_gems

        spend_tavily_gems(caller_context)

    result = data.get("result", "")
    qualified = f"{server}/{data.get('tool', tool)}"
    sys_block = f"--- MCP {qualified} ---\n{result}\n--- FIM MCP ---"
    short = re.sub(r"\s+", " ", str(result))[:120]
    tts = f"Usei {qualified} e já tenho o resultado."
    if short:
        tts = f"Pesquisei com {qualified}: {short}..."
    return sys_block, tts


def call_mcp_from_tag(
    raw: str,
    *,
    caller_context: McpCallerContext | dict[str, Any] | None = None,
) -> tuple[str, str]:
    parsed = parse_mcp_payload(raw)
    if not parsed:
        return ("--- MCP ERRO ---\nFormato inválido. Use: servidor/tool\\nargumentos\n--- FIM ---", "")
    server, tool, args = parsed
    return call_mcp(server, tool, args, caller_context=caller_context)