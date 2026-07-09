import asyncio
import datetime
import logging
import os
import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config.config_loader import CONFIG
# Log handler registration
from apps.control_api.routers.system import memory_log_handler
logging.getLogger().addHandler(memory_log_handler)

logger = logging.getLogger(__name__)

app = FastAPI(title="Lira Control Center API", version="1.0")

# CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global context references
class AppContext:
    memory_manager = None
    llm_selector = None
    image_gen = None
    music_gen = None
    emotion_engine = None
    tts = None
    signals = None

app.state.lira = AppContext()

# Media directories mapping
PICTURES_DIR = os.path.join(os.path.expanduser("~"), "Pictures", "Lira Artista")
MUSIC_DIR = os.path.join(os.path.expanduser("~"), "Music", "Lira Music")

os.makedirs(PICTURES_DIR, exist_ok=True)
os.makedirs(MUSIC_DIR, exist_ok=True)

app.mount("/media/images", StaticFiles(directory=PICTURES_DIR), name="images")
app.mount("/media/music", StaticFiles(directory=MUSIC_DIR), name="music")

# Deprecated WhatsApp endpoints
_WHATSAPP_API_HINT = (
    "WhatsApp foi movido para a API dedicada. "
    "Inicie: python apps/whatsapp_api/main.py  |  "
    "Configure WHATSAPP_API_URL=http://127.0.0.1:8043 no bridge."
)

@app.post("/api/whatsapp/chat")
async def whatsapp_chat_deprecated(_payload: dict):
    return {
        "status": "error",
        "message": _WHATSAPP_API_HINT,
        "migrated_to": "whatsapp-api",
        "default_url": os.getenv("WHATSAPP_API_URL", "http://127.0.0.1:8043"),
    }

@app.post("/api/whatsapp/tts")
async def whatsapp_tts_deprecated(_payload: dict):
    return {
        "status": "error",
        "message": _WHATSAPP_API_HINT,
        "migrated_to": "whatsapp-api",
    }

# Register modular routers
from apps.control_api.routers.brain import router as brain_router
from apps.control_api.routers.chat import router as chat_router, ws_router as chat_ws_router
from apps.control_api.routers.memory import router as memory_router
from apps.control_api.routers.system import router as system_router, ws_router as system_ws_router
from apps.control_api.routers.catalog import router as catalog_router
from apps.control_api.routers.services import router as services_router
from apps.control_api.routers.mcp import router as mcp_router
from apps.control_api.routers.finance import router as finance_router
from apps.control_api.routers.voice_tts import router as voice_tts_router

app.include_router(brain_router)
app.include_router(chat_router)
app.include_router(chat_ws_router)
app.include_router(memory_router)
app.include_router(system_router)
app.include_router(system_ws_router)
app.include_router(catalog_router)
app.include_router(services_router)
app.include_router(mcp_router)
app.include_router(finance_router)
app.include_router(voice_tts_router)

def start_server(host="0.0.0.0", port=8042, context=None):
    if context:
        app.state.lira.memory_manager = context.get("memory_manager")
        app.state.lira.llm_selector = context.get("llm_selector")
        app.state.lira.image_gen = context.get("image_gen")
        app.state.lira.music_gen = context.get("music_gen")
        app.state.lira.emotion_engine = context.get("emotion_engine")
        app.state.lira.tts = context.get("tts")
        app.state.lira.signals = context.get("signals")
    else:
        from src.providers.provider_selector import ProviderSelector
        from src.modules.vision.image_gen import LiraImageGen

        light_start = os.getenv("CONTROL_API_LIGHT_START", "1").lower() in ("1", "true", "yes")
        rag_chroma = os.getenv("CONTROL_API_RAG_CHROMA", "0").lower() in ("1", "true", "yes")

        app.state.lira.llm_selector = ProviderSelector()
        app.state.lira.image_gen = LiraImageGen()

        def _create_memory_manager():
            from src.memory.memory_manager import LiraMemoryManager

            if light_start:
                return LiraMemoryManager(
                    enable_chroma=False,
                    sync_graph_to_rag=False,
                    defer_graph_sync=True,
                )
            return LiraMemoryManager(
                enable_chroma=rag_chroma,
                sync_graph_to_rag=True,
                defer_graph_sync=True,
            )

        async def init_heavy_modules():
            try:
                from src.modules.emotion_engine import EmotionEngine

                logger.info(
                    "[API] Memoria: light_start=%s chroma=%s (SQLite+grafo primeiro; Chroma depois)",
                    light_start,
                    rag_chroma,
                )
                app.state.lira.memory_manager = await asyncio.to_thread(_create_memory_manager)
                app.state.lira.emotion_engine = await asyncio.to_thread(EmotionEngine)

                if rag_chroma and app.state.lira.memory_manager:
                    logger.info("[API] ChromaDB/SentenceTransformer carregando em segundo plano...")
                    app.state.lira.memory_manager.rag.start_chroma_background()

                logger.info("[API] Motores prontos (API ja pode atender requisicoes).")
            except Exception as e:
                logger.error("[API] Erro ao carregar motores pesados: %s", e)

        import asyncio

        @app.on_event("startup")
        async def startup_event():
            asyncio.create_task(init_heavy_modules())

    if os.getenv("CONTROL_API_LIGHT_START", "1").lower() in ("1", "true", "yes"):
        logger.info(
            "[API] Modo leve ativo: servidor sobe rapido; Chroma opcional com CONTROL_API_RAG_CHROMA=1"
        )
    logger.info("[API] Iniciando servidor FastAPI em http://%s:%s", host, port)
    uvicorn.run(app, host=host, port=port, log_level="info")

if __name__ == "__main__":
    start_server()
