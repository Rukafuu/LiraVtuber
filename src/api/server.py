import asyncio
import base64
import json
import logging
import psutil
import re
import time
import unicodedata
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn

import os
import sys
import datetime
import threading
import uuid
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.config.config_loader import CONFIG
from src.core.provider_catalog import MODEL_CATALOG, VOICE_CATALOG, get_llm_providers, get_tts_providers
from src.modules.voice import speech_state

# === LOGGING INTERCEPTOR ===
class MemoryLogHandler(logging.Handler):
    def __init__(self, capacity=200):
        super().__init__()
        self.capacity = capacity
        self.logs = []
        self.formatter = logging.Formatter('%(asctime)s - [%(levelname)s] - %(message)s')

    def emit(self, record):
        try:
            msg = self.format(record)
            self.logs.append({
                "timestamp": self.formatter.formatTime(record, "%H:%M:%S"),
                "level": record.levelname,
                "message": record.getMessage(),
                "logger": record.name
            })
            if len(self.logs) > self.capacity:
                self.logs.pop(0)
        except Exception:
            pass

# Instancia o handler e adiciona ao root logger
memory_log_handler = MemoryLogHandler()
logging.getLogger().addHandler(memory_log_handler)

logger = logging.getLogger(__name__)

app = FastAPI(title="Lira Control Center API", version="1.0")

# Referências globais (injetadas pelo main.py)
class AppContext:
    memory_manager = None
    llm_selector = None
    image_gen = None
    music_gen = None
    emotion_engine = None
    tts = None
    signals = None

app.state.lira = AppContext()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mapeamento de pastas de mídia
PICTURES_DIR = os.path.join(os.path.expanduser("~"), "Pictures", "Lira Artista")
MUSIC_DIR = os.path.join(os.path.expanduser("~"), "Music", "Lira Music")

os.makedirs(PICTURES_DIR, exist_ok=True)
os.makedirs(MUSIC_DIR, exist_ok=True)

app.mount("/media/images", StaticFiles(directory=PICTURES_DIR), name="images")
app.mount("/media/music", StaticFiles(directory=MUSIC_DIR), name="music")

# === CHAT HISTORY REST ENDPOINT ===

@app.get("/api/chat/history")
async def get_chat_history(limit: int = 50):
    """Retorna o historico de chat sincronizado com a memoria da Lira."""
    context = app.state.lira
    if not context.memory_manager:
        return {"messages": []}
    try:
        messages = context.memory_manager.get_messages(limit=limit)
        return {"messages": messages}
    except Exception as e:
        logger.error(f"[API] Erro ao carregar historico: {e}")
        return {"messages": []}

# === MEMORY REST ENDPOINTS ===

@app.get("/api/memory/graph")
async def get_memory_graph():
    """Retorna todos os fatos do Knowledge Graph."""
    context = app.state.lira
    if not context.memory_manager or not context.memory_manager.graph:
        return {"facts": []}
    return {"facts": context.memory_manager.graph.get_all_facts()}

@app.delete("/api/memory/graph")
async def delete_memory_graph(payload: dict):
    """Remove um fato do Knowledge Graph."""
    context = app.state.lira
    if not context.memory_manager or not context.memory_manager.graph:
        return {"status": "error", "message": "Memoria indisponivel"}
    
    subject = payload.get("subject")
    relation = payload.get("relation")
    object_val = payload.get("object")
    
    success = context.memory_manager.graph.delete_fact(subject, relation, object_val)
    if success:
        return {"status": "ok"}
    return {"status": "error", "message": "Falha ao remover fato"}


@app.post("/api/memory/graph")
async def create_memory_graph(payload: dict):
    """Cria ou atualiza um fato no Knowledge Graph."""
    context = app.state.lira
    if not context.memory_manager or not context.memory_manager.graph:
        return {"status": "error", "message": "Memoria indisponivel"}

    subject = str(payload.get("subject") or "").strip()
    relation = str(payload.get("relation") or "").strip()
    object_val = str(payload.get("object") or "").strip()
    if not subject or not relation or not object_val:
        return {"status": "error", "message": "Preencha subject, relation e object."}

    context.memory_manager.add_fact(subject, relation, object_val)
    return {"status": "ok", "fact": {"subject": subject, "relation": relation, "object": object_val}}

