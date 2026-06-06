"""Resolve project root and config paths for monorepo apps."""
from __future__ import annotations

import os
from pathlib import Path


def get_project_root() -> Path:
    env_root = os.getenv("LIRA_PROJECT_ROOT", "").strip()
    if env_root:
        return Path(env_root).resolve()

    markers = ("src/config/config.example.json", "main.py", "requirements.txt")
    candidates = [
        Path.cwd(),
        Path(__file__).resolve().parents[3],  # packages/lira-core/lira_core -> repo root
        Path(__file__).resolve().parents[2],  # fallback
    ]
    seen: set[Path] = set()
    for base in candidates:
        base = base.resolve()
        if base in seen:
            continue
        seen.add(base)
        if any((base / marker).exists() for marker in markers):
            return base
    return Path.cwd().resolve()


def get_config_dir() -> Path:
    return get_project_root() / "src" / "config"


def get_default_config_path() -> Path:
    return get_config_dir() / "config.json"


def get_default_example_config_path() -> Path:
    return get_config_dir() / "config.example.json"