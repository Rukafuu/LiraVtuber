"""Optional bridge to app-level media settings (avoids hard dependency on src.modules)."""
from __future__ import annotations


def get_media_runtime_capabilities() -> dict:
    try:
        from src.modules.media import get_media_runtime_capabilities as _get

        return _get()
    except Exception:
        return {
            "music_generation_enabled": False,
            "image_generation_enabled": False,
        }