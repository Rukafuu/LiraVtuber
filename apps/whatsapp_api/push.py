"""Envia mensagem de follow-up ao bridge WhatsApp (porta 8044)."""
from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

PUSH_URL = os.getenv("WPP_PUSH_URL", "http://127.0.0.1:8044/send")


def push_text(jid: str, text: str, *, timeout: float = 15.0) -> bool:
    if not jid or not (text or "").strip():
        return False
    payload = json.dumps({"jid": jid, "text": text}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        PUSH_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception as exc:
        logger.warning("[WHATSAPP PUSH] falhou: %s", exc)
        return False