"""Controle de acesso MCP — serviços sensíveis restritos ao dono do projeto."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

FILESYSTEM_SERVER = "filesystem"
GITHUB_SERVER = "github"
MEMORY_SERVER = "memory"
PUPPETEER_SERVER = "puppeteer"
TAVILY_SERVER = "tavily"

# Servidores que só o criador pode usar (disco, token GitHub, browser local, grafo MCP).
OWNER_ONLY_SERVERS = frozenset(
    {FILESYSTEM_SERVER, GITHUB_SERVER, MEMORY_SERVER, PUPPETEER_SERVER}
)

_DENIED_MESSAGES: dict[str, tuple[str, str]] = {
    GITHUB_SERVER: (
        "--- MCP GITHUB NEGADO ---\n"
        "Acesso ao GitHub (repos, issues, PRs) é exclusivo do criador (@Rukafuu).\n"
        "Este usuário não tem permissão para usar o token GitHub do projeto.\n"
        "--- FIM ---",
        "Não posso mexer no GitHub para quem não é o meu criador.",
    ),
    FILESYSTEM_SERVER: (
        "--- MCP FILESYSTEM NEGADO ---\n"
        "Leitura/escrita no disco local é exclusiva do criador (@Rukafuu).\n"
        "Este usuário não tem permissão para acessar arquivos do projeto.\n"
        "--- FIM ---",
        "Não posso mexer nos arquivos do PC para quem não é o meu criador.",
    ),
    MEMORY_SERVER: (
        "--- MCP MEMORY NEGADO ---\n"
        "O grafo de memória MCP é exclusivo do criador (@Rukafuu).\n"
        "Outros usuários não podem ler, gravar nem apagar memórias do sistema.\n"
        "--- FIM ---",
        "Não posso mexer na memória MCP para quem não é o meu criador.",
    ),
    PUPPETEER_SERVER: (
        "--- MCP PUPPETEER NEGADO ---\n"
        "Navegação automatizada no browser local é exclusiva do criador (@Rukafuu).\n"
        "Este usuário não pode abrir páginas nem rodar automação no seu PC.\n"
        "--- FIM ---",
        "Não posso abrir o navegador no PC para quem não é o meu criador.",
    ),
    "salvar_memoria": (
        "--- SALVAR MEMORIA NEGADO ---\n"
        "Gravar na memória longa (tag <salvar_memoria> e Lira Reflex) é exclusivo do criador (@Rukafuu).\n"
        "Este usuário não pode persistir reflexões arquiteturais nem notas no sistema.\n"
        "--- FIM ---",
        "Não posso salvar memória longa para quem não é o meu criador.",
    ),
}

_OWNER_CHANNELS = frozenset(
    {
        "control_center_chat",
        "control_center",
        "control_api",
        "terminal",
        "vtuber",
    }
)

_CREATOR_ALIASES = frozenset(
    {
        "lucas frischeisen",
        "rukafuu",
        "reskyume",
    }
)


@dataclass
class McpCallerContext:
    channel: str = ""
    user_id: str = ""
    user_name: str = ""
    jid: str = ""
    is_owner: bool | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def _owner_whatsapp_jids() -> set[str]:
    jids: set[str] = set()
    for key in ("WPP_OWNER_JID", "WPP_OWNER_LID"):
        value = os.getenv(key, "").strip()
        if value:
            jids.add(value)
    if not jids:
        jids.update(
            {
                "5511981826659@s.whatsapp.net",
                "38620983517314@lid",
            }
        )
    return jids


def _normalize_whatsapp_jid(jid: str) -> str:
    text = (jid or "").strip()
    if not text:
        return ""
    base = text.split(":")[0]
    if "@" not in base and "@" in text:
        base = f"{base}@{text.split('@', 1)[1]}"
    return base


def _coerce_caller(ctx: McpCallerContext | dict[str, Any] | None) -> McpCallerContext:
    if ctx is None:
        return McpCallerContext()
    if isinstance(ctx, McpCallerContext):
        return ctx
    known = {f.name for f in McpCallerContext.__dataclass_fields__.values()}
    data = {k: v for k, v in ctx.items() if k in known}
    return McpCallerContext(**data)


def is_mcp_owner(ctx: McpCallerContext | dict[str, Any] | None) -> bool:
    caller = _coerce_caller(ctx)
    if caller.is_owner is True:
        return True
    if caller.is_owner is False:
        return False

    channel = (caller.channel or "").strip().lower()
    if channel in _OWNER_CHANNELS:
        return True

    discord_owner = os.getenv("DISCORD_OWNER_ID", "").strip()
    if channel == "discord" and discord_owner and str(caller.user_id).strip() == discord_owner:
        return True

    if channel == "whatsapp":
        owners = _owner_whatsapp_jids()
        jid = caller.jid or caller.extra.get("jid", "")
        clean = _normalize_whatsapp_jid(str(jid))
        if clean in owners or str(jid).strip() in owners:
            return True
        name = (caller.user_name or "").strip().lower()
        if name in _CREATOR_ALIASES:
            return True

    return False


def server_denied_blocks(server: str) -> tuple[str, str]:
    key = (server or "").strip().lower()
    return _DENIED_MESSAGES.get(
        key,
        _DENIED_MESSAGES[FILESYSTEM_SERVER],
    )


def filesystem_denied_blocks() -> tuple[str, str]:
    """Compat — use server_denied_blocks."""
    return server_denied_blocks(FILESYSTEM_SERVER)


def tavily_denied_blocks(*, balance: int = 0, cost: int = 1) -> tuple[str, str]:
    sys_block = (
        "--- MCP TAVILY NEGADO ---\n"
        f"Busca na web custa {cost} gema(s). Saldo atual: {balance}.\n"
        "Ganhe gemas com /daily e /weekly, ou compre via PIX (/loja_gemas no Discord).\n"
        "--- FIM ---"
    )
    tts = "Sem gemas para buscar na web. Usa o daily ou a loja PIX."
    return sys_block, tts


def check_tavily_gem_access(
    ctx: McpCallerContext | dict[str, Any] | None,
) -> tuple[str, str] | None:
    """None = permitido (dono ou tem saldo). Tupla = negado."""
    if is_mcp_owner(ctx):
        return None
    from lira_core.economy.gems import account_from_caller, get_tavily_gem_cost, gems_wallet

    account = account_from_caller(ctx)
    if not account:
        return tavily_denied_blocks(balance=0, cost=get_tavily_gem_cost())

    cost = get_tavily_gem_cost()
    balance = gems_wallet.get_balance(account)
    if balance >= cost:
        return None
    return tavily_denied_blocks(balance=balance, cost=cost)


def spend_tavily_gems(ctx: McpCallerContext | dict[str, Any] | None) -> bool:
    """Debita gemas após Tavily bem-sucedido. Dono não paga."""
    if is_mcp_owner(ctx):
        return True
    from lira_core.economy.gems import account_from_caller, get_tavily_gem_cost, gems_wallet

    account = account_from_caller(ctx)
    if not account:
        return False
    return gems_wallet.spend_gems(
        account,
        get_tavily_gem_cost(),
        reason="tavily_search",
    )


def check_salvar_memoria_access(
    ctx: McpCallerContext | dict[str, Any] | None,
) -> tuple[str, str] | None:
    """Retorna (bloco_sistema, tts) se negado; None se o criador pode salvar."""
    if is_mcp_owner(ctx):
        return None
    return server_denied_blocks("salvar_memoria")


def check_mcp_server_access(
    server: str,
    ctx: McpCallerContext | dict[str, Any] | None,
) -> tuple[str, str] | None:
    """Retorna (bloco_sistema, tts) se o acesso for negado; None se permitido."""
    key = (server or "").strip().lower()
    if key == TAVILY_SERVER:
        return check_tavily_gem_access(ctx)
    if key not in OWNER_ONLY_SERVERS:
        return None
    if is_mcp_owner(ctx):
        return None
    return server_denied_blocks(key)


def caller_from_request_context(request_context: dict[str, Any] | None) -> McpCallerContext:
    """Extrai McpCallerContext de request_context do chat."""
    rc = request_context or {}
    nested = rc.get("mcp_caller") or rc.get("caller_context") or {}
    if isinstance(nested, McpCallerContext):
        return nested
    if isinstance(nested, dict) and nested:
        return _coerce_caller({**nested, "channel": nested.get("channel") or rc.get("channel", "")})
    return McpCallerContext(channel=str(rc.get("channel", "")))