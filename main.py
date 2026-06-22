"""
Supervisor local LiraVT.

Uso:
  python main.py              # stack completa
  python main.py backend-only # API + WhatsApp + bridge
  python main.py api-only     # so Control API
  python main.py frontend-only
  python main.py healthcheck
  python main.py status

VTuber (voz/terminal): python apps/vtuber/main.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.lira_supervisor.supervisor import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())