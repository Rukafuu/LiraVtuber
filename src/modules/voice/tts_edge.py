import os
import asyncio
import edge_tts
import pygame
import logging
from src.config.config_loader import CONFIG

logger = logging.getLogger(__name__)

if not pygame.mixer.get_init():
    pygame.mixer.init()

class MotorTTSEdge:
    def __init__(self):
        self.provedor = "edge"
        
        # Lê configurações do grupo 'edge' no config.json
        settings = CONFIG.get("TTS_SETTINGS", {}).get("edge", {})
        self.voice = settings.get("voice", "pt-BR-ThalitaNeural")
        self.rate = settings.get("rate", "+0%")
        self.pitch = settings.get("pitch", "+0Hz")
        self.volume = settings.get("volume", "+0%")
        self.config_valida = True # Edge TTS é público e não requer chave

    def falar(self, texto, tocar_local=True) -> bool:
        if not texto: return False
        try:
            from src.utils.text import limpar_texto_tts
            texto_limpo = limpar_texto_tts(str(texto))
            if not texto_limpo: return False

            output_file = "data/last_response.mp3"
            asyncio.run(self._generate_audio(texto_limpo, output_file))

            if tocar_local:
                pygame.mixer.music.load(output_file)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    pygame.time.Clock().tick(10)
                pygame.mixer.music.unload()
            return True
        except Exception as e:
            logger.error(f"[TTS EDGE] Erro: {e}")
            return False

    async def _generate_audio(self, texto, output_file):
        communicate = edge_tts.Communicate(texto, self.voice, rate=self.rate, volume=self.volume, pitch=self.pitch)
        await communicate.save(output_file)


