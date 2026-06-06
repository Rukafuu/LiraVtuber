"""Lira Control Center API (FastAPI, porta 8042)."""

from apps.control_api.server import app, start_server

__all__ = ["app", "start_server"]