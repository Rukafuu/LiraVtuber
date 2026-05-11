"""
Silero VAD — Detecção de Voz Neural.
Substitui o RMS básico por uma rede neural leve que identifica voz humana com precisão.
"""

import os
import torch
import numpy as np
import logging

logger = logging.getLogger(__name__)

class SileroVAD:
    def __init__(self, sampling_rate=16000):
        self.sampling_rate = sampling_rate
        self.model = None
        self._load_model()

    def _load_model(self):
        try:
            # Tenta carregar localmente primeiro ou via torch hub
            model, utils = torch.hub.load(
                repo_or_dir='snickersberg/silero-vad',
                model='silero_vad',
                force_reload=False,
                onnx=True
            )
            self.model = model
            logger.info("[VAD] Silero VAD carregado com sucesso.")
        except Exception as e:
            logger.error(f"[VAD] Erro ao carregar Silero VAD: {e}")
            self.model = None

    def is_speech(self, audio_bytes, threshold=0.5):
        """
        Verifica se um chunk de áudio contém voz.
        audio_bytes: áudio em formato int16 ou float32.
        threshold: confiança mínima (0.0 a 1.0).
        """
        if self.model is None:
            return False

        # Converte bytes int16 para float32 tensor
        audio_int16 = np.frombuffer(audio_bytes, dtype=np.int16)
        audio_float32 = audio_int16.astype(np.float32) / 32768.0
        
        # Garante que seja um tensor de 1 dimensão
        tensor = torch.from_numpy(audio_float32)
        
        try:
            # Obtém probabilidade de voz
            speech_prob = self.model(tensor, self.sampling_rate).item()
            return speech_prob >= threshold
        except Exception as e:
            logger.debug(f"[VAD] Erro na inferência: {e}")
            return False

# Singleton
_vad_instance = None

def get_vad():
    global _vad_instance
    if _vad_instance is None:
        _vad_instance = SileroVAD()
    return _vad_instance
