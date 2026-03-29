"""
SentenceDivider — Fatia o stream de tokens da LLM em frases completas.

Inspirado no Open-LLM-VTuber, adaptado para o pipeline síncrono da Hana.
Extrai tags especiais:
  - <thought>...</thought> ou <pensamento>...</pensamento> → Pensamento interno
  - [EMOTION:NOME]          → Emoção para o VTube Studio
  - <salvar_memoria>...</salvar_memoria> → Removido do texto (ação silenciosa)
  - <gerar_imagem>...</gerar_imagem>    → Removido do texto (ação silenciosa)
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Generator, List, Optional

logger = logging.getLogger(__name__)

# Pontuação que indica fim de frase
END_PUNCTUATION = {".", "!", "?", "。", "！", "？", "…"}
COMMAS = {",", "，", ";", "、"}


@dataclass
class SentenceChunk:
    """Representa um pedaço processado do stream."""
    text: str = ""                    # Texto limpo para TTS
    thought: str = ""                 # Pensamento interno (se houver)
    emotions: List[str] = field(default_factory=list)  # Emoções detectadas
    params: List[str] = field(default_factory=list)    # Parâmetros VTS [PARAM:N=V]
    is_thought: bool = False          # True se este chunk é um pensamento
    raw: str = ""                     # Texto original bruto (para memória)


class SentenceDivider:
    """
    Recebe um generator de tokens (strings) e emite SentenceChunks
    assim que detecta uma frase completa.
    """

    def __init__(self, faster_first_response: bool = True):
        self.faster_first_response = faster_first_response
        self._buffer = ""
        self._is_first_sentence = True
        self._inside_thought = False
        self._thought_buffer = ""
        self._full_response = []

    def reset(self):
        """Reseta o estado para um novo turno."""
        self._buffer = ""
        self._is_first_sentence = True
        self._inside_thought = False
        self._thought_buffer = ""
        self._full_response = []

    def process_stream(self, token_generator: Generator[str, None, None]) -> Generator[SentenceChunk, None, None]:
        """
        Processa o stream de tokens e emite SentenceChunks completos.
        
        Args:
            token_generator: Generator que emite tokens (strings) da LLM.
            
        Yields:
            SentenceChunk com texto pronto para TTS ou pensamento interno.
        """
        self.reset()

        for token in token_generator:
            self._buffer += token

            # Processa o buffer continuamente
            for chunk in self._process_buffer():
                yield chunk

        # Flush do que sobrou no buffer
        for chunk in self._flush():
            yield chunk

    def _process_buffer(self) -> Generator[SentenceChunk, None, None]:
        """Processa o buffer atual, emitindo chunks completos."""
        while True:
            # 1. Detectar abertura de <thought> ou <pensamento>
            thought_open = -1
            thought_tag_len = 0
            for tag in ("<thought>", "<pensamento>", "<think>"):
                idx = self._buffer.find(tag)
                if idx != -1 and (thought_open == -1 or idx < thought_open):
                    thought_open = idx
                    thought_tag_len = len(tag)

            if thought_open != -1:
                # Emitir texto ANTES do <thought>/<pensamento> se houver
                text_before = self._buffer[:thought_open]
                if text_before.strip():
                    for chunk in self._extract_sentences(text_before):
                        yield chunk

                self._buffer = self._buffer[thought_open + thought_tag_len:]
                self._inside_thought = True
                self._thought_buffer = ""
                continue

            # 2. Detectar fechamento de </thought> ou </pensamento>
            if self._inside_thought:
                thought_close = -1
                close_tag_len = 0
                for ctag in ("</thought>", "</pensamento>", "</think>"):
                    idx = self._buffer.find(ctag)
                    if idx != -1 and (thought_close == -1 or idx < thought_close):
                        thought_close = idx
                        close_tag_len = len(ctag)

                if thought_close != -1:
                    self._thought_buffer += self._buffer[:thought_close]
                    self._buffer = self._buffer[thought_close + close_tag_len:]
                    self._inside_thought = False

                    # Emitir o pensamento como chunk especial
                    if self._thought_buffer.strip():
                        chunk = SentenceChunk(
                            thought=self._thought_buffer.strip(),
                            is_thought=True,
                            raw=f"<thought>{self._thought_buffer.strip()}</thought>"
                        )
                        self._full_response.append(chunk.raw)
                        yield chunk
                    continue
                else:
                    # Ainda dentro do thought, acumula tudo
                    self._thought_buffer += self._buffer
                    self._buffer = ""
                    return

            # 3. Texto normal — buscar frases completas
            found_any = False
            for chunk in self._extract_sentences(self._buffer):
                found_any = True
                yield chunk

            if not found_any:
                return
            else:
                # Se emitimos algo, o buffer foi atualizado dentro de _extract_sentences
                # mas precisamos checar se há mais
                if not self._buffer.strip():
                    return

    def _extract_sentences(self, text: str) -> Generator[SentenceChunk, None, None]:
        """Extrai frases completas do texto, atualizando self._buffer."""
        # Primeiro, tenta a resposta rápida via vírgula (só na primeira frase)
        if self._is_first_sentence and self.faster_first_response:
            for comma in COMMAS:
                idx = text.find(comma)
                if idx != -1 and idx > 3:  # Pelo menos 4 chars antes da vírgula
                    sentence = text[:idx + 1].strip()
                    remaining = text[idx + 1:].strip()
                    
                    if sentence:
                        chunk = self._make_chunk(sentence)
                        self._buffer = remaining
                        self._is_first_sentence = False
                        yield chunk
                        return

        # Busca por pontuação final
        for i, char in enumerate(text):
            if char in END_PUNCTUATION:
                # Verifica se não é abreviação (ex: "ex." no meio de frase)
                sentence = text[:i + 1].strip()
                remaining = text[i + 1:]
                
                if len(sentence) > 2:  # Evitar emitir só "." ou "!"
                    chunk = self._make_chunk(sentence)
                    self._buffer = remaining
                    self._is_first_sentence = False
                    yield chunk
                    return

        # Nenhuma frase completa encontrada, manter no buffer
        self._buffer = text

    def _make_chunk(self, raw_text: str) -> SentenceChunk:
        """Cria um SentenceChunk extraindo emoções e limpando o texto."""
        # Extrair [EMOTION:NOME]
        emotions = re.findall(r'\[EMOTION:(\w+)\]', raw_text, re.IGNORECASE)
        
        # Extrair [PARAM:Nome=Valor]
        params = re.findall(r'\[PARAM:([\w=.-]+)\]', raw_text, re.IGNORECASE)
        
        # Limpar o texto removendo as tags de emoção e parâmetros
        clean_text = re.sub(r'\[EMOTION:\w+\]', '', raw_text).strip()
        clean_text = re.sub(r'\[PARAM:[\w=.-]+\]', '', clean_text).strip()
        
        # Remover tags XML de ações silenciosas (elas serão processadas no main.py)
        clean_text = re.sub(r'<(pensamento|thought|think)>.*?</\1>', '', clean_text, flags=re.DOTALL | re.IGNORECASE).strip()
        clean_text = re.sub(r'<salvar_memoria>.*?</salvar_memoria>', '', clean_text, flags=re.DOTALL).strip()
        clean_text = re.sub(r'<gerar_imagem>.*?</gerar_imagem>', '', clean_text, flags=re.DOTALL).strip()
        clean_text = re.sub(r'<editar_imagem>.*?</editar_imagem>', '', clean_text, flags=re.DOTALL).strip()
        clean_text = re.sub(r'<analisar_youtube>.*?</analisar_youtube>', '', clean_text, flags=re.DOTALL).strip()
        clean_text = re.sub(r'<bypass>.*?</bypass>', '', clean_text, flags=re.DOTALL).strip()
        clean_text = re.sub(r'<resumo_imagem>.*?</resumo_imagem>', '', clean_text, flags=re.DOTALL).strip()

        # Remover citações do Google Search Grounding [INDEX_X.Y]
        clean_text = re.sub(r'\[INDEX_\d+\.\d+(?:,\s*INDEX_\d+\.\d+)*\]', '', clean_text).strip()
        
        # Remover 【...】 (marcadores fantasma existentes)
        display_raw = raw_text

        self._full_response.append(display_raw)

        return SentenceChunk(
            text=clean_text,
            emotions=emotions,
            params=params,
            raw=display_raw
        )

    def _flush(self) -> Generator[SentenceChunk, None, None]:
        """Emite qualquer texto restante no buffer."""
        if self._inside_thought and self._thought_buffer.strip():
            chunk = SentenceChunk(
                thought=self._thought_buffer.strip(),
                is_thought=True,
                raw=f"<thought>{self._thought_buffer.strip()}</thought>"
            )
            self._full_response.append(chunk.raw)
            yield chunk
            self._thought_buffer = ""
            self._inside_thought = False

        if self._buffer.strip():
            chunk = self._make_chunk(self._buffer.strip())
            yield chunk
            self._buffer = ""

    @property
    def complete_response(self) -> str:
        """Retorna a resposta completa acumulada."""
        return " ".join(self._full_response)
