"""
Seletor de TTS com hot-swap, persistencia por provider e fallback dinamico.
"""

from __future__ import annotations

import logging
import os
import re
import threading

from src.config.config_loader import CONFIG
from src.core.provider_catalog import get_tts_providers

logger = logging.getLogger(__name__)

_swap_lock = threading.Lock()
_play_lock = threading.Lock()
_instancia_ativa = None


def _ensure_tts_settings() -> dict:
    tts_settings = CONFIG.get("TTS_SETTINGS", {})
    if not isinstance(tts_settings, dict):
        tts_settings = {}

    eleven_cfg = tts_settings.get("elevenlabs", {})
    if not isinstance(eleven_cfg, dict):
        eleven_cfg = {}
    eleven_cfg.setdefault("voice_id", str(eleven_cfg.get("voice") or CONFIG.get("ELEVENLABS_VOICE_ID", "UqJBeKrjGrdsP4JSZ7w6")).strip())
    eleven_cfg.setdefault("voice", eleven_cfg.get("voice_id", ""))
    if not str(eleven_cfg.get("model_id") or "").strip() or str(eleven_cfg.get("model_id")).strip() == "eleven_turbo_v2_5":
        eleven_cfg["model_id"] = "eleven_flash_v2_5"
    eleven_cfg.setdefault("rate", 1.1)
    eleven_cfg.setdefault("pitch", 0.0)
    eleven_cfg.setdefault("stability", 0.5)
    eleven_cfg.setdefault("similarity_boost", 0.75)
    eleven_cfg.setdefault("style", 0.0)
    eleven_cfg.setdefault("speaker_boost", True)
    tts_settings["elevenlabs"] = eleven_cfg

    google_cfg = tts_settings.get("google", {})
    if not isinstance(google_cfg, dict):
        google_cfg = {}
    google_cfg.setdefault("voice", CONFIG.get("GOOGLE_TTS_VOICE", "pt-BR-Neural2-C"))
    google_cfg.setdefault("language_code", CONFIG.get("GOOGLE_TTS_LANG", "pt-BR"))
    google_cfg.setdefault("rate", float(CONFIG.get("GOOGLE_TTS_RATE", 1.25)))
    google_cfg.setdefault("pitch", float(CONFIG.get("GOOGLE_TTS_PITCH", 1.4)))
    tts_settings["google"] = google_cfg

    edge_cfg = tts_settings.get("edge", {})
    if not isinstance(edge_cfg, dict):
        edge_cfg = {}
    edge_cfg.setdefault("voice", "pt-BR-ThalitaNeural")
    edge_cfg.setdefault("rate", "+0%")
    edge_cfg.setdefault("pitch", "+0Hz")
    edge_cfg.setdefault("volume", "+0%")
    tts_settings["edge"] = edge_cfg

    azure_cfg = tts_settings.get("azure", {})
    if not isinstance(azure_cfg, dict):
        azure_cfg = {}
    azure_cfg.setdefault("voice", "pt-BR-ThalitaNeural")
    azure_cfg.setdefault("rate", "+0%")
    azure_cfg.setdefault("pitch", "0Hz")
    tts_settings["azure"] = azure_cfg

    openai_cfg = tts_settings.get("openai", {})
    if not isinstance(openai_cfg, dict):
        openai_cfg = {}
    openai_cfg.setdefault("model", "gpt-4o-mini-tts")
    openai_cfg.setdefault("voice", "coral")
    openai_cfg.setdefault("rate", 1.0)
    openai_cfg.setdefault("pitch", 0.0)
    openai_cfg.setdefault("style", "natural e clara")
    tts_settings["openai"] = openai_cfg

    CONFIG["TTS_SETTINGS"] = tts_settings
    if not str(CONFIG.get("TTS_PROVIDER", "") or "").strip():
        CONFIG["TTS_PROVIDER"] = _default_provider_from_settings(tts_settings)
    return tts_settings


def get_tts_settings() -> dict:
    return _ensure_tts_settings()


