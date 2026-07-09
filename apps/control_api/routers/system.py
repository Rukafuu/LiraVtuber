import asyncio
import datetime
import json
import logging
import os
import psutil
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.config.config_loader import CONFIG
from apps.control_api.service_manager import service_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["system"])
ws_router = APIRouter(tags=["system_ws"])


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


memory_log_handler = MemoryLogHandler()


@router.get("/api/logs")
async def get_system_logs(limit: int = 100):
    """Retorna os logs mais recentes interceptados pelo servidor Python."""
    return {"logs": memory_log_handler.logs[-limit:]}


@router.get("/api/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.datetime.utcnow().isoformat() + "Z"}


# === WATCHDOG ENDPOINTS ===

@router.get("/api/watchdog/heartbeat")
async def get_watchdog_heartbeat():
    from apps.control_api import watchdog_state
    return watchdog_state.get_status()


@router.post("/api/watchdog/heartbeat")
async def post_watchdog_heartbeat(payload: dict):
    from apps.control_api import watchdog_state
    return watchdog_state.record_heartbeat(payload)


# === STATUS REST AND WEBSOCKET ===

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

            svc = service_manager.status_all().get("services", [])
            discord_up = next(
                (s for s in svc if s["id"] == "discord" and s["state"] in ("running", "starting", "degraded")),
                None,
            )
            wa_up = next(
                (s for s in svc if s["id"] == "whatsapp_bridge" and s["state"] == "running"),
                None,
            )
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
                    "discord": bool(discord_up),
                    "whatsapp": bool(wa_up),
                },
                "services": svc,
            }

            try:
                await websocket.send_json(status_data)
            except Exception:
                break
            await asyncio.sleep(2)
        except Exception as e:
            logger.debug(f"[API] Erro silenciado no gerador de status: {e}")
            break


@router.get("/api/status")
async def get_status_api():
    cpu = psutil.cpu_percent(interval=0)
    ram = psutil.virtual_memory()
    llm_provider = CONFIG.get("LLM_PROVIDER", "openai")
    tts_provider = CONFIG.get("TTS_PROVIDER", "elevenlabs")

    providers = CONFIG.get("LLM_PROVIDERS", {})
    provider_data = providers.get(llm_provider, {}) if isinstance(providers, dict) else {}
    llm_model = provider_data.get("modelo", "gpt-4o") if isinstance(provider_data, dict) else "gpt-4o"

    svc = service_manager.status_all().get("services", [])
    discord_up = next(
        (s for s in svc if s["id"] == "discord" and s["state"] in ("running", "starting", "degraded")),
        None,
    )
    wa_up = next(
        (s for s in svc if s["id"] == "whatsapp_bridge" and s["state"] == "running"),
        None,
    )
    return {
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
            "discord": bool(discord_up),
            "whatsapp": bool(wa_up),
        },
        "services": svc,
    }


@ws_router.websocket("/ws/status")
async def websocket_status(websocket: WebSocket):
    await websocket.accept()
    logger.info("[API] WebSocket Status conectado.")
    try:
        await status_generator(websocket)
    except WebSocketDisconnect:
        logger.info("[API] WebSocket Status desconectado.")


@ws_router.websocket("/ws/emotions")
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
                        except Exception:
                            break
                except Exception as e:
                    logger.debug(f"[API] Erro silenciado ao ler emotion_state.json: {e}")

            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        logger.info("[API] WebSocket Emoções desconectado.")
    except Exception as e:
        logger.error(f"[API] Erro no WS Emoções: {e}")
