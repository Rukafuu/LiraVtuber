import os
import asyncio
import threading
import edge_tts
import pygame
import logging
from src.config.config_loader import CONFIG
from src.modules.voice import audio_control

logger = logging.getLogger(__name__)

from src.modules.voice import audio_control
audio_control.init_audio_mixer()

class MotorTTSEdge:
    def __init__(self):
        self.provedor = "edge"
        self._stop_event = threading.Event()
        
        # Lê configurações do grupo 'edge' no config.json
        settings = CONFIG.get("TTS_SETTINGS", {}).get("edge", {})
        self.voice = settings.get("voice", "pt-BR-ThalitaNeural")
        self.rate = str(settings.get("rate") or "+0%")
        self.pitch = str(settings.get("pitch") or "+0Hz")
        self.volume = str(settings.get("volume") or "+0%")
        self.config_valida = True # Edge TTS é público e não requer chave

    def falar(self, texto, tocar_local=True) -> bool:
        if not texto: return False
        try:
            from src.utils.text import limpar_texto_tts
            texto_limpo = limpar_texto_tts(str(texto))
            if not texto_limpo: return False

            self._stop_event.clear()
            audio_control.reset_stop_state()

            import time
            timestamp = int(time.time() * 1000)
            output_file = f"data/response_{timestamp}.mp3"
            print(f"[DEBUG TTS EDGE] Texto para voz: {texto_limpo[:30]}...", flush=True)
            
            def run_tts_thread(text, path):
                try:
                    asyncio.run(self._generate_audio(text, path))
                    print(f"[DEBUG TTS EDGE] Arquivo gerado com sucesso: {path}", flush=True)
                except Exception as e:
                    print(f"[DEBUG TTS EDGE] FALHA NA THREAD TTS: {e}", flush=True)

            t = threading.Thread(target=run_tts_thread, args=(texto_limpo, output_file))
            t.start()
            t.join(timeout=15) 

            if not os.path.exists(output_file) or os.path.getsize(output_file) == 0:
                print(f"[DEBUG TTS EDGE] Falha no Edge. Tentando FALLBACK para Google TTS...", flush=True)
                try:
                    from src.modules.voice.tts_google import MotorTTSGoogle
                    google_tts = MotorTTSGoogle()
                    success = google_tts.falar(texto_limpo, tocar_local=False)
                    if success:
                        # O Google TTS também deve retornar um caminho válido no futuro, 
                        # mas por enquanto vamos focar no Edge.
                        return "data/last_response.wav" 
                except Exception as gerr:
                    print(f"[DEBUG TTS FALLBACK] Erro no fallback Google: {gerr}", flush=True)
                return False

            if self._stop_event.is_set() or audio_control.stop_requested():
                return output_file
            
            if tocar_local:
                try:
                    if pygame.mixer.music.get_busy():
                        pygame.mixer.music.stop()
                    pygame.mixer.music.unload()
                    pygame.mixer.music.load(output_file)
                    pygame.mixer.music.play()
                    while pygame.mixer.music.get_busy():
                        if self._stop_event.is_set() or audio_control.stop_requested():
                            pygame.mixer.music.stop()
                            break
                        pygame.time.Clock().tick(10)
                    pygame.mixer.music.unload()
                except Exception as mixer_err:
                    logger.error(f"[TTS EDGE] Erro no mixer: {mixer_err}")

            # Limpeza de arquivos antigos
            try:
                import glob
                audios = sorted(glob.glob("data/response_*.mp3"))
                if len(audios) > 5:
                    for old_audio in audios[:-5]:
                        if old_audio != output_file:
                            os.remove(old_audio)
            except: pass

            return output_file
        except Exception as e:
            logger.error(f"[TTS EDGE] Erro: {e}")
            return False

    async def _generate_audio(self, texto, output_file):
        communicate = edge_tts.Communicate(texto, self.voice, rate=self.rate, volume=self.volume, pitch=self.pitch)
        await communicate.save(output_file)

    def parar(self) -> bool:
        self._stop_event.set()
        try:
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
        except Exception:
            pass
        return True