@app.get("/api/memory/rag")
async def get_memory_rag():
    """Retorna todas as memorias semanticas do RAG."""
    context = app.state.lira
    if not context.memory_manager or not context.memory_manager.rag:
        return {"memories": []}
    return {"memories": context.memory_manager.rag.get_all_memories()}

@app.delete("/api/memory/rag/{mem_id}")
async def delete_memory_rag(mem_id: str):
    """Remove uma memoria semantica do RAG pelo ID."""
    context = app.state.lira
    if not context.memory_manager or not context.memory_manager.rag:
        return {"status": "error", "message": "Memoria indisponivel"}
    
    success = context.memory_manager.rag.delete_memory(mem_id)
    if success:
        return {"status": "ok"}
    return {"status": "error", "message": "Falha ao remover memoria"}


@app.post("/api/memory/rag")
async def create_memory_rag(payload: dict):
    """Cria uma memoria semantica manual no RAG."""
    context = app.state.lira
    if not context.memory_manager or not context.memory_manager.rag:
        return {"status": "error", "message": "Memoria indisponivel"}

    text = str(payload.get("text") or "").strip()
    if len(text) < 3:
        return {"status": "error", "message": "Texto muito curto."}

    mem_id = str(payload.get("id") or uuid.uuid4())
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    metadata.setdefault("source", "gui_memory_editor")
    context.memory_manager.rag.upsert_memory(mem_id, text, metadata=metadata)
    return {"status": "ok", "memory": {"id": mem_id, "text": text, "metadata": metadata}}


@app.put("/api/memory/rag/{mem_id}")
async def update_memory_rag(mem_id: str, payload: dict):
    """Atualiza uma memoria semantica existente no RAG."""
    context = app.state.lira
    if not context.memory_manager or not context.memory_manager.rag:
        return {"status": "error", "message": "Memoria indisponivel"}

    text = str(payload.get("text") or "").strip()
    if len(text) < 3:
        return {"status": "error", "message": "Texto muito curto."}

    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    metadata.setdefault("source", "gui_memory_editor")
    context.memory_manager.rag.upsert_memory(mem_id, text, metadata=metadata)
    return {"status": "ok", "memory": {"id": mem_id, "text": text, "metadata": metadata}}


# === SYSTEM LOGS ENDPOINT ===

@app.get("/api/logs")
async def get_system_logs(limit: int = 100):
    """Retorna os logs mais recentes interceptados pelo servidor Python."""
    return {"logs": memory_log_handler.logs[-limit:]}


# === CHAT WEBSOCKET & HELPERS ===

from src.core.prompt_builder import build_gui_system_prompt
from src.core.request_profiles import build_request_context
from src.utils.lira_tags import DISPLAY_XML_TAGS, SILENT_XML_TAGS, THOUGHT_TAGS, extract_xml_actions, strip_xml_tags
from src.utils.text import repair_mojibake_text
from src.modules.voice.audio_control import request_global_stop

# Sinal de cancelamento para o chat
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


def _classify_chat_task(message: str, has_images: bool) -> str:
    lowered = str(message or "").lower()
    if re.search(r"\b(gera|gerar|cria|criar|faz|faca|faça).*(imagem|foto|arte)\b", lowered):
        return "image_action"
    if re.search(r"\b(edita|editar|altera|alterar|muda|mudar).*(imagem|foto|anexo)\b", lowered):
        return "image_action"
    if re.search(r"\b(gera|gerar|cria|criar|faz|faca|faça|compoe|compõe).*(musica|música)\b", lowered):
        return "music_action"
    if has_images:
        if re.search(r"\b(traduz|traducao|tradução|transcreve|transcricao|transcrição)\b", lowered):
            return "media_exact_request"
        return "media_question"
    return "chat_normal"


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

            lt_idx = self.buffer.find("<")
            if lt_idx < 0:
                output.append(self.buffer)
                self.buffer = ""
                break

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
        return _clean_visible_chunk(output)

@app.post("/api/chat/cancel")
async def cancel_chat():
    """Endpoint para cancelar a resposta atual do chat."""
    _chat_cancel_event.set()
    request_global_stop("gui_chat_cancel")
    logger.info("[API] Cancelamento de resposta solicitado pelo chat.")
    return {"status": "cancelled"}


