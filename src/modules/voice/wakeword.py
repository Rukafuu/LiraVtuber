import logging
import os
import re
import time
import numpy as np
import pyaudio
from faster_whisper import WhisperModel
from src.modules.voice.vad_silero import get_vad
from src.config.config_loader import CONFIG

logger = logging.getLogger(__name__)

class WakeWordDetector:
    def __init__(self, keyword="lira", model_size="tiny", device="cpu"):
        self.keyword = keyword.lower()
        self.model_size = model_size
        self.device = device
        self.vad = get_vad()
        
        logger.info(f"[WAKEWORD] Inicializando detector com modelo '{model_size}'...")
        self.model = WhisperModel(model_size, device=device, compute_type="int8")
        
        self.chunk_size = 1024
        self.sample_rate = 16000 # Whisper prefere 16k
        self.audio = pyaudio.PyAudio()
        
        # Buffer de áudio circular (2 segundos)
        self.buffer_duration = 2.0
        self.buffer_limit = int(self.sample_rate * self.buffer_duration)
        self.audio_buffer = np.zeros(self.buffer_limit, dtype=np.float32)

    def listen_continuous(self):
        """
        Fica ouvindo o microfone continuamente. 
        Quando a keyword é detectada, retorna o texto completo (incluindo o comando).
        """
        stream = self.audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.chunk_size
        )
        
        logger.info(f"[WAKEWORD] Ouvindo continuamente por '{self.keyword}'...")
        
        speech_started = False
        speech_frames = []
        silence_threshold = 0.8
        last_speech_time = time.time()
        
        try:
            while True:
                data = stream.read(self.chunk_size, exception_on_overflow=False)
                
                # Check VAD
                if self.vad.is_speech(data, threshold=0.5):
                    speech_started = True
                    last_speech_time = time.time()
                    speech_frames.append(data)
                elif speech_started:
                    speech_frames.append(data)
                    # Se houver silêncio após voz, processamos o bloco
                    if time.time() - last_speech_time > silence_threshold:
                        audio_data = b"".join(speech_frames)
                        text = self._check_keyword(audio_data)
                        if text:
                            logger.info(f"[WAKEWORD] Palavra-chave '{self.keyword}' detectada!")
                            stream.stop_stream()
                            stream.close()
                            return text # Retorna o texto para o main loop
                        
                        # Reset
                        speech_started = False
                        speech_frames = []
        except Exception as e:
            logger.error(f"[WAKEWORD] Erro no loop de escuta: {e}")
        finally:
            if stream.is_active():
                stream.stop_stream()
                stream.close()
        return ""

    def _check_keyword(self, audio_bytes):
        """Converte áudio em texto e verifica a keyword. Retorna o texto se achar."""
        # Converter bytes para float32 array
        audio_int16 = np.frombuffer(audio_bytes, dtype=np.int16)
        audio_float32 = audio_int16.astype(np.float32) / 32768.0
        
        segments, _ = self.model.transcribe(audio_float32, language="pt", beam_size=1)
        text = " ".join([s.text for s in segments]).lower().strip()
        
        if text:
            logger.debug(f"[WAKEWORD] Transcrição parcial: '{text}'")
            # Procura por variações comuns da palavra "Lira"
            patterns = [self.keyword, "lyra", "lira,", "lyra,", "lira!", "lira?"]
            if any(p in text for p in patterns):
                return text
        
        return ""

if __name__ == "__main__":
    # Teste rápido
    logging.basicConfig(level=logging.INFO)
    detector = WakeWordDetector()
    detector.listen_continuous(lambda: print("ACORDOU!"))
