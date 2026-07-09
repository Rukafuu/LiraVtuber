import logging
import os
import threading
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tts", tags=["tts"])


class SpeakRequest(BaseModel):
    text: str


@router.post("/speak")
async def speak_tts(request: Request, payload: dict):
    """Reproduz TTS pelo backend e sinaliza lipsync para o VTube Studio."""
    text = str(payload.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Texto vazio.")

    context = request.app.state.lira
    if not CONFIG_ACTIVE_TTS(context):
        raise HTTPException(status_code=400, detail="TTS desativado ou nao configurado.")

    tts_engine = context.tts
    if tts_engine is None:
        from src.modules.voice.tts_selector import get_tts
        tts_engine = get_tts()
        context.tts = tts_engine

    if not tts_engine or not getattr(tts_engine, 'config_valida', True):
        raise HTTPException(status_code=500, detail="Motor TTS nao configurado ou invalido.")

    tts_timeout = float(os.getenv("TTS_CALL_TIMEOUT", "25"))

    def _run_tts():
        if context.signals is not None:
            try:
                context.signals.LIRA_SPEAKING = True
            except Exception:
                pass
        try:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                fut = pool.submit(tts_engine.falar, text)
                fut.result(timeout=tts_timeout)
        except Exception as exc:
            logger.error("[API] Erro/timeout TTS: %s", exc)
        finally:
            if context.signals is not None:
                try:
                    context.signals.LIRA_SPEAKING = False
                except Exception:
                    pass

    threading.Thread(target=_run_tts, daemon=True, name="GuiTTS").start()
    return {"status": "speaking"}


def CONFIG_ACTIVE_TTS(context) -> bool:
    from src.config.config_loader import CONFIG
    return CONFIG.get("TTS_ATIVO", True)
