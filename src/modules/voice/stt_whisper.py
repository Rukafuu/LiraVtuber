import json
import logging
import os
import re
import tempfile
import wave

import keyboard
import pyaudio

from src.config.config_loader import CONFIG
from src.core.runtime_capabilities import get_ptt_settings
from src.utils.text import ui

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Ghost phrases & noise guard (ported from upstream)
# ---------------------------------------------------------------------------

STT_PROMPT_MAX_WORDS = 160
FRASES_FANTASMAS_STT = {
    "",
    "obrigado.", "obrigada.", "obrigado", "obrigada",
    "tchau.", "tchau", "tchau tchau", "tchau, tchau.",
    "legendas pela comunidade amara.org",
    "mistura de idiomas.", "mistura de idiomas",
    "o usuario fala portugues e japones.", "portugues e japones.",
    "inscreva-se no canal", "deixe seu like",
    "legenda adriana zanotto",
    "e ai.", "e ai",
    "legenda por sonia ruberti", "legendas por sonia ruberti", "sonia ruberti",
    "subtitulos por tiago anderson", "subtitulo por tiago anderson",
    "legendas por tiago anderson", "legenda por tiago anderson",
    "ate a proxima", "ate a proxima!", "ate a proxima.",
}
PADROES_FANTASMAS_STT = (
    re.compile(r"^(?:subtitulos?|legendas?|legenda|caption|captions|subtitle|subtitles)\s+(?:por|by)\s+[\w .'-]{2,60}\.?$", re.IGNORECASE),
    re.compile(r"^(?:transcricao|transcription)\s+(?:por|by)\s+[\w .'-]{2,60}\.?$", re.IGNORECASE),
    re.compile(r"^(?:traduzido|traducao|translation)\s+(?:por|by)\s+[\w .'-]{2,60}\.?$", re.IGNORECASE),
    re.compile(r"^(?:inscreva-se|deixe seu like|ative o sininho)(?:.+)?\.?$", re.IGNORECASE),
    re.compile(r"^.+(?:ative o sininho|notificacoes de novos videos).*$", re.IGNORECASE),
)

try:
    import audioop

    def audio_rms(data, width):
        return audioop.rms(data, width)
except Exception:
    def audio_rms(data, width):
        try:
            from array import array
            import math

            if width == 2:
                arr = array("h")
            elif width == 1:
                arr = array("b")
            else:
                arr = array("h")

            arr.frombytes(data)
            if not arr:
                return 0

            squared_mean = sum(x * x for x in arr) / len(arr)
            return int(math.sqrt(squared_mean))
        except Exception:
            return 0


def _load_whisper_model():
    """Carrega o modelo faster-whisper com fallback CPU/CUDA."""
    from faster_whisper import WhisperModel

    model_size = CONFIG.get("STT_MODEL", "large-v3")
    device = CONFIG.get("STT_DEVICE", "auto")

    if device == "auto":
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            device = "cpu"

    compute_type = "float16" if device == "cuda" else "int8"
    logger.info("[STT] Carregando faster-whisper '%s' em %s (%s)", model_size, device, compute_type)
    return WhisperModel(model_size, device=device, compute_type=compute_type)


_whisper_model = None


def _get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        _whisper_model = _load_whisper_model()
    return _whisper_model


