"""Execução pós-LLM de tags silenciosas (MCP, web, YouTube…)."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from lira_core.tools.mcp_access import McpCallerContext, is_mcp_owner
from lira_core.tools.tool_manager import ToolManager
from lira_core.tools.xml_runner import (
    XmlActionHandlers,
    XmlActionReport,
    default_terminal_action_tags,
    process_xml_actions,
)
from lira_core.utils.lira_tags import extract_xml_actions, strip_xml_tags

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_MCP_HEADER_RE = re.compile(r"---\s*MCP\s+(?P<tool>[\w./_-]+)\s*---", re.IGNORECASE)
_MCP_FOOTER_RE = re.compile(r"---\s*FIM(?:\s+MCP)?\s*---\s*$", re.IGNORECASE)
_TOOL_PATH_LINE_RE = re.compile(
    r"(?m)^\s*(?:filesystem|github|tavily|memory|puppeteer)/[\w_.-]+\s*$"
)
_JSON_ONLY_LINE_RE = re.compile(r'(?m)^\s*\{[^}\n]*\}\s*$')

_SYNTHESIS_MAX_CHARS = 14_000
_READ_INTENT_RE = re.compile(
    r"\b(?:l[eê]|ler|leia|li|read|abre|abrir|mostra|ver|resume|resuma|conteúdo|conteudo)\b",
    re.IGNORECASE,
)
_FILE_PATH_RE = re.compile(
    r"(?P<path>(?:[\w.-]+/)*[\w.-]+\.(?:md|txt|json|py|ts|tsx|yaml|yml)|README\.md)",
    re.IGNORECASE,
)


@dataclass
class ToolRunStat:
    tool: str
    lines: int = 0
    chars: int = 0


@dataclass
class ToolExecutionResult:
    report: XmlActionReport
    stats: list[ToolRunStat] = field(default_factory=list)
    elapsed_ms: int = 0


def _html_to_plain(text: str) -> str:
    out = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    out = re.sub(r"</?(?:p|div|h[1-6]|li|tr|td|th|section|article)[^>]*>", "\n", out, flags=re.IGNORECASE)
    out = _HTML_TAG_RE.sub("", out)
    out = re.sub(r"[ \t]+\n", "\n", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def _parse_mcp_block(text: str) -> tuple[str, str] | None:
    m = _MCP_HEADER_RE.search(text)
    if not m:
        return None
    body = text[m.end() :]
    body = _MCP_FOOTER_RE.sub("", body).strip()
    return m.group("tool").strip(), body


def _body_metrics(body: str) -> tuple[int, int]:
    plain = _html_to_plain(body) if ("<" in body and ">" in body) else (body or "")
    lines = plain.splitlines()
    non_empty = sum(1 for ln in lines if ln.strip())
    return non_empty or len(lines), len(plain)


def _stats_from_report(report: XmlActionReport) -> list[ToolRunStat]:
    stats: list[ToolRunStat] = []
    for block in report.memory_injections:
        parsed = _parse_mcp_block(block)
        if parsed:
            tool, body = parsed
            lines, chars = _body_metrics(body)
            stats.append(ToolRunStat(tool=tool, lines=lines, chars=chars))
            continue
        plain = (block or "").strip()
        lines, chars = _body_metrics(plain)
        stats.append(ToolRunStat(tool="ferramenta", lines=lines, chars=chars))
    return stats


def clean_tool_artifacts_from_visible(text: str) -> str:
    """Remove tags MCP e linhas técnicas que o modelo às vezes vaza no texto visível."""
    if not text:
        return ""
    visible = strip_xml_tags(str(text))
    visible = _TOOL_PATH_LINE_RE.sub("", visible)
    visible = _JSON_ONLY_LINE_RE.sub("", visible)
    visible = re.sub(r":\d+processando:", "", visible, flags=re.IGNORECASE)
    visible = re.sub(r"(?m)^\s*🔎\s*\*\*.*\*\*.*$", "", visible)
    visible = re.sub(r"\n{3,}", "\n\n", visible)
    return visible.strip()


def format_tool_stats_line(stats: list[ToolRunStat], elapsed_ms: int) -> str:
    """Uma linha discreta para o usuário — sem dump técnico."""
    if not stats:
        return ""
    sec = elapsed_ms / 1000.0
    sec_str = f"{sec:.1f}".replace(".", ",") + " s"
    primary = stats[0]
    tool_l = primary.tool.lower()

    if "read" in tool_l or "filesystem" in tool_l or "auto_read" in tool_l:
        if primary.lines > 0:
            return f"\n\n📄 *Lidas {primary.lines} linhas em {sec_str}*"
        return f"\n\n📄 *Arquivo consultado em {sec_str}*"
    if "tavily" in tool_l or "search" in tool_l or "ferramenta_web" in tool_l:
        return f"\n\n🔍 *Busca concluída em {sec_str}*"
    if "github" in tool_l:
        return f"\n\n🐙 *GitHub consultado em {sec_str}*"
    if "puppeteer" in tool_l:
        return f"\n\n🌐 *Página aberta em {sec_str}*"
    if "memory" in tool_l:
        return f"\n\n🧠 *Memória MCP em {sec_str}*"
    return f"\n\n🔧 *{primary.tool} · {sec_str}*"


def synthesize_after_tools(
    llm: Any,
    *,
    user_message: str,
    sistema_prompt: str,
    tool_report: XmlActionReport,
    request_context: dict[str, Any] | None = None,
    chat_history: list | None = None,
) -> str:
    """Segunda passada: resposta natural usando o resultado interno das tools."""
    blocks = "\n\n".join(tool_report.memory_injections).strip()
    if not blocks:
        return ""

    if len(blocks) > _SYNTHESIS_MAX_CHARS:
        blocks = blocks[: _SYNTHESIS_MAX_CHARS - 20] + "\n… (truncado)"

    synthesis_prompt = (
        sistema_prompt
        + "\n\n=== [DADOS INTERNOS DA FERRAMENTA — NÃO REPRODUZA COMO DUMP] ===\n"
        + blocks
        + "\n=== [INSTRUÇÃO] ===\n"
        "Com base nos dados acima, responda ao pedido do usuário de forma natural.\n"
        "NÃO mostre tags XML, caminhos filesystem/..., JSON de tools nem cole o arquivo inteiro.\n"
        "Resuma o que importa em poucas frases (2–8), no seu tom habitual.\n"
        "Se for leitura de arquivo, diga o que o arquivo é e o essencial do conteúdo.\n"
    )

    return llm.gerar_resposta(
        chat_history=chat_history or [],
        sistema_prompt=synthesis_prompt,
        user_message=user_message,
        request_context=request_context or {},
    )


def infer_read_path(user_message: str) -> str | None:
    """Detecta pedido de leitura de arquivo no texto do usuário."""
    msg = (user_message or "").strip()
    if not msg or not _READ_INTENT_RE.search(msg):
        return None
    m = _FILE_PATH_RE.search(msg)
    if m:
        return m.group("path").replace("\\", "/")
    if re.search(r"\breadme\b", msg, re.IGNORECASE):
        return "README.md"
    return None


def _auto_read_file(
    user_message: str,
    *,
    caller_context: McpCallerContext | dict | None = None,
) -> tuple[str, str] | None:
    """Fallback quando o LLM não emitiu <mcp> mas o usuário pediu leitura."""
    path = infer_read_path(user_message)
    if not path:
        return None
    if not is_mcp_owner(caller_context):
        return None
    if not mcp_gateway_reachable():
        return (
            "--- MCP OFFLINE ---\nGateway MCP (:8045) não está ligado. "
            "Inicie em Plataformas → MCP Gateway.\n--- FIM ---",
            "",
        )
    from lira_core.tools.mcp_client import call_mcp

    return call_mcp(
        "filesystem",
        "read_text_file",
        {"path": path},
        caller_context=caller_context,
    )


def supplement_with_auto_tools(
    user_message: str | None,
    tool_exec: ToolExecutionResult,
    *,
    caller_context: McpCallerContext | dict | None = None,
) -> ToolExecutionResult:
    """Executa leitura automática se o modelo esqueceu a tag <mcp>."""
    if not user_message or tool_exec.report.memory_injections:
        return tool_exec

    t1 = time.perf_counter()
    auto = _auto_read_file(user_message, caller_context=caller_context)
    if not auto:
        return tool_exec

    sys_block, _tts = auto
    extra_ms = int((time.perf_counter() - t1) * 1000)
    report = tool_exec.report
    report.memory_injections.append(sys_block)
    report.tools_ran.append("mcp:auto_read")
    stats = _stats_from_report(report)
    return ToolExecutionResult(
        report=report,
        stats=stats,
        elapsed_ms=tool_exec.elapsed_ms + extra_ms,
    )


def execute_silent_tools(
    raw_llm_output: str,
    *,
    user_message: str | None = None,
    tool_manager: ToolManager | None = None,
    handlers: XmlActionHandlers | None = None,
    caller_context: McpCallerContext | dict | None = None,
) -> ToolExecutionResult:
    tm = tool_manager or ToolManager()
    actions = extract_xml_actions(raw_llm_output, default_terminal_action_tags())
    t0 = time.perf_counter()
    if any(actions.values()):
        report = process_xml_actions(
            actions,
            tool_manager=tm,
            handlers=handlers,
            caller_context=caller_context,
        )
    else:
        report = XmlActionReport()
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    result = ToolExecutionResult(
        report=report,
        stats=_stats_from_report(report),
        elapsed_ms=elapsed_ms,
    )
    return supplement_with_auto_tools(
        user_message,
        result,
        caller_context=caller_context,
    )


def mcp_gateway_reachable() -> bool:
    try:
        from lira_core.tools.mcp_client import gateway_base_url
        import urllib.request

        with urllib.request.urlopen(f"{gateway_base_url()}/health", timeout=2.5) as r:
            return r.status == 200
    except Exception:
        return False


def _synthesis_request_context(request_context: dict[str, Any] | None) -> dict[str, Any]:
    import os

    ctx = dict(request_context or {})
    override = os.getenv("CHAT_SYNTHESIS_MODEL", "").strip()
    if override:
        ctx["override_model"] = override
    elif not ctx.get("override_model"):
        ctx["override_model"] = "gemini-2.5-flash"
    return ctx


def quick_interim_after_tools(
    ai_response: str,
    tool_exec: ToolExecutionResult,
    *,
    clean_visible: Callable[[str], str] | None = None,
) -> str:
    """Texto imediato (sem 2ª chamada LLM): status de leitura + rascunho limpo."""
    stats = format_tool_stats_line(tool_exec.stats, tool_exec.elapsed_ms)
    visible = clean_visible(ai_response) if clean_visible else ""
    if visible:
        return (visible + stats).strip()
    return (f"_Um momento, estou processando…_{stats}").strip()


def build_final_answer_after_tools(
    llm: Any,
    *,
    user_message: str,
    sistema_prompt: str,
    tool_exec: ToolExecutionResult,
    request_context: dict[str, Any] | None = None,
    chat_history: list | None = None,
) -> str | None:
    """Resposta visível: só a Lira + linha de status (linhas/tempo)."""
    if not tool_exec.report.memory_injections or not tool_exec.report.tools_ran:
        return None
    raw = synthesize_after_tools(
        llm,
        user_message=user_message,
        sistema_prompt=sistema_prompt,
        tool_report=tool_exec.report,
        request_context=_synthesis_request_context(request_context),
        chat_history=chat_history,
    )
    answer = clean_tool_artifacts_from_visible(strip_xml_tags(str(raw or "")))
    if not answer:
        return None
    stats = format_tool_stats_line(tool_exec.stats, tool_exec.elapsed_ms)
    return (answer + stats).strip()


# Compat legado — não anexa mais dump técnico
def format_tool_results_for_chat(*_args, **_kwargs) -> str:
    return ""