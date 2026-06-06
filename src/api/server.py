"""
Shim de compatibilidade (Sprint 4).

Implementação: apps/control_api/server.py
Entrypoint: python apps/control_api/main.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.control_api.server import (  # noqa: F401
    AppContext,
    MemoryLogHandler,
    app,
    memory_log_handler,
    start_server,
)

__all__ = [
    "AppContext",
    "MemoryLogHandler",
    "app",
    "memory_log_handler",
    "start_server",
]

if __name__ == "__main__":
    start_server()