class MotorSTTWhisper:
    def __init__(self):
        self.idioma = CONFIG.get("STT_LANGUAGE", "pt")

        self.indice_mic = CONFIG.get("MIC_DEVICE_INDEX", None)
        self.formato = pyaudio.paInt16
        self.taxa_amostragem = CONFIG.get("TAXA_AMOSTRAGEM", 44100)
        self.canais = 1
        self.chunk = 1024
        self.audio = pyaudio.PyAudio()

        self.limiar_volume = 800
        self.limite_silencio = 1.6

        # Noise guard (upstream)
        self.noise_guard_enabled = bool(CONFIG.get("STT_NOISE_GUARD_ENABLED", True))
        self.min_recording_seconds = float(CONFIG.get("STT_MIN_RECORDING_SECONDS", 0.45))
        self.min_active_seconds = float(CONFIG.get("STT_MIN_ACTIVE_SECONDS", 0.30))
        self.min_sustained_active_seconds = float(CONFIG.get("STT_MIN_SUSTAINED_ACTIVE_SECONDS", 0.12))
        self.min_active_ratio = float(CONFIG.get("STT_MIN_ACTIVE_RATIO", 0.08))

        ptt_cfg = get_ptt_settings()
        self.modo_ptt = bool(ptt_cfg["enabled"])
        self.tecla_ptt = str(ptt_cfg["key"]).lower()

        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        self.caminho_dicionario = os.path.join(base_dir, "config", "dicionário.json")
        self._criar_dicionario_padrao()

    def _criar_dicionario_padrao(self):
        if not os.path.exists(self.caminho_dicionario):
            os.makedirs(os.path.dirname(self.caminho_dicionario), exist_ok=True)
            with open(self.caminho_dicionario, "w", encoding="utf-8") as f:
                json.dump({"hannah": "Lira", "lira": "Lira"}, f, indent=4, ensure_ascii=False)

    def _corrigir_texto(self, texto: str) -> str:
        try:
            with open(self.caminho_dicionario, "r", encoding="utf-8") as f:
                dicionario = json.load(f)
            for errado, certo in dicionario.items():
                padrao = re.compile(rf"\b{re.escape(errado)}\b", re.IGNORECASE | re.UNICODE)
                texto = padrao.sub(certo, texto)
            return texto
        except Exception as e:
            logger.warning(f"[STT] Falha ao aplicar dicionario de correcao: {e}")
            return texto

    # ------------------------------------------------------------------
    # Noise guard (ported from upstream)
    # ------------------------------------------------------------------

    def _audio_passes_noise_guard(self, volumes: list) -> bool:
        if not self.noise_guard_enabled:
            return True
        if not volumes:
            return False

        frame_seconds = self.chunk / float(self.taxa_amostragem)
        total_seconds = len(volumes) * frame_seconds
        active_flags = [v > self.limiar_volume for v in volumes]
        active_frames = sum(1 for a in active_flags if a)
        active_seconds = active_frames * frame_seconds
        active_ratio = active_frames / max(1, len(volumes))

        longest_run = current_run = 0
        for a in active_flags:
            if a:
                current_run += 1
                longest_run = max(longest_run, current_run)
            else:
                current_run = 0
        sustained_seconds = longest_run * frame_seconds

        if total_seconds < self.min_recording_seconds:
            logger.info("[STT] Audio descartado: curto demais (%.2fs).", total_seconds)
            return False
        if active_seconds < self.min_active_seconds and active_ratio < self.min_active_ratio:
            logger.info("[STT] Audio descartado: pouca voz ativa (active=%.2fs ratio=%.2f).", active_seconds, active_ratio)
            return False
        if sustained_seconds < self.min_sustained_active_seconds:
            logger.info("[STT] Audio descartado: sem voz sustentada (%.2fs).", sustained_seconds)
            return False
        return True

    @staticmethod
    def _normalizar_texto_fantasma(texto: str) -> str:
        normalized = str(texto or "").lower().strip()
        replacements = str.maketrans({"á":"a","à":"a","â":"a","ã":"a","é":"e","ê":"e","í":"i","ó":"o","ô":"o","õ":"o","ú":"u","ç":"c"})
        normalized = normalized.translate(replacements)
        return re.sub(r"\s+", " ", normalized).strip()

    @classmethod
    def _eh_frase_fantasma(cls, texto: str) -> bool:
        normalized = cls._normalizar_texto_fantasma(texto)
        if normalized in FRASES_FANTASMAS_STT:
            return True
        return any(p.match(normalized) for p in PADROES_FANTASMAS_STT)

    # ------------------------------------------------------------------
    # Gravação
    # ------------------------------------------------------------------

    def gravar_audio(self) -> str:
        if self.modo_ptt:
            return self._gravar_ptt()
        return self._gravar_buffer()

    def _gravar_ptt(self) -> str:
        try:
            stream = self.audio.open(
                format=self.formato, channels=self.canais, rate=self.taxa_amostragem,
                input=True, input_device_index=self.indice_mic, frames_per_buffer=self.chunk,
            )
        except Exception as e:
            logger.error(f"[STT] Falha ao abrir stream PTT: {e}")
            return None

        ui.print_ouvindo()
        frames = []
        try:
            while True:
                if keyboard.is_pressed(self.tecla_ptt):
                    data = stream.read(self.chunk, exception_on_overflow=False)
                    frames.append(data)
                elif frames:
                    break
        except KeyboardInterrupt:
            stream.stop_stream(); stream.close()
            return None

        stream.stop_stream(); stream.close()
        if not frames:
            return None

        arquivo_temp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        caminho_wav = arquivo_temp.name
        with wave.open(caminho_wav, "wb") as wf:
            wf.setnchannels(self.canais)
            wf.setsampwidth(self.audio.get_sample_size(self.formato))
            wf.setframerate(self.taxa_amostragem)
            wf.writeframes(b"".join(frames))
        return caminho_wav

    def _gravar_buffer(self) -> str:
        try:
            stream = self.audio.open(
                format=self.formato, channels=self.canais, rate=self.taxa_amostragem,
                input=True, input_device_index=self.indice_mic, frames_per_buffer=self.chunk,
            )
        except Exception as e:
            logger.error(f"[STT] Falha ao abrir stream buffer: {e}")
            return None

        ui.print_ouvindo()
        frames = []
        volumes = []
        gravando = False
        silencio_frames = 0
        max_silencio_frames = int((self.taxa_amostragem / self.chunk) * self.limite_silencio)

        while True:
            try:
                data = stream.read(self.chunk, exception_on_overflow=False)
                width = self.audio.get_sample_size(self.formato)
                volume = audio_rms(data, width)

                if volume > self.limiar_volume:
                    gravando = True
                    silencio_frames = 0
                    frames.append(data)
                    volumes.append(volume)
                elif gravando:
                    silencio_frames += 1
                    frames.append(data)
                    volumes.append(volume)
                    if silencio_frames > max_silencio_frames:
                        break
            except KeyboardInterrupt:
                stream.stop_stream(); stream.close()
                return None

        stream.stop_stream(); stream.close()

        if not frames:
            return None
        if not self._audio_passes_noise_guard(volumes):
            return None

        arquivo_temp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        caminho_wav = arquivo_temp.name
        with wave.open(caminho_wav, "wb") as wf:
            wf.setnchannels(self.canais)
            wf.setsampwidth(self.audio.get_sample_size(self.formato))
            wf.setframerate(self.taxa_amostragem)
            wf.writeframes(b"".join(frames))
        return caminho_wav

    # ------------------------------------------------------------------
    # Transcrição (faster-whisper local)
    # ------------------------------------------------------------------

    def transcrever(self) -> str:
        caminho_wav = self.gravar_audio()
        if not caminho_wav:
            return ""

        ui.print_linha("PROCESSANDO", ui.C_STT, "GROQ/WHISPER", "⚙️", "🎙️")

        texto_transcrito = ""
        try:
            groq_key = os.getenv("GROQ_API_KEY")
            if groq_key:
                from openai import OpenAI
                client = OpenAI(api_key=groq_key, base_url="https://api.groq.com/openai/v1")
                with open(caminho_wav, "rb") as audio_file:
                    transcription = client.audio.transcriptions.create(
                        model="whisper-large-v3-turbo", 
                        file=audio_file,
                        language=self.idioma
                    )
                texto_transcrito = transcription.text.strip()
            else:
                model = _get_whisper_model()
                segments, _ = model.transcribe(
                    caminho_wav,
                    language=self.idioma,
                    beam_size=5,
                    vad_filter=True,
                )
                texto_transcrito = " ".join(seg.text.strip() for seg in segments).strip()

            texto_limpo = texto_transcrito.lower().strip()

            if texto_limpo in FRASES_FANTASMAS_STT or self._eh_frase_fantasma(texto_transcrito):
                logger.info("[STT] Frase fantasma descartada: %s", texto_transcrito)
                return ""

            palavras_curtas_validas = ["oi", "oi.", "ok", "ok.", "aí", "aí.", "lá", "lá."]
            if len(texto_limpo) < 3 and texto_limpo not in palavras_curtas_validas:
                return ""

            texto_transcrito = self._corrigir_texto(texto_transcrito)
        except Exception as erro:
            logger.error(f"[STT] Erro durante transcricao Whisper local: {erro}")
        finally:
            if os.path.exists(caminho_wav):
                os.remove(caminho_wav)

        return texto_transcrito
