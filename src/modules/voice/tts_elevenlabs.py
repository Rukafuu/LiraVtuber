from __future__ import annotations

import json
import logging
import os
import threading
import urllib.error
import urllib.parse
import urllib.request

import pygame

from src.config.config_loader import CONFIG
from src.modules.voice import audio_control

logger = logging.getLogger(__name__)


class MotorTTSElevenLabs:
    def __init__(self):
        self.provedor = "elevenlabs"
        self.audio_disponivel = False
        self._stop_event = threading.Event()

        settings = CONFIG.get("TTS_SETTINGS", {}).get("elevenlabs", {})
        if not isinstance(settings, dict):
            settings = {}

        self.api_key = os.getenv("ELEVENLABS_API_KEY") or CONFIG.get("ELEVENLABS_API_KEY")
        self.voice_id = str(settings.get("voice_id") or settings.get("voice") or "").strip()
        self.model_id = str(settings.get("model_id") or "eleven_flash_v2_5").strip() or "eleven_flash_v2_5"
        self.speed = self._clamp_float(settings.get("rate", 1.1), 0.7, 1.2, 1.1)
        self.stability = self._clamp_float(settings.get("stability", 0.5), 0.0, 1.0, 0.5)
        self.similarity_boost = self._clamp_float(settings.get("similarity_boost", 0.75), 0.0, 1.0, 0.75)
        self.style = self._clamp_float(settings.get("style", 0.0), 0.0, 1.0, 0.0)
        self.speaker_boost = bool(settings.get("speaker_boost", True))

        self.config_valida = bool(self.api_key and self.voice_id)
        if not self.config_valida:
            logger.warning("[TTS ELEVENLABS] Configuracao incompleta. API key ou voice_id ausente.")

        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            self.audio_disponivel = True
        except Exception as exc:
            logger.warning("[TTS ELEVENLABS] Mixer indisponivel: %s", exc)

    @staticmethod
    def _clamp_float(value, minimum: float, maximum: float, default: float) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            parsed = default
        return max(minimum, min(maximum, parsed))

    def _request_url(self) -> str:
        query = urllib.parse.urlencode({"output_format": "mp3_44100_128"})
        return f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}?{query}"

    def _build_payload(self, texto: str) -> bytes:
        payload = {
            "text": texto,
            "model_id": self.model_id,
            "language_code": "pt",
            "voice_settings": {
                "speed": self.speed,
                "stability": self.stability,
                "similarity_boost": self.similarity_boost,
                "style": self.style,
                "use_speaker_boost": self.speaker_boost,
            },
        }
        return json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def falar(self, texto_cru: str, tocar_local=True) -> bool:
        if not self.config_valida or not texto_cru:
            return False

        try:
            from src.utils.text import limpar_texto_tts

            texto_limpo = limpar_texto_tts(str(texto_cru))
            if not texto_limpo:
                return False

            self._stop_event.clear()
            audio_control.reset_stop_state()

            request = urllib.request.Request(
                self._request_url(),
                data=self._build_payload(texto_limpo),
                headers={
                    "Content-Type": "application/json",
                    "xi-api-key": self.api_key,
                    "Accept": "audio/mpeg",
                },
                method="POST",
            )

            with urllib.request.urlopen(request, timeout=120) as response:
                audio_bytes = response.read()

            if self._stop_event.is_set() or audio_control.stop_requested():
                return True

            os.makedirs("data", exist_ok=True)
            output_file = os.path.abspath(os.path.join("data", "last_response_elevenlabs.mp3"))
            with open(output_file, "wb") as file:
                file.write(audio_bytes)

            if tocar_local and self.audio_disponivel:
                pygame.mixer.music.load(output_file)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    if self._stop_event.is_set() or audio_control.stop_requested():
                        pygame.mixer.music.stop()
                        break
                    pygame.time.Clock().tick(10)
                try:
                    pygame.mixer.music.unload()
                except Exception:
                    pass
            return True
        except urllib.error.HTTPError as exc:
            try:
                details = exc.read().decode("utf-8", errors="ignore")
            except Exception:
                details = str(exc)
            logger.error("[TTS ELEVENLABS] HTTP %s: %s", exc.code, details)
            return False
        except Exception as exc:
            logger.error("[TTS ELEVENLABS] Erro: %s", exc)
            return False

    def parar(self) -> bool:
        self._stop_event.set()
        try:
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
        except Exception:
            pass
        return True
