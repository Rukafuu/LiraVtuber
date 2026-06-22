"""Sanitização de respostas LLM para Discord."""
from __future__ import annotations

import re

# Respostas de filtro de segurança (OpenRouter free / modelos baratos)
_SAFETY_RE = re.compile(
    r"^(?:user\s+safety|content\s+policy|safety\s*[:;]|i\s+can(?:not|'t)\s+(?:help|assist|answer))",
    re.IGNORECASE,
)
_GARBAGE_ONLY_RE = re.compile(r"^[\s:;,.-]*(safe|unsafe|blocked|refused)[\s:;,.-]*$", re.IGNORECASE)

FALLBACK_MODEL = "openrouter/free"
FALLBACK_MESSAGE = (
    "💜 O modelo gratuito travou no filtro de segurança de novo. "
    "Repete a mensagem ou usa `/chat` — eu respondo de verdade."
)


def is_api_error_response(text: str | None) -> bool:
    t = (text or "").strip()
    return t.startswith("(ERRO API:") or "Error code: 429" in t or "rate-limited" in t.lower()


def is_bad_llm_response(text: str | None) -> bool:
    t = (text or "").strip()
    if is_api_error_response(t):
        return True
    if not t:
        return True
    if len(t) < 4:
        return True
    if _SAFETY_RE.search(t):
        return True
    if _GARBAGE_ONLY_RE.match(t):
        return True
    if re.fullmatch(r"user\s+safety\s*[:;]?\s*safe\.?", t, re.IGNORECASE):
        return True
    return False


_VTS_EMOTION_RE = re.compile(r"\[EMOTION:[^\]]*\]?", re.IGNORECASE)
_VTS_PARAM_RE = re.compile(r"\[PARAM:[^\]]*\]?", re.IGNORECASE)
_VTS_TRAILING_TAG_RE = re.compile(r"\[[A-Z_]+:[^\]]*$")
# Hiragana, katakana, kanji, pontuação CJK — o Gemini às vezes "enfeita" com 進歩 etc.
_CJK_RUN_RE = re.compile(
    r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\u3000-\u303f\uff00-\uffef]+"
)
_CJK_CHAR_RE = re.compile(
    r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]"
)


def strip_stray_cjk(text: str | None, *, cjk_ratio_keep: float = 0.35) -> str:
    """
    Remove kanji/hiragana/katakana soltos em respostas PT-BR.
    Mantém texto se a resposta for majoritariamente CJK (ex.: tradução pedida).
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return ""

    letters = re.findall(r"\w", cleaned, flags=re.UNICODE)
    cjk_count = len(_CJK_CHAR_RE.findall(cleaned))
    if letters and (cjk_count / len(letters)) >= cjk_ratio_keep:
        return cleaned

    cleaned = _CJK_RUN_RE.sub("", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r" +\n", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def strip_vtube_studio_tags(text: str | None) -> str:
    """Remove tags [PARAM]/[EMOTION] do VTube Studio — só fazem sentido no terminal com avatar."""
    cleaned = (text or "").strip()
    if not cleaned:
        return ""
    cleaned = _VTS_EMOTION_RE.sub("", cleaned)
    cleaned = _VTS_PARAM_RE.sub("", cleaned)
    cleaned = _VTS_TRAILING_TAG_RE.sub("", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def sanitize_for_discord(text: str | None) -> str:
    if is_api_error_response(text):
        return (
            "💜 Limite da API (429) — espera ~30s e manda de novo. "
            "O Discord agora usa Gemini; se persistir, confere `GEMINI_API_KEY` no `.env`."
        )
    text = strip_stray_cjk(strip_vtube_studio_tags(text))
    if is_bad_llm_response(text):
        return FALLBACK_MESSAGE
    return text


_VTUBE_EXTRA_TAG_RE = re.compile(
    r"\[(?:POSE|EXPRESSION|LOOK|ACTION|VTUBE|EXPRESSAO|EXPRESSÃO)[^\]]*\]?",
    re.IGNORECASE,
)
_VTUBE_NARRATION_LINE_RE = re.compile(
    r"^\*[^*]*(?:olhando|express|pose|sorri|revira|cruza|inclina|superior|deboche|desd[eê]n)[^*]*\*$",
    re.IGNORECASE,
)
_VTUBE_INLINE_NARRATION_RE = re.compile(
    r"^\*[^*]*(?:olhando|express|pose|sorri|revira|cruza|inclina|superior|deboche|desd[eê]n)[^*]*\*\s*",
    re.IGNORECASE,
)
_VTUBE_OPENING_NARRATION_RE = re.compile(
    r"^(?:Olhando|Expressando|Sorrindo|Revirando os olhos|Cruza os braços|Inclina a cabeça)"
    r"[^.!?\n]*?(?:superior|deboche|desd[eê]n|sarcástic[ao])[^.!?\n]*[.!?]\s+",
    re.IGNORECASE,
)


def _strip_whatsapp_roleplay_line(line: str) -> str:
    stripped = line.strip()
    if not stripped:
        return ""
    if _VTUBE_NARRATION_LINE_RE.match(stripped):
        return ""
    while True:
        m = _VTUBE_INLINE_NARRATION_RE.match(stripped)
        if not m:
            break
        stripped = stripped[m.end() :].strip()
    stripped = _VTUBE_OPENING_NARRATION_RE.sub("", stripped, count=1)
    return stripped.strip()


def sanitize_for_whatsapp(text: str | None) -> str:
    """Remove tags VTube, poses e narração corporal — WhatsApp é só texto."""
    from src.utils.text import sanitize_visible_response_text

    cleaned = sanitize_visible_response_text(text)
    cleaned = strip_stray_cjk(strip_vtube_studio_tags(cleaned))
    cleaned = _VTUBE_EXTRA_TAG_RE.sub("", cleaned)
    cleaned = re.sub(r"\[[^\]]+\]", "", cleaned)

    kept_lines: list[str] = []
    for line in cleaned.splitlines():
        processed = _strip_whatsapp_roleplay_line(line)
        if not processed and line.strip():
            continue
        kept_lines.append(processed)
    cleaned = "\n".join(kept_lines)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()