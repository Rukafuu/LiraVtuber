import asyncio
import datetime
import json
import logging
import re
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse

from src.config.config_loader import CONFIG
from src.core.request_profiles import build_request_context
from src.utils.lira_tags import DISPLAY_XML_TAGS, SILENT_XML_TAGS, THOUGHT_TAGS, extract_xml_actions, strip_xml_tags
from src.utils.text import repair_mojibake_text
from src.utils.sentence_divider import SentenceDivider
from lira_core.tools.runner_helpers import (
    build_final_answer_after_tools,
    clean_tool_artifacts_from_visible,
    execute_silent_tools,
    quick_interim_after_tools,
)
from lira_core.tools.tool_manager import ToolManager
from lira_core.tools.mcp_access import McpCallerContext

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/brain", tags=["brain"])


def _clean_visible_chunk(text: str) -> str:
    if not text:
        return ""
    cleaned = repair_mojibake_text(str(text))
    cleaned = re.sub(r"\[EMOTION:[^\]]*\]?", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\[PARAM:[^\]]*\]?", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\[INDEX_[^\]]*\]?", "", cleaned, flags=re.IGNORECASE)
    return cleaned


def _clean_visible_response(text: str) -> str:
    visible = strip_xml_tags(str(text or ""), DISPLAY_XML_TAGS)
    visible = clean_tool_artifacts_from_visible(visible)
    visible = _clean_visible_chunk(visible)
    visible = re.sub(r"\n{3,}", "\n\n", visible)
    return visible.strip()