@app.post("/api/tts/speak")
async def speak_tts(payload: dict):
    """Reproduz TTS pelo backend e sinaliza lipsync para o VTube Studio."""
    text = str(payload.get("text") or "").strip()
    if not text:
        return {"status": "error", "message": "Texto vazio."}
    if not CONFIG.get("TTS_ATIVO", True):
        return {"status": "error", "message": "TTS desativado."}

    context = app.state.lira
    tts_engine = context.tts
    if tts_engine is None:
        from src.modules.voice.tts_selector import get_tts

        tts_engine = get_tts()
        context.tts = tts_engine

    def _run_tts():
        speech_state.set_speaking(True)
        if context.signals is not None:
            try:
                context.signals.LIRA_SPEAKING = True
            except Exception:
                pass
        try:
            tts_engine.falar(text)
        except Exception as exc:
            logger.error("[API] Erro ao reproduzir TTS: %s", exc)
        finally:
            speech_state.set_speaking(False)
            if context.signals is not None:
                try:
                    context.signals.LIRA_SPEAKING = False
                except Exception:
                    pass

    threading.Thread(target=_run_tts, daemon=True, name="GuiTTS").start()
    return {"status": "speaking"}

# Legacy implementation kept temporarily while the Tauri chat route is rebuilt below.
async def _websocket_chat_legacy(websocket: WebSocket):
    await websocket.accept()
    logger.info("[API] WebSocket Chat conectado.")
    try:
        while True:
            # Limpa o sinal de cancelamento para um novo turno
            _chat_cancel_event.clear()
            
            data_str = await websocket.receive_text()
            data = json.loads(data_str)
            
            user_message = data.get("text", "")
            images_b64 = data.get("images_b64", [])
            
            # Classifica a tarefa para o prompt
            def classify(msg):
                lowered = msg.lower()
                if re.search(r"\b(gera|cria|criar|faz|fa[cç]a).*(imagem|foto|arte)\b", lowered):
                    return "image_action"
                if re.search(r"\b(gera|cria|criar|faz|fa[cç]a|comp[oô]e).*(m[uú]sica|musica)\b", lowered):
                    return "music_action"
                return "chat_normal"
            
            task_type = classify(user_message)
            
            context = app.state.lira
            llm = context.llm_selector.get_provider() if context.llm_selector else None
            
            if not llm:
                await websocket.send_json({"type": "error", "content": "Erro: Provedor LLM não inicializado."})
                continue
                
            # Atualiza o provider com base nas configs da GUI antes de chamar
            chat_cfg = CONFIG.get("CHAT", {})
            llm.provedor = chat_cfg.get("LLM_PROVIDER", CONFIG.get("LLM_PROVIDER", "openai"))
            llm.modelo_chat = chat_cfg.get("LLM_MODEL", "")

            # Memória Híbrida
            mem_context = ""
            raw_history = []
            if context.memory_manager:
                mem_context = context.memory_manager.get_context(user_message)
                terminal_state = context.memory_manager.get_terminal_context_state(history_limit=30, stale_after_minutes=45)
                raw_history = terminal_state["history"]

            current_datetime = datetime.datetime.now().strftime("%A, %d de %B de %Y, %H:%M")
            
            # Prompt GUI
            sistema_prompt = build_gui_system_prompt(
                task_type=task_type,
                memory_context=mem_context,
                request_context=build_request_context(channel="control_center_chat", task_type=task_type),
                attachments_overview=f"{len(images_b64)} imagem(ns) enviadas pelo chat." if images_b64 else "- nenhum anexo"
            )
            
            # Injecting Markdown instruction
            sistema_prompt += "\n[ATENÇÃO]: Você está respondendo em um Chat Bot via GUI. Sinta-se livre para dar respostas mais longas se o contexto pedir, e VOCÊ DEVE OBRIGATORIAMENTE usar formatação Markdown (negrito, listas, códigos, etc) para deixar a resposta mais bonita."

            # Enviando Meta inicial
            await websocket.send_json({
                "type": "meta",
                "meta": {"provider": llm.provedor.upper(), "model": llm.modelo_chat}
            })

            # Marca a origem da mensagem para a LLM saber como responder
            user_message_marcada = (
                f"[ORIGEM: control_center_chat | chat visual | resposta sera exibida em markdown na GUI]\n"
                f"Mensagem do usuario: {user_message}"
            )

            token_stream = llm.gerar_resposta_stream(
                chat_history=raw_history,
                sistema_prompt=sistema_prompt,
                user_message=user_message_marcada,
                image_b64=images_b64[0] if images_b64 else None,
                request_context=build_request_context(channel="control_center_chat", task_type="chat_normal"),
            )

            divider = SentenceDivider(faster_first_response=True)
            full_raw_response = []
            
            for chunk in divider.process_stream(token_stream):
                # Verifica cancelamento a cada chunk
                if _chat_cancel_event.is_set():
                    logger.info("[API] Resposta cancelada pelo usuario.")
                    break
                if chunk.is_thought:
                    if context.emotion_engine:
                        context.emotion_engine.processar_pensamento(chunk.thought)
                    full_raw_response.append(chunk.raw)
                else:
                    if context.emotion_engine:
                        for emo in chunk.emotions:
                            context.emotion_engine.processar_emocao(emo)
                    full_raw_response.append(chunk.raw)
                    # Stream tokens back to the frontend
                    await websocket.send_json({
                        "type": "chunk",
                        "content": chunk.text
                    })
                    
            ai_response = "".join(full_raw_response)
            
            # Processar as ações (Gerar Imagens/Músicas) no final do stream
            actions = extract_xml_actions(ai_response, (
                "gerar_imagem", 
                "gerar_imagem_personagem", 
                "editar_imagem", 
                "editar_imagem_personagem", 
                "gerar_musica"
            ))
            
            if any(actions.values()):
                logger.info(f"[API] Ações detectadas no chat: {list(actions.keys())}")

            media_results = []
            if context.image_gen:
                # 1. Geração simples
                for prompt_img in actions.get("gerar_imagem", []):
                    if prompt_img:
                        logger.info(f"[XML] Gerando imagem do Chat: {prompt_img[:80]}")
                        try:
                            img_path = context.image_gen.generate(prompt_img)
                            if img_path:
                                filename = os.path.basename(img_path)
                                media_results.append({"type": "image", "url": f"http://127.0.0.1:8042/media/images/{filename}"})
                        except Exception as e:
                            logger.error(f"[Chat] Erro gerando imagem: {e}")

                # 2. Geração de personagem (Lira)
                for payload in actions.get("gerar_imagem_personagem", []):
                    if payload:
                        logger.info(f"[XML] Gerando personagem do Chat")
                        try:
                            img_path = context.image_gen.generate_character(payload)
                            if img_path:
                                filename = os.path.basename(img_path)
                                media_results.append({"type": "image", "url": f"http://127.0.0.1:8042/media/images/{filename}"})
                        except Exception as e:
                            logger.error(f"[Chat] Erro gerando personagem: {e}")

            if context.music_gen:
                for prompt_music in actions.get("gerar_musica", []):
                    if prompt_music:
                        logger.info(f"[XML] Gerando música do Chat: {prompt_music[:80]}")
                        job_id = context.music_gen.submit(prompt_music, origin="gui_chat", request_meta={})
                        media_results.append({"type": "music", "job_id": job_id})
                        
            # Se for música, avisar front que iniciou e começar polling de status
            for m in media_results:
                await websocket.send_json({"type": "media", "media": m})
                if m["type"] == "music":
                    # Polling simplificado para o job de música
                    async def poll_music(jid, ws):
                        while True:
                            await asyncio.sleep(2)
                            status = context.music_gen.get_status(jid)
                            if status.get("state") == "completed":
                                filename = os.path.basename(status.get("output_path"))
                                await ws.send_json({
                                    "type": "media", 
                                    "media": {"type": "music", "job_id": jid, "url": f"http://127.0.0.1:8042/media/music/{filename}"}
                                })
                                break
                            elif status.get("state") in ["failed", "cancelled"]:
                                break
                    asyncio.create_task(poll_music(m["job_id"], websocket))

            # Salva na memória global para manter sincronizado com o Terminal
            if context.memory_manager:
                context.memory_manager.add_interaction("Amarinth", user_message)
                context.memory_manager.add_interaction("Lira", ai_response)

            await websocket.send_json({"type": "done"})

    except WebSocketDisconnect:
        logger.info("[API] WebSocket Chat desconectado.")
    except Exception as e:
        logger.error(f"[API] Erro no WebSocket Chat: {e}")


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    logger.info("[API] WebSocket Chat Tauri conectado.")
    try:
        while True:
            _chat_cancel_event.clear()

            data = json.loads(await websocket.receive_text())
            user_message = str(data.get("text") or "").strip()
            raw_images = data.get("images_b64", [])
            if not isinstance(raw_images, list):
                raw_images = []

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
            context = app.state.lira
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

            if context.memory_manager and visible_ai_response:
                context.memory_manager.add_interaction("Amarinth", user_message)
                context.memory_manager.add_interaction("Lira", visible_ai_response)

            await websocket.send_json({"type": "done"})

    except WebSocketDisconnect:
        logger.info("[API] WebSocket Chat Tauri desconectado.")
    except Exception as exc:
        logger.exception("[API] Erro no WebSocket Chat Tauri: %s", exc)


