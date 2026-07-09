import json
import logging
import os
from fastapi import APIRouter

from src.config.config_loader import CONFIG
from src.core.provider_catalog import MODEL_CATALOG, VOICE_CATALOG, get_llm_providers, get_tts_providers

logger = logging.getLogger(__name__)

router = APIRouter(tags=["catalog"])


def _model_spec_to_dict(model) -> dict:
    return {
        "id": model.id,
        "label": model.label,
        "provider": model.provider,
        "supportsVision": bool(model.supports_vision),
        "custom": False,
    }


def _voice_spec_to_dict(voice) -> dict:
    return {
        "id": voice.id,
        "label": voice.label,
        "provider": voice.provider,
        "supportsRate": bool(getattr(voice, "supports_rate", True)),
        "supportsPitch": bool(getattr(voice, "supports_pitch", True)),
        "pitchMode": getattr(voice, "pitch_mode", "native"),
    }


def _get_custom_models() -> list[dict]:
    raw_models = CONFIG.get("CUSTOM_LLM_MODELS", [])
    if not isinstance(raw_models, list):
        return []

    models: list[dict] = []
    for item in raw_models:
        if not isinstance(item, dict):
            continue

        provider = str(item.get("provider") or "").strip().lower()
        model_id = str(item.get("id") or "").strip()
        if not provider or not model_id:
            continue

        models.append({
            "id": model_id,
            "label": str(item.get("label") or model_id).strip() or model_id,
            "provider": provider,
            "supportsVision": bool(item.get("supportsVision", item.get("supports_vision", True))),
            "custom": True,
        })
    return models


@router.get("/api/catalog")
async def get_catalog():
    return {
        "llmProviders": get_llm_providers(),
        "ttsProviders": get_tts_providers(),
        "models": [_model_spec_to_dict(model) for model in MODEL_CATALOG] + _get_custom_models(),
        "voices": [_voice_spec_to_dict(voice) for voice in VOICE_CATALOG],
        "elevenlabsModels": [
            "eleven_flash_v2_5",
            "eleven_multilingual_v2",
            "eleven_turbo_v2_5",
            "eleven_v3",
        ],
        "openaiTtsModels": ["gpt-4o-mini-tts"],
    }


@router.post("/api/catalog/custom-models")
async def upsert_custom_model(payload: dict):
    provider = str(payload.get("provider") or "").strip().lower()
    model_id = str(payload.get("id") or "").strip()
    if not provider or not model_id:
        return {"status": "error", "message": "Provider e modelo sao obrigatorios."}

    custom_model = {
        "id": model_id,
        "label": str(payload.get("label") or model_id).strip() or model_id,
        "provider": provider,
        "supportsVision": bool(payload.get("supportsVision", True)),
        "custom": True,
    }
    custom_models = [
        model for model in _get_custom_models()
        if not (model["provider"] == provider and model["id"] == model_id)
    ]
    custom_models.append(custom_model)
    CONFIG["CUSTOM_LLM_MODELS"] = custom_models

    try:
        CONFIG.save()
    except Exception as e:
        return {"status": "error", "message": str(e)}

    return {"status": "ok", "model": custom_model}


@router.delete("/api/catalog/custom-models")
async def delete_custom_model(payload: dict):
    provider = str(payload.get("provider") or "").strip().lower()
    model_id = str(payload.get("id") or "").strip()
    if not provider or not model_id:
        return {"status": "error", "message": "Provider e modelo sao obrigatorios."}

    before = _get_custom_models()
    after = [
        model for model in before
        if not (model["provider"] == provider and model["id"] == model_id)
    ]
    CONFIG["CUSTOM_LLM_MODELS"] = after

    try:
        CONFIG.save()
    except Exception as e:
        return {"status": "error", "message": str(e)}

    return {"status": "ok", "removed": len(after) != len(before)}


@router.get("/api/config/llm")
async def get_llm_config():
    provider = CONFIG.get("LLM_PROVIDER", "openai")
    providers = CONFIG.get("LLM_PROVIDERS", {})
    provider_data = providers.get(provider, {}) if isinstance(providers, dict) else {}

    tts_provider = CONFIG.get("TTS_PROVIDER", "elevenlabs")
    tts_settings = CONFIG.get("TTS_SETTINGS", {})
    tts_data = tts_settings.get(tts_provider, {}) if isinstance(tts_settings, dict) else {}

    return {
        "llmProvider": provider,
        "llmModel": provider_data.get("modelo", ""),
        "llmFilter": "",
        "llmTemperature": CONFIG.get("LLM_TEMPERATURE", 0.85),
        "visionModel": provider_data.get("modelo_vision", ""),
        "ttsProvider": tts_provider,
        "ttsVoice": tts_data.get("voice_id", tts_data.get("voice", "")),
        "ttsModel": tts_data.get("model_id", tts_data.get("model", "")),
        "ttsFilter": "",
        "ttsSpeed": tts_data.get("rate", 1.0),
        "ttsPitch": tts_data.get("pitch", 0.0),
        "ttsStability": tts_data.get("stability", 0.5),
        "ttsSimilarity": tts_data.get("similarity_boost", 0.75),
        "ttsStyle": tts_data.get("style", 0.0),
        "ttsSpeakerBoost": tts_data.get("speaker_boost", True)
    }


