import logging
import os
import threading

from google.cloud import texttospeech
import pygame

from src.config.config_loader import CONFIG
from src.modules.voice import audio_control

logger = logging.getLogger(__name__)


class MotorTTSGoogle:
    def __init__(self):
        self.provedor = "google"
        self.audio_disponivel = False
        self._stop_event = threading.Event()

        settings = CONFIG.get("TTS_SETTINGS", {}).get("google", {})
        if not isinstance(settings, dict):
            settings = {}

        credenciais = CONFIG.get("GOOGLE_APPLICATION_CREDENTIALS")
        if credenciais:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credenciais

        try:
            self.client = texttospeech.TextToSpeechClient()
            self.config_valida = True
            logger.info("[TTS] MODO GOOGLE CLOUD pronto.")
        except Exception as e:
            logger.error(f"[TTS] Google falhou: {e}")
            self.config_valida = False

        self.language_code = settings.get("language_code", CONFIG.get("GOOGLE_TTS_LANG", "pt-BR"))
        self.voice_name = settings.get("voice", CONFIG.get("GOOGLE_TTS_VOICE", "pt-BR-Neural2-C"))
        self.speaking_rate = float(settings.get("rate", CONFIG.get("GOOGLE_TTS_RATE", 1.25)))
        self.pitch = float(settings.get("pitch", CONFIG.get("GOOGLE_TTS_PITCH", 1.4)))

        try:
            pygame.mixer.init()
            self.audio_disponivel = True
        except Exception as e:
            logger.warning(
                f"[TTS] Mixer de audio indisponivel. O TTS ainda pode sintetizar sem tocar localmente: {e}"
            )

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

            input_text = texttospeech.SynthesisInput(ssml=f"<speak>{texto_limpo}</speak>")
            voice = texttospeech.VoiceSelectionParams(
                language_code=self.language_code,
                name=self.voice_name,
            )
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3,
                pitch=self.pitch,
                speaking_rate=self.speaking_rate,
            )

            response = self.client.synthesize_speech(
                input=input_text,
                voice=voice,
                audio_config=audio_config,
            )

            with open("data/last_response.mp3", "wb") as f:
                f.write(response.audio_content)

            if self._stop_event.is_set() or audio_control.stop_requested():
                return True
            if tocar_local and self.audio_disponivel:
                pygame.mixer.music.load("data/last_response.mp3")
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
            elif tocar_local:
                logger.warning("[TTS] Audio local desabilitado porque o mixer nao foi inicializado.")

            return True
        except Exception as e:
            logger.error(f"[GOOGLE TTS] Erro de sintese: {e}")
            return False

    def parar(self) -> bool:
        self._stop_event.set()
        try:
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
        except Exception:
            pass
        return True