def _default_provider_from_settings(tts_settings: dict) -> str:
    eleven_cfg = tts_settings.get("elevenlabs", {}) if isinstance(tts_settings, dict) else {}
    voice_id = ""
    if isinstance(eleven_cfg, dict):
        voice_id = str(eleven_cfg.get("voice_id") or eleven_cfg.get("voice") or "").strip()
    if (os.getenv("ELEVENLABS_API_KEY") or CONFIG.get("ELEVENLABS_API_KEY")) and voice_id:
        return "elevenlabs"
    return "google"


class TTSWrapper:
    """Wrapper que prioriza o provider ativo e tenta os demais como fallback."""

    def __init__(self, provider_inicial: str):
        self.instancias = {}
        self.provedor = provider_inicial
        _ensure_tts_settings()
        self._set_provider_chain(self.provedor)
        self._instanciar(self.provedor)

    def _set_provider_chain(self, primario: str):
        primary = (primario or "google").lower()
        self._provider_chain = [primary] + [provider for provider in get_tts_providers() if provider != primary]

    def _instanciar(self, prov: str):
        if prov in self.instancias:
            return self.instancias[prov]
        nova_instancia = _criar_tts(prov)
        self.instancias[prov] = nova_instancia
        return nova_instancia

    def falar(self, texto: str, tocar_local=True) -> bool:
        if re.search(r'\{.*"acao".*\}', texto, re.DOTALL) or re.search(
            r"function_call|gerar_ou_editar_imagem|gerar_imagem|editar_imagem|gerar_musica|acao_pc|<tool_code>|```",
            texto,
        ):
            return True

        with _play_lock:
            for prov in self._provider_chain:
                try:
                    instancia = self._instanciar(prov)
                    if hasattr(instancia, "config_valida") and not instancia.config_valida:
                        continue
                    sucesso = instancia.falar(texto, tocar_local)
                    if sucesso:
                        self.provedor = prov
                        return True
                    logger.warning("[TTS WRAPPER] %s falhou. Tentando proximo...", prov.upper())
                except Exception as exc:
                    logger.error("[TTS WRAPPER] Erro ao usar %s: %s", prov.upper(), exc)
            return False

    def parar(self) -> bool:
        stopped = False
        for instancia in list(self.instancias.values()):
            try:
                if hasattr(instancia, "parar") and instancia.parar():
                    stopped = True
            except Exception as exc:
                logger.warning("[TTS WRAPPER] Falha ao parar instancia TTS: %s", exc)
        return stopped


def get_tts(provedor: str = None, force_reload: bool = False):
    global _instancia_ativa
    prov = (provedor or CONFIG.get("TTS_PROVIDER", "google")).lower()
    with _swap_lock:
        _ensure_tts_settings()
        if _instancia_ativa is None:
            _instancia_ativa = TTSWrapper(prov)
        else:
            _instancia_ativa.provedor = prov
            _instancia_ativa._set_provider_chain(prov)
            if force_reload:
                _instancia_ativa.instancias.pop(prov, None)
            _instancia_ativa._instanciar(prov)
        return _instancia_ativa


def _criar_tts(prov: str):
    provider = (prov or "google").lower()
    if provider == "elevenlabs":
        from src.modules.voice.tts_elevenlabs import MotorTTSElevenLabs

        return MotorTTSElevenLabs()
    if provider == "google":
        from src.modules.voice.tts_google import MotorTTSGoogle

        return MotorTTSGoogle()
    if provider == "edge":
        from src.modules.voice.tts_edge import MotorTTSEdge

        return MotorTTSEdge()
    if provider == "azure":
        from src.modules.voice.tts_azure import MotorTTSAzure

        return MotorTTSAzure()
    if provider == "openai":
        from src.modules.voice.tts_openai import MotorTTSOpenAI

        return MotorTTSOpenAI()
    return _DummyTTS()


class _DummyTTS:
    def __init__(self):
        self.config_valida = True
        self.provedor = "offline"

    def falar(self, texto, tocar_local=True):
        print(f"[TTS OFFLINE] {texto}")
        return False

    def parar(self):
        return False
