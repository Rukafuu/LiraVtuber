from __future__ import annotations

from dataclasses import dataclass

from src.config.config_loader import CONFIG


@dataclass(frozen=True)
class RequestProfile:
    channel: str
    task_type: str
    allow_terminal_output: bool
    markdown_enabled: bool
    response_mode: str
    max_output_tokens: int
    thinking_level: str | None = None
    thinking_budget: int | None = None
    auto_route_media: bool = False
    media_model: str | None = None
    structured_output: bool = False
    response_mime_type: str | None = None


def _as_bool(value, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "sim", "on"}:
            return True
        if lowered in {"0", "false", "no", "nao", "não", "off"}:
            return False
    return default


def _as_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def get_chat_settings() -> dict:
    chat_cfg = CONFIG.get("CHAT", {})
    if not isinstance(chat_cfg, dict):
        chat_cfg = {}

    media_model = (
        chat_cfg.get("media_model")
        or CONFIG.get("HANA_INBOX_MODEL")
        or "gemini-2.5-flash"
    )

    return {
        "response_mode": str(chat_cfg.get("response_mode", "adaptive") or "adaptive"),
        "auto_route_media": _as_bool(chat_cfg.get("auto_route_media", True), True),
        "media_model": str(media_model),
        "max_output_tokens_normal": _as_int(chat_cfg.get("max_output_tokens_normal", 2048), 2048),
        "max_output_tokens_media": _as_int(chat_cfg.get("max_output_tokens_media", 8192), 8192),
        "markdown_enabled": _as_bool(chat_cfg.get("markdown_enabled", True), True),
    }


def build_request_context(
    channel: str = "terminal_voice",
    task_type: str = "chat_normal",
    **overrides,
) -> dict:
    settings = get_chat_settings()

    channel_key = (channel or "terminal_voice").strip().lower()
    task_key = (task_type or "chat_normal").strip().lower()

    if channel_key == "control_center_chat":
        is_media_task = task_key in {"analise_midia", "media_summary", "resumo_detalhado"}
        profile = RequestProfile(
            channel=channel_key,
            task_type=task_key,
            allow_terminal_output=False,
            markdown_enabled=settings["markdown_enabled"],
            response_mode=settings["response_mode"],
            max_output_tokens=settings["max_output_tokens_media"] if is_media_task else settings["max_output_tokens_normal"],
            thinking_level="medium" if is_media_task else "low",
            auto_route_media=settings["auto_route_media"],
            media_model=settings["media_model"],
            structured_output=is_media_task,
            response_mime_type="application/json" if is_media_task else None,
        )
    else:
        profile = RequestProfile(
            channel="terminal_voice",
            task_type=task_key,
            allow_terminal_output=True,
            markdown_enabled=False,
            response_mode="voice",
            max_output_tokens=768,
            thinking_level=None,
            auto_route_media=False,
            media_model=settings["media_model"],
            structured_output=False,
            response_mime_type=None,
        )

    context = {
        "channel": profile.channel,
        "task_type": profile.task_type,
        "allow_terminal_output": profile.allow_terminal_output,
        "markdown_enabled": profile.markdown_enabled,
        "response_mode": profile.response_mode,
        "max_output_tokens": profile.max_output_tokens,
        "thinking_level": profile.thinking_level,
        "thinking_budget": profile.thinking_budget,
        "auto_route_media": profile.auto_route_media,
        "media_model": profile.media_model,
        "structured_output": profile.structured_output,
        "response_mime_type": profile.response_mime_type,
    }
    context.update({key: value for key, value in overrides.items() if value is not None})
    return context
