"""
SentenceDivider - fatia o stream em frases visíveis sem deixar vazar XML silencioso.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Generator, List

END_PUNCTUATION = {".", "!", "?", "…", "。", "！", "？"}
COMMAS = {",", ";", "，", "、"}
THOUGHT_TAGS = ("pensamento", "thought", "think")
SILENT_XML_TAGS = (
    "salvar_memoria",
    "gerar_imagem",
    "editar_imagem",
    "analisar_youtube",
    "usar_inbox",
    "analisar_inbox",
    "bypass",
    "resumo_imagem",
    "ferramenta_web",
)


@dataclass
class SentenceChunk:
    text: str = ""
    thought: str = ""
    emotions: List[str] = field(default_factory=list)
    params: List[str] = field(default_factory=list)
    is_thought: bool = False
    raw: str = ""


class SentenceDivider:
    def __init__(self, faster_first_response: bool = True):
        self.faster_first_response = faster_first_response
        self.reset()

    def reset(self):
        self._buffer = ""
        self._raw_response_parts: list[str] = []
        self._visible_buffer = ""
        self._visible_raw_buffer = ""
        self._is_first_sentence = True
        self._tag_buffer = ""
        self._mode = "visible"
        self._hidden_tag_name = ""
        self._hidden_buffer = ""

    def process_stream(self, token_generator: Generator[str, None, None]) -> Generator[SentenceChunk, None, None]:
        self.reset()

        for token in token_generator:
            if not token:
                continue
            self._raw_response_parts.append(token)
            self._buffer += token
            for chunk in self._process_buffer():
                yield chunk

        for chunk in self._flush():
            yield chunk

    def _process_buffer(self) -> Generator[SentenceChunk, None, None]:
        while self._buffer:
            char = self._buffer[0]
            self._buffer = self._buffer[1:]

            if self._mode == "tag":
                self._tag_buffer += char
                if char == ">":
                    yield from self._consume_completed_tag()
                continue

            if self._mode in {"thought", "silent"}:
                self._hidden_buffer += char
                close_tag = f"</{self._hidden_tag_name}>"
                if self._hidden_buffer.lower().endswith(close_tag):
                    content = self._hidden_buffer[: -len(close_tag)]
                    if self._mode == "thought" and content.strip():
                        yield self._make_thought_chunk(content.strip())
                    self._hidden_buffer = ""
                    self._hidden_tag_name = ""
                    self._mode = "visible"
                continue

            if char == "<":
                self._mode = "tag"
                self._tag_buffer = "<"
                continue

            self._append_visible_char(char)
            chunk = self._extract_next_sentence()
            if chunk:
                yield chunk

    def _consume_completed_tag(self) -> Generator[SentenceChunk, None, None]:
        raw_tag = self._tag_buffer
        self._tag_buffer = ""
        self._mode = "visible"

        normalized = raw_tag.strip().lower()
        tag_name = normalized.strip("<>/ ").split()[0] if normalized.startswith("<") else ""
        is_closing = normalized.startswith("</")

        if tag_name in THOUGHT_TAGS and not is_closing:
            self._mode = "thought"
            self._hidden_tag_name = tag_name
            self._hidden_buffer = ""
            return

        if tag_name in SILENT_XML_TAGS and not is_closing:
            self._mode = "silent"
            self._hidden_tag_name = tag_name
            self._hidden_buffer = ""
            return

        self._append_visible_text(raw_tag)
        chunk = self._extract_next_sentence()
        if chunk:
            yield chunk

    def _append_visible_char(self, char: str):
        self._visible_buffer += char
        self._visible_raw_buffer += char

    def _append_visible_text(self, text: str):
        self._visible_buffer += text
        self._visible_raw_buffer += text

    def _extract_next_sentence(self) -> SentenceChunk | None:
        text = self._visible_buffer
        if not text.strip():
            return None

        if self._is_first_sentence and self.faster_first_response:
            for comma in COMMAS:
                idx = text.find(comma)
                if idx > 3:
                    return self._pop_sentence(idx + 1)

        for idx, char in enumerate(text):
            if char in END_PUNCTUATION:
                return self._pop_sentence(idx + 1)
        return None

    def _pop_sentence(self, cut_index: int) -> SentenceChunk | None:
        visible = self._visible_buffer[:cut_index]
        raw = self._visible_raw_buffer[:cut_index]
        self._visible_buffer = self._visible_buffer[cut_index:]
        self._visible_raw_buffer = self._visible_raw_buffer[cut_index:]
        self._is_first_sentence = False
        return self._make_chunk(raw, visible)

    def _make_thought_chunk(self, thought_text: str) -> SentenceChunk:
        return SentenceChunk(
            thought=thought_text,
            is_thought=True,
            raw=f"<thought>{thought_text}</thought>",
        )

    def _make_chunk(self, raw_text: str, visible_text: str | None = None) -> SentenceChunk:
        text_base = visible_text if visible_text is not None else raw_text
        emotions = re.findall(r"\[EMOTION:(\w+)\]", text_base, re.IGNORECASE)
        params = re.findall(r"\[PARAM:([\w=.-]+)\]", text_base, re.IGNORECASE)

        clean_text = re.sub(r"\[EMOTION:\w+\]", "", text_base, flags=re.IGNORECASE).strip()
        clean_text = re.sub(r"\[PARAM:[\w=.-]+\]", "", clean_text, flags=re.IGNORECASE).strip()
        clean_text = re.sub(r"\[INDEX_\d+\.\d+(?:,\s*INDEX_\d+\.\d+)*\]", "", clean_text).strip()

        return SentenceChunk(
            text=clean_text,
            emotions=emotions,
            params=params,
            raw=raw_text,
        )

    def _flush(self) -> Generator[SentenceChunk, None, None]:
        if self._mode == "tag" and self._tag_buffer:
            self._append_visible_text(self._tag_buffer)
            self._tag_buffer = ""
            self._mode = "visible"

        if self._mode == "thought" and self._hidden_buffer.strip():
            yield self._make_thought_chunk(self._hidden_buffer.strip())
            self._hidden_buffer = ""
            self._hidden_tag_name = ""
            self._mode = "visible"

        if self._mode == "silent":
            self._hidden_buffer = ""
            self._hidden_tag_name = ""
            self._mode = "visible"

        tail = self._visible_buffer.strip()
        raw_tail = self._visible_raw_buffer.strip()
        if tail and raw_tail:
            yield self._make_chunk(raw_tail, tail)
        self._visible_buffer = ""
        self._visible_raw_buffer = ""

    @property
    def complete_response(self) -> str:
        return "".join(self._raw_response_parts)