# === STATUS WEBSOCKET ===

async def status_generator(websocket: WebSocket):
    while True:
        try:
            cpu = psutil.cpu_percent(interval=0)
            ram = psutil.virtual_memory()
            
            # Lê configs ativas para os Módulos
            llm_provider = CONFIG.get("LLM_PROVIDER", "openai")
            tts_provider = CONFIG.get("TTS_PROVIDER", "elevenlabs")
            
            providers = CONFIG.get("LLM_PROVIDERS", {})
            provider_data = providers.get(llm_provider, {}) if isinstance(providers, dict) else {}
            llm_model = provider_data.get("modelo", "gpt-4o") if isinstance(provider_data, dict) else "gpt-4o"
            
            status_data = {
                "cpu": cpu,
                "ramPercent": ram.percent,
                "ramUsedStr": f"{ram.used / (1024**3):.1f}",
                "ramTotalStr": f"{ram.total / (1024**3):.1f}",
                "llmProvider": llm_provider.upper(),
                "llmModel": llm_model,
                "ttsProvider": tts_provider.upper(),
                "modules": {
                    "llm": True,
                    "tts": CONFIG.get("TTS_ATIVO", True),
                    "stt": CONFIG.get("STT_ATIVO", True),
                    "visao": CONFIG.get("VISAO_ATIVA", False),
                    "vtube_studio": CONFIG.get("VTUBESTUDIO_ATIVO", False),
                    "discord": CONFIG.get("Modo_discord", False)
                }
            }
            
            try:
                await websocket.send_json(status_data)
            except:
                break
            await asyncio.sleep(2)
        except Exception as e:
            logger.debug(f"[API] Erro silenciado no gerador de status: {e}")
            break


