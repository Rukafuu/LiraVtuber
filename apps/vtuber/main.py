"""
Entrypoint: python apps/vtuber/main.py

Runtime de voz (STT → LLM → TTS), VTube Studio, visão e tags XML.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.chdir(ROOT)

from dotenv import load_dotenv

load_dotenv(ROOT / ".env", encoding="utf-8-sig")

# Side-effect: inicia o loop do terminal (apps.vtuber.runtime)
import apps.vtuber.runtime  # noqa: F401, E402


def main():
    """O loop principal roda no import de runtime."""
    pass


if __name__ == "__main__":
    main()