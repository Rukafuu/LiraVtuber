"""
Shim de compatibilidade (Sprint 4).

Implementação: apps/vtuber/runtime.py
Entrypoint preferido: python apps/vtuber/main.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.chdir(ROOT)

from dotenv import load_dotenv

load_dotenv(ROOT / ".env", encoding="utf-8-sig")

import apps.vtuber.runtime  # noqa: F401

if __name__ == "__main__":
    pass