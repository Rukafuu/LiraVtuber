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


def sanitize_for_discord(text: str | None) -> str:
    if is_api_error_response(text):
        return (
            "💜 Limite da API (429) — espera ~30s e manda de novo. "
            "O Discord agora usa Gemini; se persistir, confere `GEMINI_API_KEY` no `.env`."
        )
    if is_bad_llm_response(text):
        return FALLBACK_MESSAGE
    return (text or "").strip()