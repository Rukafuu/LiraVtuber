"""
Entrypoint: python apps/whatsapp_api/main.py

API dedicada ao bridge Baileys (porta 8043 por padrao).
Control Center: python apps/control_api/main.py (8042).
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import uvicorn
from dotenv import load_dotenv

load_dotenv(ROOT / ".env", encoding="utf-8-sig")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# ── Corrige crash silencioso no Windows (WinError 10054) ─────────────────────
# O asyncio no Windows levanta ConnectionResetError quando o bridge Node.js
# fecha abruptamente uma conexão HTTP. Sem esse handler, o loop de eventos
# do uvicorn pode travar e matar toda a API silenciosamente.
if sys.platform == "win32":
    _original_exception_handler = None

    def _win_asyncio_exception_handler(loop, context):
        exc = context.get("exception")
        if isinstance(exc, (ConnectionResetError, OSError)) and getattr(exc, "winerror", None) in (10054, 10053, 10058):
            # Conexão abruptamente encerrada pelo host remoto — seguro ignorar no Windows
            logging.debug("[WHATSAPP API] WinError %s suprimido (ConnectionReset do bridge).", getattr(exc, "winerror", "?"))
            return
        # Para qualquer outro erro, chama o handler padrão
        loop.default_exception_handler(context)

    _pending_loop = asyncio.new_event_loop()
    _pending_loop.set_exception_handler(_win_asyncio_exception_handler)
    asyncio.set_event_loop(_pending_loop)

from apps.whatsapp_api.app import app  # noqa: E402


def main():
    host = os.getenv("WHATSAPP_API_HOST", "127.0.0.1")
    port = int(os.getenv("WHATSAPP_API_PORT", "8043"))
    logger = logging.getLogger(__name__)

    # Loop de reinício automático: se o uvicorn morrer por qualquer exceção
    # não tratada, reinicia após 3 segundos (evita ficar sem API).
    MAX_RESTARTS = 10
    restart_count = 0
    while restart_count < MAX_RESTARTS:
        try:
            logger.info("[WHATSAPP API] Iniciando em http://%s:%s (tentativa %d)", host, port, restart_count + 1)
            uvicorn_config = uvicorn.Config(app, host=host, port=port, log_level="info")
            server = uvicorn.Server(uvicorn_config)

            if sys.platform == "win32":
                loop = asyncio.new_event_loop()
                loop.set_exception_handler(_win_asyncio_exception_handler)
                asyncio.set_event_loop(loop)
                loop.run_until_complete(server.serve())
            else:
                server.run()

            # Se chegou aqui sem exceção, o servidor encerrou normalmente
            logger.info("[WHATSAPP API] Servidor encerrou normalmente.")
            break
        except KeyboardInterrupt:
            logger.info("[WHATSAPP API] Encerrado pelo usuário.")
            break
        except Exception as e:
            restart_count += 1
            logger.error("[WHATSAPP API] Erro fatal (tentativa %d/%d): %s — reiniciando em 3s...", restart_count, MAX_RESTARTS, e)
            if restart_count >= MAX_RESTARTS:
                logger.critical("[WHATSAPP API] Número máximo de reinícios atingido. Encerrando.")
                sys.exit(1)
            time.sleep(3)


if __name__ == "__main__":
    main()