"""
Entrypoint: python apps/control_api/main.py

Control Center API (chat, mídia, WebSocket). Porta 8042 por padrão.
WhatsApp: apps/whatsapp_api/main.py (8043).
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env", encoding="utf-8-sig")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

from apps.control_api.server import start_server  # noqa: E402


def main():
    host = os.getenv("CONTROL_API_HOST", "0.0.0.0")
    port = int(os.getenv("CONTROL_API_PORT", "8042"))
    print(
        f"[Control API] Subindo em http://{host}:{port} "
        "(modo leve por padrao; Chroma em background se CONTROL_API_RAG_CHROMA=1)",
        flush=True,
    )
    start_server(host=host, port=port)


if __name__ == "__main__":
    main()