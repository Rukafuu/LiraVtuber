from dataclasses import dataclass

from src.config.config_loader import CONFIG
from src.modules.media import get_media_runtime_capabilities


@dataclass(frozen=True)
class ProviderCapabilities:
    provider: str
    supports_images: bool
    supports_native_media: bool
    supports_native_search: bool
    supports_tool_calls: bool
    supports_music_generation: bool = False


def _to_float(value, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def resolve_llm_temperature(scope: str | None = None, default: float = 0.85) -> float:
    if scope:
        scoped_cfg = CONFIG.get(scope, {})
        if isinstance(scoped_cfg, dict) and scoped_cfg.get("LLM_TEMPERATURE") is not None:
            return _to_float(scoped_cfg.get("LLM_TEMPERATURE"), default)
    return _to_float(CONFIG.get("LLM_TEMPERATURE", default), default)


def get_provider_capabilities(provider: str, model: str | None = None, vision_enabled: bool | None = None) -> ProviderCapabilities:
    provider_key = (provider or "").strip().lower()
    model_key = (model or "").strip().lower()
    vision_active = bool(CONFIG.get("VISAO_ATIVA", False)) if vision_enabled is None else bool(vision_enabled)
    media_caps = get_media_runtime_capabilities()
    supports_music_generation = bool(media_caps["music_generation_enabled"])

    if provider_key == "google_cloud":
        return ProviderCapabilities(
            provider=provider_key,
            supports_images=True,
            supports_native_media=True,
            supports_native_search=not vision_active,
            supports_tool_calls=False,
            supports_music_generation=supports_music_generation,
        )

    if provider_key == "cerebras":
        return ProviderCapabilities(
            provider=provider_key,
            supports_images=False,
            supports_native_media=False,
            supports_native_search=False,
            supports_tool_calls=True,
            supports_music_generation=supports_music_generation,
        )

    if provider_key == "groq":
        return ProviderCapabilities(
            provider=provider_key,
            supports_images=True,
            supports_native_media=False,
            supports_native_search=("compound" in model_key and not vision_active),
            supports_tool_calls=True,
            supports_music_generation=supports_music_generation,
        )

    if provider_key == "openrouter":
        return ProviderCapabilities(
            provider=provider_key,
            supports_images=True,
            supports_native_media=False,
            supports_native_search=False,
            supports_tool_calls=True,
            supports_music_generation=supports_music_generation,
        )

    if provider_key == "openai":
        return ProviderCapabilities(
            provider=provider_key,
            supports_images=True,
            supports_native_media=False,
            supports_native_search=False,
            supports_tool_calls=True,
            supports_music_generation=supports_music_generation,
        )

    return ProviderCapabilities(
        provider=provider_key or "desconhecido",
        supports_images=False,
        supports_native_media=False,
        supports_native_search=False,
        supports_tool_calls=False,
        supports_music_generation=supports_music_generation,
    )


def get_ptt_settings() -> dict:
    gui_cfg = CONFIG.get("GUI", {})

    if isinstance(gui_cfg, dict):
        enabled = bool(gui_cfg.get("ptt_enabled", CONFIG.get("precione_para_falar", False)))
        key = str(gui_cfg.get("ptt_key", CONFIG.get("TECLA_PTT", "F2")) or "F2")
    else:
        enabled = bool(CONFIG.get("precione_para_falar", False))
        key = str(CONFIG.get("TECLA_PTT", "F2") or "F2")

    return {
        "enabled": enabled,
        "key": key,
    }


def get_stop_hotkey_settings() -> dict:
    gui_cfg = CONFIG.get("GUI", {})

    if isinstance(gui_cfg, dict):
        enabled = bool(gui_cfg.get("stop_hotkey_enabled", True))
        key = str(gui_cfg.get("stop_hotkey", "F8") or "F8")
    else:
        enabled = True
        key = "F8"

    return {
        "enabled": enabled,
        "key": key,
    }


def sync_legacy_ptt_config() -> dict:
    state = get_ptt_settings()
    CONFIG["precione_para_falar"] = bool(state["enabled"])
    CONFIG["TECLA_PTT"] = str(state["key"])
    return state
