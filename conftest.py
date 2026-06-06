"""Pytest: garante lira-core no PYTHONPATH."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LIRA_CORE_PKG = ROOT / "packages" / "lira-core"

if str(LIRA_CORE_PKG) not in sys.path:
    sys.path.insert(0, str(LIRA_CORE_PKG))

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))