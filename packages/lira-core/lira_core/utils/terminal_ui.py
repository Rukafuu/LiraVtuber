"""Minimal terminal UI hooks used by BaseLLM (full UI stays in src.utils.text)."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from lira_core.config.config_loader import CONFIG
from lira_core.paths import get_config_dir

logger = logging.getLogger(__name__)


class _CoreTerminalUI:
    """No-op by default; apps can replace via bind_terminal_ui()."""

    def print_pensando(self, provedor: str = "LLM_PROVIDER") -> None:
        return

    def print_lira_text(self, text: str, first_chunk: bool = False) -> None:
        return


_ui = _CoreTerminalUI()


def get_terminal_ui():
    return _ui


def bind_terminal_ui(ui_obj) -> None:
    global _ui
    _ui = ui_obj


class ConsoleUI(_CoreTerminalUI):
    """Lightweight console output for VTuber runtime when src.utils.text is unavailable."""

    def print_pensando(self, provedor: str = "LLM_PROVIDER") -> None:
        try:
            cfg_path = get_config_dir() / "config.json"
            if cfg_path.exists():
                cfg = json.loads(cfg_path.read_text(encoding="utf-8-sig"))
            else:
                cfg = dict(CONFIG._config) if hasattr(CONFIG, "_config") else {}
            llm_key = cfg.get("LLM_PROVIDER", provedor.lower())
            prov_cfg = cfg.get("LLM_PROVIDERS", {}).get(llm_key, {})
            modelo = prov_cfg.get("modelo_chat", prov_cfg.get("modelo", "N/D"))
            print(f"[LIRA] Pensando ({provedor.upper()} / {modelo})...", flush=True)
        except Exception as exc:
            logger.debug("[terminal_ui] print_pensando: %s", exc)
            print(f"[LIRA] Pensando ({provedor.upper()})...", flush=True)


ui = ConsoleUI()