@app.websocket("/ws/emotions")
async def websocket_emotions(websocket: WebSocket):
    await websocket.accept()
    logger.info("[API] WebSocket Emoções conectado.")
    
    # Arquivo de estado IPC
    STATE_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "emotion_state.json"))
    last_ts = 0.0
    
    try:
        while True:
            if os.path.exists(STATE_FILE):
                try:
                    with open(STATE_FILE, "r", encoding="utf-8") as f:
                        state = json.load(f)
                    
                    current_ts = state.get("updated_at", 0)
                    if current_ts > last_ts:
                        try:
                            await websocket.send_json(state)
                            last_ts = current_ts
                        except:
                            break
                except Exception as e:
                    logger.debug(f"[API] Erro silenciado ao ler emotion_state.json: {e}")
            
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        logger.info("[API] WebSocket Emoções desconectado.")
    except Exception as e:
        logger.error(f"[API] Erro no WS Emoções: {e}")


@app.websocket("/ws/status")
async def websocket_status(websocket: WebSocket):
    await websocket.accept()
    logger.info("[API] WebSocket Status conectado.")
    try:
        await status_generator(websocket)
    except WebSocketDisconnect:
        logger.info("[API] WebSocket Status desconectado.")


# === CONFIG REST ENDPOINTS ===

def _model_spec_to_dict(model) -> dict:
    return {
        "id": model.id,
        "label": model.label,
        "provider": model.provider,
        "supportsVision": bool(model.supports_vision),
        "custom": False,
    }


def _voice_spec_to_dict(voice) -> dict:
    return {
        "id": voice.id,
        "label": voice.label,
        "provider": voice.provider,
        "supportsRate": bool(getattr(voice, "supports_rate", True)),
        "supportsPitch": bool(getattr(voice, "supports_pitch", True)),
        "pitchMode": getattr(voice, "pitch_mode", "native"),
    }


