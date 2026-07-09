import asyncio
import base64
import datetime
import json
import logging
import os
import re
import threading
import time
import unicodedata
import uuid
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.config.config_loader import CONFIG
from src.core.prompt_builder import build_gui_system_prompt
from src.core.request_profiles import build_request_context
from src.utils.lira_tags import DISPLAY_XML_TAGS, SILENT_XML_TAGS, THOUGHT_TAGS, extract_xml_actions, strip_xml_tags
from src.utils.text import repair_mojibake_text
from src.utils.sentence_divider import SentenceDivider
from src.modules.voice.audio_control import request_global_stop
from lira_core.tools.runner_helpers import (
    build_final_answer_after_tools,
    clean_tool_artifacts_from_visible,
    execute_silent_tools,
    quick_interim_after_tools,
)
from lira_core.tools.tool_manager import ToolManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])
ws_router = APIRouter(tags=["chat_ws"])

_chat_cancel_event = threading.Event()

_IMAGE_DATA_URL_RE = re.compile(r"^data:(?P<mime>image/[\w.+-]+);base64,(?P<data>.+)$", re.IGNORECASE | re.DOTALL)
_HIDDEN_STREAM_TAGS = {tag.lower() for tag in (*SILENT_XML_TAGS, *THOUGHT_TAGS)}


def _strip_data_url_image(value: str) -> tuple[str, str]:
    text = str(value or "").strip()
    match = _IMAGE_DATA_URL_RE.match(text)
    if match:
        return match.group("data").strip(), match.group("mime").lower()
    return text, "image/png"


def _extension_for_mime(mime: str) -> str:
    return {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/webp": ".webp",
        "image/gif": ".gif",
        "image/bmp": ".bmp",
    }.get((mime or "").lower(), ".png")


def _save_chat_upload_image(raw_image: str, index: int) -> str | None:
    image_b64, mime = _strip_data_url_image(raw_image)
    if not image_b64:
        return None
    try:
        payload = base64.b64decode(image_b64, validate=False)
    except Exception as exc:
        logger.warning("[API] Imagem anexada invalida ignorada: %s", exc)
        return None

    upload_dir = os.path.abspath(os.path.join("temp", "gui_chat_uploads"))
    os.makedirs(upload_dir, exist_ok=True)
    filename = f"{time.strftime('%Y%m%d_%H%M%S')}_{index}{_extension_for_mime(mime)}"
    path = os.path.join(upload_dir, filename)
    try:
        with open(path, "wb") as file:
            file.write(payload)
        return path
    except Exception as exc:
        logger.warning("[API] Falha ao salvar anexo do chat: %s", exc)
        return None


