"""
Emotion Engine — Motor de emoções da Hana.

Parseia tags [EMOTION:X] do texto da LLM, mantém estado de humor,
e emite callbacks para o VTube Studio e GUI.
"""

import logging
import time
from dataclasses import dataclass
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class EmotionEvent:
    """Evento de emoção emitido pelo motor."""
    emotion: str
    timestamp: float
    turno: int = 0


class EmotionEngine:
    """Motor de emoções da Hana. Thread-safe e observável."""

    # Emoções válidas e seus valores de humor (-1.0 a 1.0)
    EMOTION_MOOD_MAP = {
        "HAPPY":     0.8,
        "NEUTRAL":   0.0,
        "SAD":      -0.6,
        "ANGRY":    -0.8,
        "SHY":       0.3,
        "SURPRISED": 0.5,
        "SMUG":      0.6,
        "LOVE":      1.0,
        "SCARED":   -0.4,
        "CONFUSED":  -0.1,
    }

    def __init__(self):
        self.mood: float = 0.0  # -1.0 (muito triste) a 1.0 (muito feliz)
        self.current_emotion: str = "NEUTRAL"
        self.last_thought: str = ""
        self.history: List[EmotionEvent] = []
        self._turno: int = 0

        # Callbacks
        self._on_emotion_callbacks: List[Callable[[str], None]] = []
        self._on_thought_callbacks: List[Callable[[str], None]] = []

        logger.info("[EMOTION ENGINE] Motor de emoções inicializado.")

    def registrar_callback_emocao(self, callback: Callable[[str], None]):
        """Registra callback chamado quando uma emoção é detectada."""
        self._on_emotion_callbacks.append(callback)

    def registrar_callback_pensamento(self, callback: Callable[[str], None]):
        """Registra callback chamado quando um pensamento é detectado."""
        self._on_thought_callbacks.append(callback)

    def novo_turno(self):
        """Incrementa o turno (chamado pelo main.py)."""
        self._turno += 1

    def processar_emocao(self, emotion_name: str):
        """
        Processa uma emoção detectada no texto da LLM.
        Atualiza o humor e dispara callbacks.
        """
        emotion_upper = emotion_name.upper().strip()

        if emotion_upper not in self.EMOTION_MOOD_MAP:
            logger.warning(f"[EMOTION ENGINE] Emoção desconhecida: {emotion_upper}. Usando NEUTRAL.")
            emotion_upper = "NEUTRAL"

        self.current_emotion = emotion_upper

        # Atualiza humor com média ponderada (decaimento suave)
        target_mood = self.EMOTION_MOOD_MAP[emotion_upper]
        self.mood = self.mood * 0.3 + target_mood * 0.7

        # Registra no histórico
        event = EmotionEvent(
            emotion=emotion_upper,
            timestamp=time.time(),
            turno=self._turno
        )
        self.history.append(event)

        # Manter apenas últimos 50 eventos
        if len(self.history) > 50:
            self.history = self.history[-50:]

        logger.info(f"[EMOTION ENGINE] Emoção: {emotion_upper} | Humor: {self.mood:.2f}")

        # Dispara callbacks
        for cb in self._on_emotion_callbacks:
            try:
                cb(emotion_upper)
            except Exception as e:
                logger.error(f"[EMOTION ENGINE] Erro no callback de emoção: {e}")

    def processar_pensamento(self, thought: str):
        """Armazena o último pensamento e dispara callbacks."""
        self.last_thought = thought
        logger.debug(f"[EMOTION ENGINE] Pensamento: {thought[:60]}...")

        for cb in self._on_thought_callbacks:
            try:
                cb(thought)
            except Exception as e:
                logger.error(f"[EMOTION ENGINE] Erro no callback de pensamento: {e}")

    def get_mood_emoji(self) -> str:
        """Retorna um emoji representando o humor atual."""
        if self.mood > 0.6:
            return "😄"
        elif self.mood > 0.2:
            return "😊"
        elif self.mood > -0.2:
            return "😐"
        elif self.mood > -0.6:
            return "😔"
        else:
            return "😡"

    def get_mood_label(self) -> str:
        """Retorna uma label humana para o humor atual."""
        if self.mood > 0.6:
            return "Muito Feliz"
        elif self.mood > 0.2:
            return "Feliz"
        elif self.mood > -0.2:
            return "Neutra"
        elif self.mood > -0.6:
            return "Triste"
        else:
            return "Irritada"