def _get_custom_models() -> list[dict]:
    raw_models = CONFIG.get("CUSTOM_LLM_MODELS", [])
    if not isinstance(raw_models, list):
        return []

    models: list[dict] = []
    for item in raw_models:
        if not isinstance(item, dict):
            continue

        provider = str(item.get("provider") or "").strip().lower()
        model_id = str(item.get("id") or "").strip()
        if not provider or not model_id:
            continue

        models.append({
            "id": model_id,
            "label": str(item.get("label") or model_id).strip() or model_id,
            "provider": provider,
            "supportsVision": bool(item.get("supportsVision", item.get("supports_vision", True))),
            "custom": True,
        })
    return models


@app.get("/api/catalog")
async def get_catalog():
    return {
        "llmProviders": get_llm_providers(),
        "ttsProviders": get_tts_providers(),
        "models": [_model_spec_to_dict(model) for model in MODEL_CATALOG] + _get_custom_models(),
        "voices": [_voice_spec_to_dict(voice) for voice in VOICE_CATALOG],
        "elevenlabsModels": [
            "eleven_flash_v2_5",
            "eleven_multilingual_v2",
            "eleven_turbo_v2_5",
            "eleven_v3",
        ],
        "openaiTtsModels": ["gpt-4o-mini-tts"],
    }


@app.post("/api/catalog/custom-models")
async def upsert_custom_model(payload: dict):
    provider = str(payload.get("provider") or "").strip().lower()
    model_id = str(payload.get("id") or "").strip()
    if not provider or not model_id:
        return {"status": "error", "message": "Provider e modelo sao obrigatorios."}

    custom_model = {
        "id": model_id,
        "label": str(payload.get("label") or model_id).strip() or model_id,
        "provider": provider,
        "supportsVision": bool(payload.get("supportsVision", True)),
        "custom": True,
    }
    custom_models = [
        model for model in _get_custom_models()
        if not (model["provider"] == provider and model["id"] == model_id)
    ]
    custom_models.append(custom_model)
    CONFIG["CUSTOM_LLM_MODELS"] = custom_models

    try:
        CONFIG.save()
    except Exception as e:
        return {"status": "error", "message": str(e)}

    return {"status": "ok", "model": custom_model}


@app.delete("/api/catalog/custom-models")
async def delete_custom_model(payload: dict):
    provider = str(payload.get("provider") or "").strip().lower()
    model_id = str(payload.get("id") or "").strip()
    if not provider or not model_id:
        return {"status": "error", "message": "Provider e modelo sao obrigatorios."}

    before = _get_custom_models()
    after = [
        model for model in before
        if not (model["provider"] == provider and model["id"] == model_id)
    ]
    CONFIG["CUSTOM_LLM_MODELS"] = after

    try:
        CONFIG.save()
    except Exception as e:
        return {"status": "error", "message": str(e)}

    return {"status": "ok", "removed": len(after) != len(before)}


@app.get("/api/config/llm")
async def get_llm_config():
    provider = CONFIG.get("LLM_PROVIDER", "openai")
    providers = CONFIG.get("LLM_PROVIDERS", {})
    provider_data = providers.get(provider, {}) if isinstance(providers, dict) else {}
    
    tts_provider = CONFIG.get("TTS_PROVIDER", "elevenlabs")
    tts_settings = CONFIG.get("TTS_SETTINGS", {})
    tts_data = tts_settings.get(tts_provider, {}) if isinstance(tts_settings, dict) else {}

    return {
        "llmProvider": provider,
        "llmModel": provider_data.get("modelo", ""),
        "llmFilter": "",
        "llmTemperature": CONFIG.get("LLM_TEMPERATURE", 0.85),
        "visionModel": provider_data.get("modelo_vision", ""),
        "ttsProvider": tts_provider,
        "ttsVoice": tts_data.get("voice_id", tts_data.get("voice", "")),
        "ttsModel": tts_data.get("model_id", tts_data.get("model", "")),
        "ttsFilter": "",
        "ttsSpeed": tts_data.get("rate", 1.0),
        "ttsPitch": tts_data.get("pitch", 0.0),
        "ttsStability": tts_data.get("stability", 0.5),
        "ttsSimilarity": tts_data.get("similarity_boost", 0.75),
        "ttsStyle": tts_data.get("style", 0.0),
        "ttsSpeakerBoost": tts_data.get("speaker_boost", True)
    }


