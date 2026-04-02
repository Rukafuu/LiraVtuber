import json
import logging
import os
import re
import tempfile
import wave

import keyboard
import pyaudio
from groq import Groq

from src.config.config_loader import CONFIG
from src.core.runtime_capabilities import get_ptt_settings
from src.utils.text import ui

logger = logging.getLogger(__name__)

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


class MotorSTTWhisper:
    def __init__(self):
        api_key = os.environ.get("GROQ_API_KEY") or CONFIG.get("GROQ_API_KEY")
        self.cliente = Groq(api_key=api_key)
        self.modelo_stt = CONFIG.get("STT_MODEL", "whisper-large-v3")
        self.idioma = CONFIG.get("STT_LANGUAGE", "pt")

        self.indice_mic = CONFIG.get("MIC_DEVICE_INDEX", None)
        self.formato = pyaudio.paInt16
        self.taxa_amostragem = CONFIG.get("TAXA_AMOSTRAGEM", 44100)
        self.canais = 1
        self.chunk = 1024
        self.audio = pyaudio.PyAudio()

        self.limiar_volume = 800
        self.limite_silencio = 1.6

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
                json.dump({"hannah": "Hana"}, f, indent=4, ensure_ascii=False)

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

    def gravar_audio(self) -> str:
        if self.modo_ptt:
            return self._gravar_ptt()
        return self._gravar_buffer()

    def _gravar_ptt(self) -> str:
        try:
            stream = self.audio.open(
                format=self.formato,
                channels=self.canais,
                rate=self.taxa_amostragem,
                input=True,
                input_device_index=self.indice_mic,
                frames_per_buffer=self.chunk,
            )
        except Exception as e:
            logger.error(f"[STT] Falha ao abrir stream de audio no modo PTT: {e}")
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
            stream.stop_stream()
            stream.close()
            return None

        stream.stop_stream()
        stream.close()

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
                format=self.formato,
                channels=self.canais,
                rate=self.taxa_amostragem,
                input=True,
                input_device_index=self.indice_mic,
                frames_per_buffer=self.chunk,
            )
        except Exception as e:
            logger.error(f"[STT] Falha ao abrir stream de audio no modo buffer: {e}")
            return None

        ui.print_ouvindo()

        frames = []
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
                elif gravando:
                    silencio_frames += 1
                    frames.append(data)
                    if silencio_frames > max_silencio_frames:
                        break
            except KeyboardInterrupt:
                stream.stop_stream()
                stream.close()
                return None

        stream.stop_stream()
        stream.close()

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

    def transcrever(self) -> str:
        caminho_wav = self.gravar_audio()
        if not caminho_wav:
            return ""

        ui.print_linha("PROCESSANDO", ui.C_STT, "WHISPER", "⚙️", "🎙️")

        texto_transcrito = ""
        try:
            with open(caminho_wav, "rb") as arquivo_audio:
                transcricao = self.cliente.audio.transcriptions.create(
                    file=(os.path.basename(caminho_wav), arquivo_audio),
                    model=self.modelo_stt,
                    language=self.idioma,
                    response_format="text",
                    prompt="",
                )
                texto_transcrito = transcricao.strip()
                texto_limpo = texto_transcrito.lower().strip()

                frases_fantasmas = [
                    "",
                    "obrigado.",
                    "obrigada.",
                    "obrigado",
                    "obrigada",
                    "tchau.",
                    "tchau",
                    "tchau tchau",
                    "tchau, tchau.",
                    "legendas pela comunidade amara.org",
                    "mistura de idiomas.",
                    "mistura de idiomas",
                    "o usuário fala português e japonês.",
                    "português e japonês.",
                    "inscreva-se no canal",
                    "deixe seu like",
                    "legenda adriana zanotto",
                    "e aí.",
                    "e aí",
                    "e ai.",
                    "e ai",
                    "legenda por sônia ruberti",
                    "legendas por sônia ruberti",
                    "sônia ruberti",
                ]

                if texto_limpo in frases_fantasmas:
                    return ""

                palavras_curtas_validas = ["oi", "oi.", "ok", "ok.", "aí", "aí.", "lá", "lá."]
                if len(texto_limpo) < 3 and texto_limpo not in palavras_curtas_validas:
                    return ""

                texto_transcrito = self._corrigir_texto(texto_transcrito)
        except Exception as erro:
            logger.error(f"[STT] Erro durante transcricao Whisper: {erro}")
        finally:
            if os.path.exists(caminho_wav):
                os.remove(caminho_wav)

        return texto_transcrito
