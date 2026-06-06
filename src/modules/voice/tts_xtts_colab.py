import logging
import os
import numpy as np
import pygame
import threading
import shutil
import tempfile
import soundfile as sf
from gradio_client import Client
from src.config.config_loader import CONFIG
from src.modules.voice import audio_control

logger = logging.getLogger(__name__)


class MotorTTSXTTSColab:
    def __init__(self):
        self.provedor = "xtts_colab"
        self.audio_disponivel = False
        self._stop_event = threading.Event()

        xtts_cfg = CONFIG.get("TTS_SETTINGS", {}).get("xtts_colab", {})
        self.api_url = xtts_cfg.get("url", "")
        self.speed = xtts_cfg.get("speed", 0.9)
        self.client = None

        if self.api_url:
            threading.Thread(target=self._init_client, daemon=True).start()

    def _init_client(self):
        try:
            logger.info(f"[XTTS-Colab] Conectando ao cliente Gradio em {self.api_url}...")
            self.client = Client(self.api_url)
            self.audio_disponivel = True
            audio_control.init_audio_mixer()
            logger.info("[XTTS-Colab] ✅ Conectado com sucesso!")
        except Exception as e:
            logger.warning(f"[XTTS-Colab] ❌ Erro ao conectar ao Gradio: {e}")

    def falar(self, texto: str, tocar_local=True) -> bool:
        if not self.client:
            logger.error("[XTTS-Colab] Cliente Gradio não inicializado. Verifique a URL.")
            return False

        try:
            self._stop_event.clear()
            audio_control.reset_stop_state()

            import re
            # Limpeza de emojis e tags do Discord
            texto_limpo = re.sub(r'<a?:\w+:\d+>', '', texto)
            texto_limpo = re.sub(r'<[^>]+>', '', texto_limpo)
            texto_limpo = re.sub(r'\[[^\]]+\]', '', texto_limpo)
            texto_limpo = re.sub(r'\{[^\}]+\}', '', texto_limpo)
            # Limpeza de risadas excessivas
            texto_limpo = re.sub(r'[kK]{4,}', 'kkk', texto_limpo)
            texto_limpo = re.sub(r'[hH]{4,}', 'hhh', texto_limpo)
            texto_limpo = texto_limpo.strip()

            if not texto_limpo:
                return False

            logger.info(f"[XTTS-Colab] Solicitando áudio para: {texto_limpo[:40]}...")

            # Correções fonéticas para PT-BR
            correcoes = {
                "GitHub": "Git Râbi", "github": "Git Râbi",
                "Python": "Páiton", "python": "Páiton",
                "Lucas": "Lúcas",
            }
            for errado, certo in correcoes.items():
                texto_limpo = texto_limpo.replace(errado, certo)

            # Divide em frases para evitar timeout
            sentences = re.split(r'(?<=[.!?]) +', texto_limpo)
            sentences = [s.strip() for s in sentences if s.strip()]

            if not sentences:
                return None

            last_path = None
            for i, sentence in enumerate(sentences):
                logger.info(f"[XTTS-Colab] Processando frase {i+1}/{len(sentences)}: {sentence[:40]}...")

                try:
                    result = self.client.predict(
                        sentence,
                        self.speed,
                        api_name="/prever"
                    )
                except Exception as e:
                    logger.error(f"[XTTS-Colab] Falha na API Gradio (frase {i+1}): {e}")
                    continue

                # XTTS retorna (sample_rate, numpy_array) → Gradio serializa como arquivo
                result_path = None
                if isinstance(result, str) and os.path.exists(result):
                    result_path = result
                elif isinstance(result, dict):
                    for key in ("path", "name", "url"):
                        candidate = result.get(key, "")
                        if candidate and os.path.exists(candidate):
                            result_path = candidate
                            break

                if result_path:
                    import time
                    timestamp = int(time.time() * 1000)
                    target_path = f"data/response_{timestamp}.wav"
                    shutil.copy(result_path, target_path)
                    last_path = target_path

                    if tocar_local:
                        try:
                            if pygame.mixer.music.get_busy():
                                pygame.mixer.music.stop()
                            pygame.mixer.music.unload()
                            pygame.mixer.music.load(target_path)
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
                        except Exception as e:
                            logger.error(f"[XTTS-Colab] Erro ao tocar áudio: {e}")
                else:
                    logger.warning(f"[XTTS-Colab] Resultado inválido para frase {i+1}: {result}")

            return last_path is not None

        except Exception as e:
            logger.error(f"[XTTS-Colab] Erro geral: {e}")
            return False

    def parar(self) -> bool:
        self._stop_event.set()
        try:
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
        except Exception:
            pass
        return True
