"""
Processamento unificado de tags XML silenciosas (registry + handlers do app).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from lira_core.tools.mcp_access import McpCallerContext, check_salvar_memoria_access
from lira_core.tools.mcp_client import call_mcp_from_tag
from lira_core.tools.registry import XML_TAG_TO_TOOL_ID, tool_ids_for_xml_tags
from lira_core.tools.tool_manager import ToolManager

logger = logging.getLogger(__name__)

ToolResult = tuple[str, str]  # system_block, tts_summary


@dataclass
class XmlActionHandlers:
    """Callbacks opcionais para acoes que ficam no app (VTuber, API, Discord)."""

    on_salvar_memoria: Callable[[str], None] | None = None
    on_gerar_imagem: Callable[[str], None] | None = None
    on_editar_imagem: Callable[[str], None] | None = None
    on_gerar_musica: Callable[[str], None] | None = None
    on_acao_pc: Callable[[str], Any] | None = None
    on_tool_result: Callable[[str, ToolResult], None] | None = None
    on_executando: Callable[[str], None] | None = None
    on_falar_resumo: Callable[[str], None] | None = None


@dataclass
class XmlActionReport:
    tools_ran: list[str] = field(default_factory=list)
    memory_injections: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def default_terminal_action_tags() -> tuple[str, ...]:
    registry_tags = tool_ids_for_xml_tags()
    return (
        "salvar_memoria",
        "gerar_imagem",
        "editar_imagem",
        "gerar_musica",
        "acao_pc",
        "analisar_youtube",
        "ferramenta_web",
        "ler_tela_ocr",
        "ocr_tela",
        "mcp",
    )


def process_xml_actions(
    actions: dict[str, list[str]],
    *,
    tool_manager: ToolManager,
    handlers: XmlActionHandlers | None = None,
    caller_context: McpCallerContext | dict | None = None,
) -> XmlActionReport:
    handlers = handlers or XmlActionHandlers()
    report = XmlActionReport()

    for conteudo in actions.get("salvar_memoria", []):
        if not conteudo:
            continue
        denied = check_salvar_memoria_access(caller_context)
        if denied:
            logger.warning(
                "[XML] salvar_memoria negado (caller=%s)",
                caller_context,
            )
            continue
        try:
            if handlers.on_salvar_memoria:
                handlers.on_salvar_memoria(conteudo)
            elif tool_manager.memory_manager:
                tool_manager.memory_manager.rag.add_memory(
                    conteudo, metadata={"role": "lira", "source": "xml_tag"}
                )
                tool_manager.memory_manager.graph.add_fact("lira_nota", "deve_lembrar", conteudo[:200])
            logger.info("[XML] Memoria salva: %s...", conteudo[:80])
        except Exception as e:
            report.errors.append(f"salvar_memoria: {e}")
            logger.error("[XML] Erro ao salvar memoria: %s", e)

    for prompt_img in actions.get("gerar_imagem", []):
        if prompt_img and handlers.on_gerar_imagem:
            handlers.on_gerar_imagem(prompt_img)

    for prompt_edit in actions.get("editar_imagem", []):
        if prompt_edit and handlers.on_editar_imagem:
            handlers.on_editar_imagem(prompt_edit)

    for prompt_music in actions.get("gerar_musica", []):
        if prompt_music and handlers.on_gerar_musica:
            handlers.on_gerar_musica(prompt_music)

    for payload in actions.get("mcp", []):
        if not payload:
            continue
        if handlers.on_executando:
            handlers.on_executando("mcp")
        try:
            resultado_sis, resumo_tts = call_mcp_from_tag(
                payload,
                caller_context=caller_context,
            )
            report.tools_ran.append("mcp")
            if handlers.on_tool_result:
                handlers.on_tool_result("mcp", (resultado_sis, resumo_tts))
            if resumo_tts and handlers.on_falar_resumo:
                handlers.on_falar_resumo(resumo_tts)
            if resultado_sis:
                report.memory_injections.append(resultado_sis)
        except Exception as e:
            report.errors.append(f"mcp: {e}")
            logger.exception("[XML] Falha MCP")

    for tag_name, payloads in actions.items():
        if tag_name.lower() == "mcp":
            continue
        tool_id = XML_TAG_TO_TOOL_ID.get(tag_name.lower())
        if not tool_id or not payloads:
            continue

        for payload in payloads:
            args = _build_tool_args(tool_id, payload)
            if handlers.on_executando:
                handlers.on_executando(tool_id)

            try:
                resultado_sis, resumo_tts = tool_manager.executar_tool(tool_id, args)
                report.tools_ran.append(tool_id)

                if handlers.on_tool_result:
                    handlers.on_tool_result(tool_id, (resultado_sis, resumo_tts))

                if resumo_tts and handlers.on_falar_resumo:
                    handlers.on_falar_resumo(resumo_tts)

                if resultado_sis:
                    report.memory_injections.append(resultado_sis)
            except Exception as e:
                report.errors.append(f"{tool_id}: {e}")
                logger.exception("[XML] Falha ao executar tool %s", tool_id)

    for payload in actions.get("acao_pc", []):
        if not payload or not handlers.on_acao_pc:
            continue
        if handlers.on_executando:
            handlers.on_executando("acao_pc")
        try:
            handlers.on_acao_pc(payload)
        except Exception as e:
            report.errors.append(f"acao_pc: {e}")
            logger.error("[XML] Erro acao_pc: %s", e)

    return report


def _build_tool_args(tool_id: str, payload: str) -> dict:
    text = (payload or "").strip()
    if tool_id == "pesquisa_web":
        return {"query": text}
    if tool_id == "analisar_youtube":
        return {"url": text}
    if tool_id == "ler_tela_ocr":
        return {}
    if tool_id == "gerar_imagem":
        return {"prompt": text}
    if tool_id == "anotar_fato":
        return {"objeto": text}
    return {"payload": text}