def _coerce_gui_history(raw_history) -> list[dict]:
    if not isinstance(raw_history, list):
        return []
    history = []
    for item in raw_history[-16:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip().lower()
        content = str(item.get("content") or "").strip()
        if not content or role == "system":
            continue
        if role in {"user", "amarinth", "human"}:
            history.append({"role": "user", "content": content})
        elif role in {"lira", "assistant", "ai", "model"}:
            history.append({"role": "assistant", "content": _clean_visible_response(content)})
    return history


def _classify_gui_chat_task(message: str, has_images: bool) -> str:
    lowered = unicodedata.normalize("NFKD", str(message or "").lower()).encode("ascii", "ignore").decode("ascii")
    if re.search(r"\b(gera|gerar|cria|criar|faz|faca).*(imagem|foto|arte)\b", lowered):
        return "image_action"
    if re.search(r"\b(edita|editar|altera|alterar|muda|mudar).*(imagem|foto|anexo)\b", lowered):
        return "image_action"
    if re.search(r"\b(gera|gerar|cria|criar|faz|faca|compoe).*(musica)\b", lowered):
        return "music_action"
    if has_images:
        if re.search(r"\b(traduz|traducao|transcreve|transcricao)\b", lowered):
            return "media_exact_request"
        return "media_question"
    return "chat_normal"


def _resolve_chat_provider_and_model(payload: dict) -> tuple[str, str]:
    providers = CONFIG.get("LLM_PROVIDERS", {})
    if not isinstance(providers, dict):
        providers = {}
    provider = str(payload.get("provider") or CONFIG.get("LLM_PROVIDER", "openai") or "openai").strip().lower()
    provider_data = providers.get(provider, {}) if isinstance(providers.get(provider, {}), dict) else {}
    model = str(
        payload.get("model")
        or provider_data.get("modelo_chat")
        or provider_data.get("modelo")
        or ""
    ).strip()
    return provider, model


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


def _with_source_image(payload: str, source_image_path: str | None) -> str:
    if not source_image_path:
        return payload
    try:
        parsed = json.loads(payload)
        if isinstance(parsed, dict) and not parsed.get("source_image"):
            parsed["source_image"] = source_image_path
            return json.dumps(parsed, ensure_ascii=False)
    except Exception:
        pass
    return payload


class VisibleStreamFilter:
    """Remove tags silenciosas sem quebrar markdown do stream da GUI."""

    def __init__(self):
        self.buffer = ""
        self.hidden_tag = ""

    def feed(self, token: str) -> str:
        self.buffer += str(token or "")
        output: list[str] = []

        while self.buffer:
            if self.hidden_tag:
                close_tag = f"</{self.hidden_tag}>"
                idx = self.buffer.lower().find(close_tag)
                if idx < 0:
                    keep = max(0, len(close_tag) - 1)
                    self.buffer = self.buffer[-keep:] if keep else ""
                    break
                self.buffer = self.buffer[idx + len(close_tag):]
                self.hidden_tag = ""
                continue

            # Intercept VTube Studio bracket tags like [EMOTION:...] or [PARAM:...]
            bracket_idx = self.buffer.find("[")
            if bracket_idx >= 0:
                # Se tem um colchete, vamos ver se fecha na mesma linha
                close_bracket_idx = self.buffer.find("]", bracket_idx)
                if close_bracket_idx >= 0:
                    tag_content = self.buffer[bracket_idx:close_bracket_idx + 1]
                    if tag_content.upper().startswith("[EMOTION:") or tag_content.upper().startswith("[PARAM:") or tag_content.upper().startswith("[INDEX_"):
                        # E um tag do VTS, removemos!
                        output.append(self.buffer[:bracket_idx])
                        self.buffer = self.buffer[close_bracket_idx + 1:]
                        continue
                else:
                    # Se nao fecha ainda, vamos ver se parece com uma tag do VTS
                    partial = self.buffer[bracket_idx:].upper()
                    if "[EMOTION:".startswith(partial) or "[PARAM:".startswith(partial) or "[INDEX_".startswith(partial) or partial.startswith("[EMOTION:") or partial.startswith("[PARAM:") or partial.startswith("[INDEX_"):
                        # E possivelmente uma tag do VTS, seguramos no buffer
                        output.append(self.buffer[:bracket_idx])
                        self.buffer = self.buffer[bracket_idx:]
                        break

            lt_idx = self.buffer.find("<")
            if lt_idx < 0:
                output.append(self.buffer)
                self.buffer = ""
                break

            # Se chegamos ate aqui, o bracket nao bloqueou, verificamos as tags XML
            if bracket_idx >= 0 and bracket_idx < lt_idx:
                # O bracket vem antes, entao liberamos ate ele (ja que nao foi segurado)
                output.append(self.buffer[:bracket_idx + 1])
                self.buffer = self.buffer[bracket_idx + 1:]
                continue

            if lt_idx > 0:
                output.append(self.buffer[:lt_idx])
                self.buffer = self.buffer[lt_idx:]

            gt_idx = self.buffer.find(">")
            if gt_idx < 0:
                break

            raw_tag = self.buffer[: gt_idx + 1]
            self.buffer = self.buffer[gt_idx + 1:]
            match = re.match(r"</?\s*([a-zA-Z_][\w-]*)", raw_tag)
            tag_name = match.group(1).lower() if match else ""
            is_closing = raw_tag.strip().startswith("</")

            if tag_name in _HIDDEN_STREAM_TAGS:
                if not is_closing:
                    self.hidden_tag = tag_name
                continue

            output.append(raw_tag)

        return _clean_visible_chunk("".join(output))

    def flush(self) -> str:
        if self.hidden_tag:
            self.buffer = ""
            self.hidden_tag = ""
            return ""
        output = self.buffer
        self.buffer = ""
        # Limpa o que sobrar no flush usando regex
        return _clean_visible_chunk(output)


@router.get("/history")
async def get_chat_history(websocket_or_request=None, limit: int = 50):
    """Retorna o historico de chat sincronizado com a memoria da Lira."""
    # O FastAPI injeta o request se necessário. Usamos app.state.lira a partir do request.app
    # Mas como o endpoint FastAPI padrão recebe request, vamos obtê-lo.
    app = websocket_or_request.app if hasattr(websocket_or_request, "app") else None
    if not app:
        # Se chamado via injeção de dependência ou direto
        return {"messages": []}
    
    context = app.state.lira
    if not context or not context.memory_manager:
        return {"messages": []}
    try:
        messages = context.memory_manager.get_messages(limit=limit)
        return {"messages": messages}
    except Exception as e:
        logger.error(f"[API] Erro ao carregar historico: {e}")
        return {"messages": []}


# Para suportar a assinatura padrão do FastAPI:
from fastapi import Request
@router.get("/history")
async def get_chat_history_api(request: Request, limit: int = 50):
    return await get_chat_history(request, limit)


@router.post("/cancel")
async def cancel_chat():
    """Endpoint para cancelar a resposta atual do chat."""
    _chat_cancel_event.set()
    request_global_stop("gui_chat_cancel")
    logger.info("[API] Cancelamento de resposta solicitado pelo chat.")
    return {"status": "cancelled"}


@ws_router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    logger.info("[API] WebSocket Chat Tauri conectado.")
    app = websocket.app
    context = app.state.lira
    
    try:
        while True:
            _chat_cancel_event.clear()

            data = json.loads(await websocket.receive_text())
            user_message = str(data.get("text") or "").strip()
            logger.info(f"[DEBUG] Mensagem recebida (Tauri): '{user_message}'")
            raw_images = data.get("images_b64", [])
            if not isinstance(raw_images, list):
                raw_images = []

            # --- ARQUITETURA DE CÉREBRO DUPLO: VIGILÂNCIA DE IMAGEM ---
            is_image_intent = re.search(r"\b(gera|gerar|cria|criar|faz|faca|imagine|imagina|draw|paint|desenha|mostra|refaz|refazer|novamente|novo|re-generate|again|tenta|tente)\b.*(imagem|foto|arte|desenho|kitsune|neko|personagem|waifu|garota|menina|ilustra|obra|ela|uma)\b", user_message.lower())
            is_retry = re.search(r"\b(tenta|novo|novamente|refaz|repetir|cade|kd|não foi|n foi|gerou|gerar)\b", user_message.lower())

            if is_image_intent or is_retry:
                logger.info("[DUAL BRAIN] 🧠 Intenção de Arte detectada no Chat Tauri!")
                
                # Fallback de prompt: se for retry, tenta pegar do histórico enviado
                final_art_prompt = user_message
                history = data.get("history", [])
                if is_retry and not is_image_intent and history:
                    for m in reversed(history):
                        if m.get('role') == 'user':
                            final_art_prompt = m.get('content', user_message)
                            break

                async def run_parallel_gen(prompt_text):
                    try:
                        logger.info(f"[DUAL BRAIN] 🎨 Gerando em background: {prompt_text[:50]}...")
                        img_path = context.image_gen.generate(prompt_text)
                        if img_path:
                            filename = os.path.basename(img_path)
                            await websocket.send_json({
                                "type": "media",
                                "media": [{"type": "image", "url": f"http://127.0.0.1:8042/media/images/{filename}"}]
                            })
                            logger.info("[DUAL BRAIN] ✅ Arte enviada com sucesso!")
                    except Exception as e:
                        logger.error(f"[DUAL BRAIN] Erro: {e}")

                asyncio.create_task(run_parallel_gen(final_art_prompt))

            images_b64: list[str] = []
            uploaded_image_paths: list[str] = []
            for idx, raw_image in enumerate(raw_images):
                clean_b64, _mime = _strip_data_url_image(raw_image)
                if not clean_b64:
                    continue
                images_b64.append(clean_b64)
                saved_path = _save_chat_upload_image(raw_image, idx)
                if saved_path:
                    uploaded_image_paths.append(saved_path)

            task_type = _classify_gui_chat_task(user_message, has_images=bool(images_b64))
            chat_provider, chat_model = _resolve_chat_provider_and_model(data)
            llm = context.llm_selector.get_provider(chat_provider) if context.llm_selector else None
            if not llm:
                await websocket.send_json({"type": "error", "content": f"Erro: Provedor LLM '{chat_provider}' nao inicializado."})
                continue

            request_context = build_request_context(
                channel="control_center_chat",
                task_type=task_type,
                override_model=chat_model or None,
            )
            raw_history = _coerce_gui_history(data.get("history", []))
            mem_context = context.memory_manager.get_context(user_message) if context.memory_manager else ""

            current_datetime = datetime.datetime.now().strftime("%A, %d de %B de %Y, %H:%M")
            sistema_prompt = build_gui_system_prompt(
                task_type=task_type,
                memory_context=mem_context,
                request_context=request_context,
                attachments_overview=f"{len(images_b64)} imagem(ns) enviadas pelo chat." if images_b64 else "- nenhum anexo",
            )
            sistema_prompt += (
                "\n=== [MARKDOWN DO CHAT] ===\n"
                "Use Markdown natural quando ajudar: titulos curtos, listas, tabelas e blocos de codigo. "
                "Preserve quebras de linha importantes e nao escreva tags XML no texto visivel.\n"
                f"Data/hora local do pedido: {current_datetime}.\n"
            )

            await websocket.send_json({
                "type": "meta",
                "meta": {"provider": chat_provider.upper(), "model": chat_model or getattr(llm, "modelo_chat", "")},
            })

            user_message_marked = (
                "[ORIGEM: control_center_chat | chat visual | resposta exibida em Markdown na GUI]\n"
                f"Mensagem do usuario: {user_message}"
            )
            token_stream = llm.gerar_resposta_stream(
                chat_history=raw_history,
                sistema_prompt=sistema_prompt,
                user_message=user_message_marked,
                image_b64=images_b64[0] if images_b64 else None,
                request_context=request_context,
            )

            full_raw_response: list[str] = []
            visible_filter = VisibleStreamFilter()
            cancelled = False

            try:
                for token in token_stream:
                    if _chat_cancel_event.is_set():
                        logger.info("[API] Resposta do chat Tauri cancelada pelo usuario.")
                        cancelled = True
                        break
                    if not token:
                        continue
                    full_raw_response.append(token)
                    visible_chunk = visible_filter.feed(token)
                    if visible_chunk:
                        await websocket.send_json({"type": "chunk", "content": visible_chunk})
            except Exception as stream_exc:
                logger.error(f"[API] Erro durante o stream: {stream_exc}")
                await websocket.send_json({"type": "chunk", "content": "\n\n❌ **Erro ao processar imagem/resposta.** O modelo pode não suportar visão ou a API falhou."})

            # Se terminou sem nada e não foi cancelado, manda um aviso
            if not full_raw_response and not cancelled:
                await websocket.send_json({"type": "chunk", "content": "*(Lira ficou em silêncio... Talvez o modelo não suporte imagens?)*"})
                await websocket.send_json({"type": "done"})
                continue

            tail = visible_filter.flush()
            if tail and not cancelled:
                await websocket.send_json({"type": "chunk", "content": tail})

            ai_response = "".join(full_raw_response)
            visible_ai_response = _clean_visible_response(ai_response)

            if cancelled:
                await websocket.send_json({"type": "done"})
                continue

            if context.emotion_engine:
                for thought_tag in THOUGHT_TAGS:
                    for thought in extract_xml_actions(ai_response, (thought_tag,)).get(thought_tag, []):
                        context.emotion_engine.processar_pensamento(thought)
                for emotion in re.findall(r"\[EMOTION:(\w+)\]", ai_response, re.IGNORECASE):
                    context.emotion_engine.processar_emocao(emotion)

            import asyncio as _asyncio_tools

            final_answer_for_memory: str | None = None
            memory_pending_bg = False

            def _run_tools():
                from lira_core.tools.mcp_access import McpCallerContext

                tm = ToolManager(getattr(context, "memory_manager", None))
                return execute_silent_tools(
                    ai_response,
                    user_message=user_message,
                    tool_manager=tm,
                    caller_context=McpCallerContext(
                        channel=str((request_context or {}).get("channel", "control_center_chat")),
                        is_owner=True,
                    ),
                )

            if not cancelled:
                tool_exec = await _asyncio_tools.to_thread(_run_tools)
                if tool_exec.report.tools_ran:
                    logger.info("[API] Tools executadas no chat: %s", tool_exec.report.tools_ran)
                if tool_exec.report.memory_injections:
                    interim = quick_interim_after_tools(
                        ai_response,
                        tool_exec,
                        clean_visible=_clean_visible_response,
                    )
                    await websocket.send_json({"type": "replace_content", "content": interim})
                    final_answer_for_memory = interim
                    memory_pending_bg = True

                    async def _bg_synthesize_tool_answer():
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

                            final_answer = await _asyncio_tools.to_thread(_synthesize)
                            if not final_answer:
                                return
                            await websocket.send_json(
                                {"type": "replace_content", "content": final_answer}
                            )
                            if context.memory_manager:
                                context.memory_manager.add_interaction("Lira", final_answer)
                        except Exception as synth_exc:
                            logger.error("[API] Síntese pós-tool falhou: %s", synth_exc)

                    asyncio.create_task(_bg_synthesize_tool_answer())

            # Texto liberado antes de mídia/TTS/síntese em background
            if context.memory_manager:
                context.memory_manager.add_interaction("Amarinth", user_message)
                if not memory_pending_bg and (final_answer_for_memory or visible_ai_response):
                    context.memory_manager.add_interaction(
                        "Lira",
                        final_answer_for_memory or visible_ai_response,
                    )

            await websocket.send_json({"type": "done"})

            actions = extract_xml_actions(ai_response, (
                "gerar_imagem",
                "gerar_imagem_personagem",
                "editar_imagem",
                "editar_imagem_personagem",
                "gerar_musica",
            ))

            if any(actions.values()):
                logger.info("[API] Acoes detectadas no chat Tauri: %s", [key for key, value in actions.items() if value])

            media_results = []
            source_image = uploaded_image_paths[0] if uploaded_image_paths else None
            if context.image_gen:
                for prompt_img in actions.get("gerar_imagem", []):
                    if not prompt_img:
                        continue
                    try:
                        img_path = context.image_gen.generate(prompt_img)
                        if img_path:
                            filename = os.path.basename(img_path)
                            media_results.append({"type": "image", "url": f"http://127.0.0.1:8042/media/images/{filename}"})
                    except Exception as exc:
                        logger.error("[Chat] Erro gerando imagem: %s", exc)

                for prompt_edit in actions.get("editar_imagem", []):
                    if not prompt_edit:
                        continue
                    try:
                        img_path = context.image_gen.edit(prompt_edit, image_path=source_image)
                        if img_path:
                            filename = os.path.basename(img_path)
                            media_results.append({"type": "image", "url": f"http://127.0.0.1:8042/media/images/{filename}"})
                    except Exception as exc:
                        logger.error("[Chat] Erro editando imagem: %s", exc)

                for payload in actions.get("gerar_imagem_personagem", []):
                    if not payload:
                        continue
                    try:
                        img_path = context.image_gen.generate_character(payload)
                        if img_path:
                            filename = os.path.basename(img_path)
                            media_results.append({"type": "image", "url": f"http://127.0.0.1:8042/media/images/{filename}"})
                    except Exception as exc:
                        logger.error("[Chat] Erro gerando personagem: %s", exc)

                for payload in actions.get("editar_imagem_personagem", []):
                    if not payload:
                        continue
                    try:
                        img_path = context.image_gen.edit_character(_with_source_image(payload, source_image))
                        if img_path:
                            filename = os.path.basename(img_path)
                            media_results.append({"type": "image", "url": f"http://127.0.0.1:8042/media/images/{filename}"})
                    except Exception as exc:
                        logger.error("[Chat] Erro editando personagem: %s", exc)

            if context.music_gen:
                for prompt_music in actions.get("gerar_musica", []):
                    if not prompt_music:
                        continue
                    try:
                        job_id = context.music_gen.submit(prompt_music, origin="gui_chat", request_meta={})
                        media_results.append({"type": "music", "job_id": job_id})
                    except Exception as exc:
                        logger.error("[Chat] Erro iniciando musica: %s", exc)

            for media in media_results:
                await websocket.send_json({"type": "media", "media": media})
                if media["type"] != "music":
                    continue

                async def poll_music(job_id, ws):
                    while True:
                        await asyncio.sleep(2)
                        status = context.music_gen.get_status(job_id)
                        if status.get("state") == "completed":
                            filename = os.path.basename(status.get("output_path"))
                            await ws.send_json({
                                "type": "media",
                                "media": {"type": "music", "job_id": job_id, "url": f"http://127.0.0.1:8042/media/music/{filename}"},
                            })
                            break
                        if status.get("state") in ["failed", "cancelled"]:
                            break

                asyncio.create_task(poll_music(media["job_id"], websocket))

    except WebSocketDisconnect:
        logger.info("[API] WebSocket Chat Tauri desconectado.")
    except Exception as exc:
        logger.exception("[API] Erro no WebSocket Chat Tauri: %s", exc)
