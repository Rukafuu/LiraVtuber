import logging
import os
import threading

import pygame
from openai import OpenAI

from src.config.config_loader import CONFIG
from src.modules.voice import audio_control

logger = logging.getLogger(__name__)


class MotorTTSOpenAI:
    def __init__(self):
        self.provedor = "openai"
        self.audio_disponivel = False
        self._stop_event = threading.Event()

        settings = CONFIG.get("TTS_SETTINGS", {}).get("openai", {})
        self.model = settings.get("model", "gpt-4o-mini-tts")
        self.voice = settings.get("voice", "coral")
        self.rate = float(settings.get("rate", 1.0))
        self.pitch = float(settings.get("pitch", 0.0))
        self.style = settings.get("style", "natural e clara")

        api_key = os.getenv("OPENAI_API_KEY") or CONFIG.get("OPENAI_API_KEY")
        if not api_key:
            logger.error("[TTS] OPENAI_API_KEY ausente.")
            self.client = None
            self.config_valida = False
        else:
            self.client = OpenAI(api_key=api_key)
            self.config_valida = True

        try:
            pygame.mixer.init()
            self.audio_disponivel = True
        except Exception as e:
            logger.warning("[TTS OPENAI] Mixer indisponível: %s", e)

    def _style_instruction(self) -> str:
        tone = "mais grave e aveludado" if self.pitch <= -8 else "mais agudo e brilhante" if self.pitch >= 8 else "equilibrado e natural"
        if -8 < self.pitch <= -3:
            tone = "levemente mais grave"
        elif 3 <= self.pitch < 8:
            tone = "levemente mais agudo"
        return f"Fale em português do Brasil, com articulação clara, tom {tone} e estilo {self.style}."

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

            os.makedirs("data", exist_ok=True)
            output_file = os.path.abspath(os.path.join("data", "last_response_openai.mp3"))
            try:
                response = self.client.audio.speech.create(
                    model=self.model,
                    voice=self.voice,
                    input=texto_limpo,
                    speed=self.rate,
                    response_format="mp3",
                    instructions=self._style_instruction(),
                )
            except TypeError:
                response = self.client.audio.speech.create(
                    model=self.model,
                    voice=self.voice,
                    input=texto_limpo,
                    speed=self.rate,
                    format="mp3",
                    instructions=self._style_instruction(),
                )

            if hasattr(response, "stream_to_file"):
                response.stream_to_file(output_file)
            elif hasattr(response, "write_to_file"):
                response.write_to_file(output_file)
            else:
                audio_bytes = getattr(response, "content", None)
                if audio_bytes is None and hasattr(response, "read"):
                    audio_bytes = response.read()
                if not audio_bytes:
                    raise RuntimeError("A resposta da OpenAI TTS veio sem áudio.")
                with open(output_file, "wb") as file:
                    file.write(audio_bytes)

            if self._stop_event.is_set() or audio_control.stop_requested():
                return True
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
        except Exception as e:
            logger.error("[TTS OPENAI] Erro: %s", e)
            return False

    def parar(self) -> bool:
        self._stop_event.set()
        try:
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
        except Exception:
            pass
        return True