@app.post("/api/config/llm")
async def update_llm_config(payload: dict):
    CONFIG["LLM_PROVIDER"] = payload.get("llmProvider", "openai")
    CONFIG["LLM_TEMPERATURE"] = payload.get("llmTemperature", 0.85)
    
    # Atualiza modelo do provider
    providers = CONFIG.get("LLM_PROVIDERS", {})
    if not isinstance(providers, dict): providers = {}
    provider = payload.get("llmProvider", "openai")
    block = providers.get(provider, {})
    if not isinstance(block, dict): block = {}
    block["modelo"] = payload.get("llmModel", "")
    block["modelo_chat"] = payload.get("llmModel", "")
    block["modelo_vision"] = payload.get("visionModel", "")
    providers[provider] = block
    CONFIG["LLM_PROVIDERS"] = providers

    # Atualiza TTS
    tts_provider = payload.get("ttsProvider", "elevenlabs")
    CONFIG["TTS_PROVIDER"] = tts_provider
    tts_settings = CONFIG.get("TTS_SETTINGS", {})
    if not isinstance(tts_settings, dict): tts_settings = {}
    tts_block = tts_settings.get(tts_provider, {})
    if not isinstance(tts_block, dict): tts_block = {}
    
    tts_block["voice"] = payload.get("ttsVoice", "")
    tts_block["rate"] = payload.get("ttsSpeed", 1.0)
    tts_block["pitch"] = payload.get("ttsPitch", 0.0)
    
    if tts_provider == "elevenlabs":
        tts_block["voice_id"] = payload.get("ttsVoice", "")
        tts_block["model_id"] = payload.get("ttsModel", "")
        tts_block["stability"] = payload.get("ttsStability", 0.5)
        tts_block["similarity_boost"] = payload.get("ttsSimilarity", 0.75)
        tts_block["style"] = payload.get("ttsStyle", 0.0)
        tts_block["speaker_boost"] = payload.get("ttsSpeakerBoost", True)
    
    tts_settings[tts_provider] = tts_block
    CONFIG["TTS_SETTINGS"] = tts_settings

    try:
        CONFIG.save()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/config/conexoes")
async def get_conexoes_config():
    return {
        "tts": CONFIG.get("TTS_ATIVO", True),
        "stt": CONFIG.get("STT_ATIVO", True),
        "ptt": CONFIG.get("GUI", {}).get("ptt_enabled", False),
        "pttKey": CONFIG.get("GUI", {}).get("ptt_key", "F2"),
        "stopHotkey": CONFIG.get("GUI", {}).get("stop_hotkey_enabled", True),
        "stopKey": CONFIG.get("GUI", {}).get("stop_hotkey", "F4"),
        "vts": CONFIG.get("VTUBESTUDIO_ATIVO", False),
        "discord": CONFIG.get("Modo_discord", False),
        "visao": CONFIG.get("VISAO_ATIVA", False)
    }

@app.get("/api/vts/state")
async def get_vts_state():
    STATE_PATH = os.path.abspath("data/vts_state.json")
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {"connected": False, "authenticated": False, "status": "offline"}

@app.post("/api/config/conexoes")
async def update_conexoes_config(payload: dict):
    CONFIG["TTS_ATIVO"] = payload.get("tts", True)
    CONFIG["STT_ATIVO"] = payload.get("stt", True)
    CONFIG["VTUBESTUDIO_ATIVO"] = payload.get("vts", False)
    CONFIG["Modo_discord"] = payload.get("discord", False)
    CONFIG["VISAO_ATIVA"] = payload.get("visao", False)
    
    gui_cfg = CONFIG.get("GUI", {})
    if not isinstance(gui_cfg, dict): gui_cfg = {}
    gui_cfg["ptt_enabled"] = payload.get("ptt", False)
    gui_cfg["ptt_key"] = payload.get("pttKey", "F2")
    gui_cfg["stop_hotkey_enabled"] = payload.get("stopHotkey", True)
    gui_cfg["stop_hotkey"] = payload.get("stopKey", "F4")
    CONFIG["GUI"] = gui_cfg

    try:
        CONFIG.save()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def start_server(host="0.0.0.0", port=8042, context=None):
    if context:
        app.state.lira.memory_manager = context.get("memory_manager")
        app.state.lira.llm_selector = context.get("llm_selector")
        app.state.lira.image_gen = context.get("image_gen")
        app.state.lira.music_gen = context.get("music_gen")
        app.state.lira.emotion_engine = context.get("emotion_engine")
        app.state.lira.tts = context.get("tts")
        app.state.lira.signals = context.get("signals")

    logger.info(f"[API] Iniciando servidor FastAPI em http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="warning")

if __name__ == "__main__":
    start_server()