@router.post("/api/config/llm")
async def update_llm_config(payload: dict):
    CONFIG["LLM_PROVIDER"] = payload.get("llmProvider", "openai")
    CONFIG["LLM_TEMPERATURE"] = payload.get("llmTemperature", 0.85)

    # Atualiza modelo do provider
    providers = CONFIG.get("LLM_PROVIDERS", {})
    if not isinstance(providers, dict):
        providers = {}
    provider = payload.get("llmProvider", "openai")
    block = providers.get(provider, {})
    if not isinstance(block, dict):
        block = {}
    block["modelo"] = payload.get("llmModel", "")
    block["modelo_chat"] = payload.get("llmModel", "")
    block["modelo_vision"] = payload.get("visionModel", "")
    providers[provider] = block
    CONFIG["LLM_PROVIDERS"] = providers

    # Atualiza TTS
    tts_provider = payload.get("ttsProvider", "elevenlabs")
    CONFIG["TTS_PROVIDER"] = tts_provider
    tts_settings = CONFIG.get("TTS_SETTINGS", {})
    if not isinstance(tts_settings, dict):
        tts_settings = {}
    tts_block = tts_settings.get(tts_provider, {})
    if not isinstance(tts_block, dict):
        tts_block = {}

    tts_block["voice"] = payload.get("ttsVoice", "")
    tts_block["rate"] = payload.get("ttsSpeed", 1.0)
    tts_block["pitch"] = payload.get("ttsPitch", 0.0)

    if tts_provider == "elevenlabs":
        tts_block["voice_id"] = payload.get("ttsVoice", "")
        tts_block["model_id"] = payload.get("ttsModel", "")
        tts_block["stability"] = payload.get("ttsStability", 0.5)
        tts_block["similarity_boost"] = payload.get("ttsSimilarity", 0.75)
        tts_block["style"] = payload.get("ttsStyle", 0.0)
        tts_block["speaker_boost"] = payload.get("ttsSpeakerBoost", True)

    tts_settings[tts_provider] = tts_block
    CONFIG["TTS_SETTINGS"] = tts_settings

    try:
        CONFIG.save()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/api/config/conexoes")
async def get_conexoes_config():
    return {
        "tts": CONFIG.get("TTS_ATIVO", True),
        "stt": CONFIG.get("STT_ATIVO", True),
        "ptt": CONFIG.get("GUI", {}).get("ptt_enabled", False),
        "pttKey": CONFIG.get("GUI", {}).get("ptt_key", "F2"),
        "stopHotkey": CONFIG.get("GUI", {}).get("stop_hotkey_enabled", True),
        "stopKey": CONFIG.get("GUI", {}).get("stop_hotkey", "F4"),
        "vts": CONFIG.get("VTUBESTUDIO_ATIVO", False),
        "discord": CONFIG.get("Modo_discord", False),
        "visao": CONFIG.get("VISAO_ATIVA", False)
    }


@router.post("/api/config/conexoes")
async def update_conexoes_config(payload: dict):
    CONFIG["TTS_ATIVO"] = payload.get("tts", True)
    CONFIG["STT_ATIVO"] = payload.get("stt", True)
    CONFIG["VTUBESTUDIO_ATIVO"] = payload.get("vts", False)
    CONFIG["Modo_discord"] = payload.get("discord", False)
    CONFIG["VISAO_ATIVA"] = payload.get("visao", False)

    gui_cfg = CONFIG.get("GUI", {})
    if not isinstance(gui_cfg, dict):
        gui_cfg = {}
    gui_cfg["ptt_enabled"] = payload.get("ptt", False)
    gui_cfg["ptt_key"] = payload.get("pttKey", "F2")
    gui_cfg["stop_hotkey_enabled"] = payload.get("stopHotkey", True)
    gui_cfg["stop_hotkey"] = payload.get("stopKey", "F4")
    CONFIG["GUI"] = gui_cfg

    try:
        CONFIG.save()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/api/vts/state")
async def get_vts_state():
    STATE_PATH = os.path.abspath("data/vts_state.json")
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"connected": False, "authenticated": False, "status": "offline"}