@router.post("/chat")
async def brain_chat(request: Request, payload: dict):
    """
    Endpoint centralizado de processamento do cérebro da Lira.
    Recebe requisições do Terminal VTuber, Discord Bot ou WhatsApp e
    retorna um stream de eventos JSON (Server-Sent Events simplificado).
    """
    user_message = str(payload.get("message") or "").strip()
    channel = str(payload.get("channel") or "terminal").strip().lower()
    raw_history = payload.get("history") or []
    image_b64 = payload.get("image_b64")
    caller_ctx_data = payload.get("caller_context") or {}

    if not user_message:
        raise HTTPException(status_code=400, detail="Mensagem do usuario vazia.")

    context = request.app.state.lira
    if not context or not context.llm_selector:
        raise HTTPException(status_code=500, detail="Provedor LLM central nao inicializado.")

    # 1. Resolve o provider/model ativo
    providers = CONFIG.get("LLM_PROVIDERS", {})
    default_provider = CONFIG.get("LLM_PROVIDER", "openai")
    provider_name = str(payload.get("provider") or default_provider).strip().lower()
    provider_data = providers.get(provider_name, {}) if isinstance(providers.get(provider_name, {}), dict) else {}
    model_name = str(payload.get("model") or provider_data.get("modelo_chat") or provider_data.get("modelo") or "").strip()

    llm = context.llm_selector.get_provider(provider_name)
    if not llm:
        raise HTTPException(status_code=500, detail=f"Erro: Provedor LLM '{provider_name}' nao inicializado no core.")

    # 2. Configura contexto e prompt do sistema
    task_type = "chat_normal"
    if image_b64:
        task_type = "media_question"

    request_context = build_request_context(
        channel=channel,
        task_type=task_type,
        override_model=model_name or None,
    )

    mem_context = ""
    if context.memory_manager:
        mem_context = context.memory_manager.get_context(user_message)

    if channel == "discord":
        from src.modules.discord.constants import EMOJI
        emoji_list_str = "\n".join([f"- :{key}:" for key in EMOJI.keys()])
        discord_context = (
            "Canal: Discord.\n"
            "Você está conversando no Discord. Responda com deboche, sarcasmo e superioridade. Trate os humanos como seres inferiores e fofos em sua ignorância.\n"
            "REGRA OBRIGATÓRIA DE EMOJIS: NUNCA use emojis padrão do Windows (como 🌸, 😈, 😂).\n"
            "Use os emojis customizados listados abaixo escrevendo-os EXATAMENTE como mostrado, no formato :chave:.\n"
            "NUNCA invente emojis, NUNCA adicione números antes do nome. Use apenas as chaves da lista abaixo.\n"
            "NUNCA use kanji, hiragana ou katakana — só português do Brasil.\n\n"
            f"[EMOJIS DISPONÍVEIS - USE EXATAMENTE ESSES NOMES]:\n{emoji_list_str}\n\n"
            f"Contexto de memoria: {mem_context}"
        )
        mem_context = discord_context

    current_datetime = datetime.datetime.now().strftime("%A, %d de %B de %Y, %H:%M")
    conversation_timing = ""

    # Recupera histórico e timing centralizadamente se não enviado
    if not raw_history and context.memory_manager:
        if channel == "terminal":
            terminal_state = context.memory_manager.get_terminal_context_state(history_limit=30, stale_after_minutes=45)
            raw_history = terminal_state["history"]
            conversation_timing = terminal_state["timing_text"]
        else:
            raw_history = context.memory_manager.get_messages(limit=16)

    # Prompt builder baseado no canal
    if channel == "terminal":
        from src.core.prompt_builder import build_terminal_system_prompt
        sistema_prompt = build_terminal_system_prompt(
            memory_context=mem_context,
            current_datetime=current_datetime,
            vts_anatomy=payload.get("vts_anatomy", ""),
            conversation_timing=conversation_timing,
        )
    else:
        from src.core.prompt_builder import build_gui_system_prompt
        sistema_prompt = build_gui_system_prompt(
            task_type=task_type,
            memory_context=mem_context,
            request_context=request_context,
            attachments_overview=f"1 imagem anexada via {channel}." if image_b64 else "- nenhum anexo",
        )

    # Instrução de Markdown rica apenas para canais visuais
    if channel != "terminal":
        sistema_prompt += (
            "\n=== [MARKDOWN DO CHAT] ===\n"
            "Use Markdown natural quando ajudar: titulos curtos, listas, tabelas e blocos de codigo.\n"
        )
    sistema_prompt += f"\nData/hora local do pedido: {current_datetime}.\n"

    async def event_generator():
        yield json.dumps({
            "type": "meta",
            "provider": provider_name.upper(),
            "model": model_name or getattr(llm, "modelo_chat", ""),
        }) + "\n"

        user_message_marked = (
            f"[ORIGEM: {channel} | chat processado via API central]\n"
            f"Mensagem do usuario: {user_message}"
        )

        try:
            token_stream = llm.gerar_resposta_stream(
                chat_history=raw_history,
                sistema_prompt=sistema_prompt,
                user_message=user_message_marked,
                image_b64=image_b64,
                request_context=request_context,
            )
        except Exception as exc:
            yield json.dumps({"type": "error", "content": f"Falha na geracao stream da LLM: {exc}"}) + "\n"
            return

        full_raw_response = []
        try:
            # Iteração do stream
            for token in token_stream:
                if not token:
                    continue
                full_raw_response.append(token)
                yield json.dumps({"type": "chunk", "content": token}) + "\n"
        except Exception as stream_exc:
            yield json.dumps({"type": "error", "content": f"Erro no stream: {stream_exc}"}) + "\n"
            return

        ai_response = "".join(full_raw_response)
        visible_ai_response = _clean_visible_response(ai_response)

        # Processamento de Emoções para o VTube Studio
        emotions_found = []
        for thought_tag in THOUGHT_TAGS:
            for thought in extract_xml_actions(ai_response, (thought_tag,)).get(thought_tag, []):
                if context.emotion_engine:
                    context.emotion_engine.processar_pensamento(thought)
        for emotion in re.findall(r"\[EMOTION:(\w+)\]", ai_response, re.IGNORECASE):
            emotions_found.append(emotion)
            if context.emotion_engine:
                context.emotion_engine.processar_emocao(emotion)

        if emotions_found:
            yield json.dumps({"type": "emotions", "emotions": emotions_found}) + "\n"

        # Execução das ferramentas silenciosas
        def _run_tools():
            tm = ToolManager(getattr(context, "memory_manager", None))
            return execute_silent_tools(
                ai_response,
                user_message=user_message,
                tool_manager=tm,
                caller_context=McpCallerContext(
                    channel=channel,
                    is_owner=bool(caller_ctx_data.get("is_owner", True)),
                    user_id=caller_ctx_data.get("user_id"),
                ),
            )

        tool_exec = await asyncio.to_thread(_run_tools)
        if tool_exec.report.tools_ran:
            yield json.dumps({"type": "tools_ran", "tools": tool_exec.report.tools_ran}) + "\n"

        final_answer = visible_ai_response

        # Se executou tools de injeção de memória, realiza a segunda passada de síntese
        if tool_exec.report.memory_injections:
            interim = quick_interim_after_tools(
                ai_response,
                tool_exec,
                clean_visible=_clean_visible_response,
            )
            yield json.dumps({"type": "replace_content", "content": interim}) + "\n"
            final_answer = interim

            try:
                def _synthesize():
                    return build_final_answer_after_tools(
                        llm,
                        user_message=user_message_marked,
                        sistema_prompt=sistema_prompt,
                        tool_exec=tool_exec,
                        request_context=request_context,
                        chat_history=raw_history,
                    )
                final_answer = await asyncio.to_thread(_synthesize)
                if final_answer:
                    yield json.dumps({"type": "replace_content", "content": final_answer}) + "\n"
            except Exception as synth_exc:
                logger.error("[BRAIN API] Síntese pós-tool falhou: %s", synth_exc)

        # Salva na memória centralizada de forma consistente
        if context.memory_manager:
            context.memory_manager.add_interaction(payload.get("user_role_name") or "Amarinth", user_message)
            if final_answer:
                context.memory_manager.add_interaction("Lira", final_answer)

        # Detecção de tags de mídias para gerar imagens ou música no cliente
        actions = extract_xml_actions(ai_response, (
            "gerar_imagem",
            "gerar_imagem_personagem",
            "editar_imagem",
            "editar_imagem_personagem",
            "gerar_musica",
        ))
        if any(actions.values()):
            yield json.dumps({"type": "media_actions", "actions": actions}) + "\n"

        yield json.dumps({"type": "done"}) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")
