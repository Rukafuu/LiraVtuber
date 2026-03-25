import os
import logging
import time
import xml.sax.saxutils as saxutils
from src.config.config_loader import CONFIG

logger = logging.getLogger(__name__)

try:
    import azure.cognitiveservices.speech as speechsdk
except ImportError:
    speechsdk = None

class MotorTTSAzure:
    def __init__(self):
        self.provedor = "azure"
        
        self.chave = CONFIG.get("AZURE_SPEECH_KEY")
        self.regiao = CONFIG.get("AZURE_REGION")
        
        # Lê configurações do grupo 'azure' no config.json
        settings = CONFIG.get("TTS_SETTINGS", {}).get("azure", {})
        self.voz = settings.get("voice", "pt-BR-ThalitaNeural")
        self.rate = settings.get("rate", "+0%")
        self.pitch = settings.get("pitch", "0Hz")

        if not self.chave or not self.regiao or not speechsdk:
            logger.error("[TTS] Chaves da Azure ausentes ou SDK não instalada.")
            self.config_valida = False
        else:
            try:
                self.speech_config = speechsdk.SpeechConfig(subscription=self.chave, region=self.regiao)
                self.speech_config.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Raw16Khz16BitMonoPcm)
                self.sintetizador = speechsdk.SpeechSynthesizer(speech_config=self.speech_config, audio_config=None)
                self.config_valida = True
                logger.info("[TTS] ⚙️ MODO AZURE inicializado.")
            except Exception as e:
                logger.error(f"[TTS] Erro Azure: {e}")
                self.config_valida = False

    def falar(self, texto: str, tocar_local=True) -> bool:
        if not self.config_valida or not texto:
            return False

        try:
            from src.utils.text import limpar_texto_tts
            texto_limpo = limpar_texto_tts(str(texto))
            if not texto_limpo: return False

            texto_escapado = saxutils.escape(texto_limpo)
            ssml = f"""
            <speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="pt-BR">
                <voice name="{self.voz}">
                    <prosody rate="{self.rate}" pitch="{self.pitch}">
                        {texto_escapado}
                    </prosody>
                </voice>
            </speak>
            """

            resultado = self.sintetizador.speak_ssml_async(ssml).get()

            if resultado.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                audio_buffer = resultado.audio_data
                
                if len(audio_buffer) > 0 and tocar_local:
                    import numpy as np
                    import sounddevice as sd
                    
                    audio_np = np.frombuffer(audio_buffer, dtype=np.int16)
                    sd.play(audio_np, samplerate=16000)
                    sd.wait()
                    return True
                
            elif resultado.reason == speechsdk.ResultReason.Canceled:
                logger.error(f"[TTS AZURE] Cancelado: {resultado.cancellation_details.reason}")

            return False

        except Exception as e:
            logger.error(f"[TTS AZURE] Erro: {e}")
            return False
