"""Compatibility shim — use lira_core.config.config_loader."""
from lira_core.config.config_loader import *  # noqa: F403
from lira_core.config.config_loader import CONFIG, ConfigLoader, salvar_configuracoes

__all__ = ["CONFIG", "ConfigLoader", "salvar_configuracoes"]
