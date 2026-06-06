"""Compatibility shim — use lira_core.brain.base_llm."""
from lira_core.brain.base_llm import *  # noqa: F403
from lira_core.brain.base_llm import BaseLLM

try:
    from lira_core.utils import terminal_ui as _terminal_ui
    from src.utils.text import ui as _rich_ui

    _terminal_ui.bind_terminal_ui(_rich_ui)
except Exception:
    pass

__all__ = ["BaseLLM"]
