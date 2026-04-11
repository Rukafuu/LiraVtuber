"""
Utilitarios de texto e console compartilhados pela Hana.
"""

from __future__ import annotations

import re
import shutil
import sys
import textwrap
import time

from src.utils.hana_tags import SILENT_XML_TAGS


def repair_mojibake_text(text: str) -> str:
    if not text:
        return ""

    repaired = str(text)
    replacements = {
        "Ã¡": "á",
        "Ã¢": "â",
        "Ã£": "ã",
        "Ãª": "ê",
        "Ã©": "é",
        "Ã­": "í",
        "Ã³": "ó",
        "Ãµ": "õ",
        "Ãº": "ú",
        "Ã§": "ç",
        "Ã": "Á",
        "Ã‰": "É",
        "Ã“": "Ó",
        "Ãš": "Ú",
        "Ã‡": "Ç",
        "â€¢": "•",
        "â€”": "—",
        "â€“": "–",
        "âœ“": "✓",
        "âœ¨": "✨",
        "âš¡": "⚡",
        "âš™": "⚙️",
        "â—": "●",
        "ðŸ§ ": "🧠",
        "ðŸ—£": "🗣",
        "ðŸ—£ï¸": "🗣️",
        "ðŸŽ­": "🎭",
        "ðŸ‘": "👁",
        "ðŸ‘ï¸": "👁️",
        "ðŸŽ™ï¸": "🎙️",
        "ðŸ‘‚": "👂",
        "ðŸ‘¤": "👤",
        "ðŸ”Š": "🔊",
        "ðŸ”§": "🔧",
        "ðŸŽ¨": "🎨",
        "ðŸŽ¬": "🎬",
        "ðŸŽµ": "🎵",
        "Ã€": "À",
        "Ã¹": "ù",
        "Ã´": "ô",
        "Ã‡Ã£": "ção",
    }
    for bad, good in replacements.items():
        repaired = repaired.replace(bad, good)
    return repaired


def limpar_texto_tts(texto: str) -> str:
    """Remove canais silenciosos e ruido visual antes do envio ao TTS."""
    if not texto:
        return ""

    texto_limpo = repair_mojibake_text(texto)
    texto_limpo = re.sub(r"<think>.*?</think>", "", texto_limpo, flags=re.DOTALL | re.IGNORECASE)
    texto_limpo = re.sub(r"<pensamento>.*?</pensamento>", "", texto_limpo, flags=re.DOTALL | re.IGNORECASE)
    texto_limpo = re.sub(r"<thought>.*?</thought>", "", texto_limpo, flags=re.DOTALL | re.IGNORECASE)
    for tag_name in SILENT_XML_TAGS:
        texto_limpo = re.sub(rf"<{tag_name}>.*?</{tag_name}>", "", texto_limpo, flags=re.DOTALL | re.IGNORECASE)

    texto_limpo = re.sub(r"<tool_code>.*?</tool_code>", "", texto_limpo, flags=re.DOTALL | re.IGNORECASE)
    texto_limpo = re.sub(r"```.*?```", "", texto_limpo, flags=re.DOTALL)
    texto_limpo = re.sub(r"\[INDEX_\d+\.\d+(?:,\s*INDEX_\d+\.\d+)*\]", "", texto_limpo)
    texto_limpo = re.sub(r"ã€.*?ã€‘", "", texto_limpo, flags=re.DOTALL)
    texto_limpo = re.sub(r"ã€Š.*?ã€‹", "", texto_limpo, flags=re.DOTALL)

    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E6-\U0001F1FF"
        "\U0001F900-\U0001F9FF"
        "\u2600-\u26FF"
        "\u2700-\u27BF"
        "\U00020000-\U0003FFFF"
        "]+",
        flags=re.UNICODE,
    )
    texto_limpo = emoji_pattern.sub("", texto_limpo)
    texto_limpo = re.sub(r"\[SISTEMA[^\]]*\]", "", texto_limpo)
    texto_limpo = re.sub(r"\[([^\]]+)\]:", "", texto_limpo)
    texto_limpo = re.sub(r"<[^>]*>", "", texto_limpo)
    texto_limpo = re.sub(r"[*`~^_#{}\[\]()]", "", texto_limpo)
    texto_limpo = re.sub(r"\s+", " ", texto_limpo).strip()
    texto_limpo = texto_limpo.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return texto_limpo


class ConsoleUI:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    C_SYS = "\033[96m"
    C_STT = "\033[96m"
    C_HANA = "\033[95m"
    C_TTS = "\033[95m"
    C_MEM = "\033[94m"
    C_VIS = "\033[92m"
    C_USER = "\033[93m"
    C_TEMP = "\033[96m"
    C_MOTOR = "\033[95m"
    C_ERR = "\033[41;97m"
    C_INFO = "\033[90m"
    C_RST = "\033[0m"
    _ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

    def __init__(self, prefix="[HANA]"):
        self.prefix = prefix
        self.turno_atual = 1
        self.tempo_inicio_turno = 0.0
        self._ultimo_turno_pensado = 0

    def novo_turno(self):
        self.turno_atual += 1
        self.tempo_inicio_turno = time.time()

    def get_tempo_decorrido(self) -> str:
        if self.tempo_inicio_turno == 0:
            return "0s"
        return f"{int(time.time() - self.tempo_inicio_turno)}s"

    def _obter_hora(self) -> str:
        return time.strftime("[%H:%M:%S]")

    def _terminal_width(self) -> int:
        try:
            return max(88, shutil.get_terminal_size((120, 40)).columns)
        except Exception:
            return 120

    def _strip_ansi(self, value: str) -> str:
        return self._ANSI_RE.sub("", value)

    def _write_line(self, line: str):
        sys.stdout.write(f"\r\033[K{repair_mojibake_text(line)}{self.C_RST}\n")
        sys.stdout.flush()

    def _wrap_text(self, text: str, width: int, subsequent_indent: str = "") -> list[str]:
        wrapped = []
        for paragraph in repair_mojibake_text(str(text)).splitlines() or [""]:
            if not paragraph.strip():
                wrapped.append("")
                continue
            wrapped.extend(
                textwrap.wrap(
                    paragraph,
                    width=width,
                    replace_whitespace=False,
                    drop_whitespace=False,
                    subsequent_indent=subsequent_indent,
                    break_long_words=False,
                    break_on_hyphens=False,
                )
                or [paragraph]
            )
        return wrapped

    def print_linha(self, estado: str, cor: str, modulo_dir: str, icone_esq: str, icone_dir: str):
        prefix = f"{self.C_HANA}{self.prefix}{self.C_RST} {self.C_INFO}{self._obter_hora()}{self.C_RST}"
        rail = f"{icone_esq} {cor}{self.BOLD}{repair_mojibake_text(estado)}{self.C_RST} | Turno: {self.turno_atual} | {self.get_tempo_decorrido()} | {icone_dir} {cor}{repair_mojibake_text(modulo_dir)}{self.C_RST}"
        full = f"{prefix} {rail}"
        width = self._terminal_width()
        if len(self._strip_ansi(full)) <= width:
            self._write_line(full)
            return

        left = f"{prefix} {icone_esq} {cor}{self.BOLD}{repair_mojibake_text(estado)}{self.C_RST}"
        right = f"Turno: {self.turno_atual} | {self.get_tempo_decorrido()} | {icone_dir} {cor}{repair_mojibake_text(modulo_dir)}{self.C_RST}"
        self._write_line(left)
        indent = " " * len(self._strip_ansi(prefix)) + " "
        for line in self._wrap_text(right, max(20, width - len(indent))):
            self._write_line(f"{indent}{line}")

    def print_ouvindo(self):
        self.print_linha("OUVINDO", self.C_SYS, "HUMANO", "👂", "👤")

    def print_pensando(self, provedor: str = "LLM_PROVIDER"):
        if self._ultimo_turno_pensado == self.turno_atual:
            return
        self._ultimo_turno_pensado = self.turno_atual
        self.print_linha("PENSANDO", self.C_MOTOR, provedor.upper(), "🧠", "🎭")

        import json
        import os

        try:
            with open(os.path.join("src", "config", "config.json"), "r", encoding="utf-8-sig") as file:
                cfg = json.load(file)
            llm_provider_key = cfg.get("LLM_PROVIDER", provedor.lower())
            provider_cfg = cfg.get("LLM_PROVIDERS", {}).get(llm_provider_key, {})
            modelo_chat = str(provider_cfg.get("modelo_chat", provider_cfg.get("modelo", "N/D")))
            self.print_linha("MODELO", self.C_MOTOR, modelo_chat, "⚙️", "📘")
            if cfg.get("VISAO_ATIVA", False):
                modelo_visao = str(provider_cfg.get("modelo_vision", modelo_chat))
                self.print_linha("VISAO: ON", self.C_VIS, modelo_visao, "👁️", "🏭")
            else:
                self.print_linha("VISAO: OFF", self.C_SYS, "Desativado", "👁️", "🏭")
        except Exception:
            pass

    def print_falando(self, tts_provider: str = "TTS"):
        self.print_linha("FALANDO", self.C_HANA, tts_provider.upper(), "🗣️", "🔊")

    def print_executando(self, tool_name: str):
        self.print_linha("EXECUTANDO", self.C_VIS, tool_name.upper(), "⚙️", "🔧")

    def print_erro(self, msg: str):
        prefix = f"{self.C_ERR}{self.prefix}{self.C_RST} {self.C_INFO}{self._obter_hora()}{self.C_RST} {self.C_ERR}{self.BOLD}ERRO{self.C_RST}: "
        indent = " " * len(self._strip_ansi(prefix))
        width = max(20, self._terminal_width() - len(self._strip_ansi(prefix)))
        for idx, line in enumerate(self._wrap_text(msg, width, subsequent_indent=indent)):
            if idx == 0:
                self._write_line(f"{prefix}{line}")
            else:
                self._write_line(f"{indent}{line}")

    def print_info_livre(self, msg: str):
        formatted = repair_mojibake_text(str(msg))
        if formatted.startswith("Você:") or formatted.startswith("Voce:"):
            formatted = f"{self.C_USER}{formatted}{self.C_RST}"
        formatted = formatted.replace("[STT]", f"{self.C_STT}[STT]{self.C_RST}")
        formatted = formatted.replace("[TTS]", f"{self.C_TTS}[TTS]{self.C_RST}")
        formatted = formatted.replace("[TEMPERAMENTO]", f"{self.C_TEMP}[TEMPERAMENTO]{self.C_RST}")

        prefix = f"{self.C_INFO}{self.prefix} {self._obter_hora()} ℹ {self.C_RST}"
        indent = " " * len(self._strip_ansi(prefix))
        width = max(20, self._terminal_width() - len(self._strip_ansi(prefix)))
        for idx, line in enumerate(self._wrap_text(formatted, width, subsequent_indent=indent)):
            if idx == 0:
                self._write_line(f"{prefix}{line}")
            else:
                self._write_line(f"{indent}{line}")

    def print_hana_text(self, text: str, first_chunk: bool = False):
        prefix = f"{self.C_HANA}[HANA]{self.C_RST}: " if first_chunk else " " * 8
        width = max(20, self._terminal_width() - len(self._strip_ansi(prefix)))
        wrapped = self._wrap_text(text, width)
        for idx, line in enumerate(wrapped):
            line_prefix = prefix if idx == 0 else " " * len(self._strip_ansi(prefix))
            self._write_line(f"{line_prefix}{line}")

    def set_banner(self, stt_info: str, tts_info: str, provider_info: str = "", model_info: str = ""):
        border = f"{self.BOLD}{self.C_HANA}{'=' * 63}{self.C_RST}"
        print("\n" + border)
        print(f" {self.C_SYS}✨ HANA ONLINE E PRONTA PARA OUVIR ✨{self.C_RST}")
        print(f" {self.C_INFO}STT: {self.BOLD}{repair_mojibake_text(stt_info)}{self.C_RST}{self.C_INFO} | TTS: {self.BOLD}{repair_mojibake_text(tts_info)}{self.C_RST}")
        if provider_info:
            print(
                f" {self.C_INFO}PROVEDOR: {self.BOLD}{repair_mojibake_text(provider_info)}{self.C_RST}"
                f"{self.C_INFO} | LLM: {self.BOLD}{repair_mojibake_text(model_info)}{self.C_RST}"
            )
        print(f" {self.C_INFO}Pressione e segure a tecla configurada para falar.{self.C_RST}")
        print(f" {self.C_INFO}Diga ou digite 'Desligar sistema' para encerrar.{self.C_RST}")
        print(border + "\n")


ui = ConsoleUI()
