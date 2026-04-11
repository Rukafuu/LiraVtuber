from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelSpec:
    id: str
    label: str
    provider: str
    backend: str
    family: str
    context_window: int
    latency_class: str
    supports_vision: bool = False
    supports_native_search: bool = False
    preview: bool = False
    deprecated: bool = False
    active: bool = True


@dataclass(frozen=True)
class VoiceSpec:
    id: str
    label: str
    provider: str
    locale: str
    supports_rate: bool = True
    supports_pitch: bool = True
    pitch_mode: str = "native"


MODEL_CATALOG: tuple[ModelSpec, ...] = (
    # Groq
    ModelSpec("groq/compound", "Groq Compound", "groq", "groq_api", "compound", 131072, "fast", supports_native_search=True),
    ModelSpec("groq/compound-mini", "Groq Compound Mini", "groq", "groq_api", "compound", 131072, "fast", supports_native_search=True),
    ModelSpec("llama-3.1-8b-instant", "Llama 3.1 8B Instant", "groq", "groq_api", "llama", 131072, "fast"),
    ModelSpec("llama-3.3-70b-versatile", "Llama 3.3 70B Versatile", "groq", "groq_api", "llama", 131072, "medium"),
    ModelSpec("meta-llama/llama-4-scout-17b-16e-instruct", "Llama 4 Scout 17B 16E", "groq", "groq_api", "llama", 131072, "fast", supports_vision=True, preview=True),
    ModelSpec("openai/gpt-oss-20b", "GPT OSS 20B", "groq", "groq_api", "gpt-oss", 131072, "fast"),
    ModelSpec("openai/gpt-oss-120b", "GPT OSS 120B", "groq", "groq_api", "gpt-oss", 131072, "medium"),
    ModelSpec("qwen/qwen3-32b", "Qwen3 32B", "groq", "groq_api", "qwen", 131072, "fast", preview=True),
    # Google / Gemini
    ModelSpec("gemini-3.1-pro-preview", "Gemini 3.1 Pro Preview", "google_cloud", "vertex_or_gemini_api", "gemini", 1048576, "medium", supports_vision=True, preview=True),
    ModelSpec("gemini-3.1-flash-preview", "Gemini 3.1 Flash Preview", "google_cloud", "vertex_or_gemini_api", "gemini", 1048576, "fast", supports_vision=True, preview=True),
    ModelSpec("gemini-3.1-flash-lite-preview", "Gemini 3.1 Flash Lite Preview", "google_cloud", "vertex_or_gemini_api", "gemini", 1048576, "fast", supports_vision=True, preview=True),
    ModelSpec("gemini-2.5-pro", "Gemini 2.5 Pro", "google_cloud", "vertex_or_gemini_api", "gemini", 1048576, "medium", supports_vision=True),
    ModelSpec("gemini-2.5-flash", "Gemini 2.5 Flash", "google_cloud", "vertex_or_gemini_api", "gemini", 1048576, "fast", supports_vision=True),
    ModelSpec("gemini-2.5-flash-lite", "Gemini 2.5 Flash Lite", "google_cloud", "vertex_or_gemini_api", "gemini", 1048576, "fast", supports_vision=True),
    # Cerebras
    ModelSpec("gpt-oss-120b", "GPT OSS 120B", "cerebras", "cerebras_api", "gpt-oss", 131072, "fast"),
    ModelSpec("gpt-oss-20b", "GPT OSS 20B", "cerebras", "cerebras_api", "gpt-oss", 131072, "fast"),
    ModelSpec("llama3.1-8b", "Llama 3.1 8B", "cerebras", "cerebras_api", "llama", 131072, "fast"),
    ModelSpec("zai-glm-4.7", "GLM 4.7", "cerebras", "cerebras_api", "glm", 128000, "fast"),
    ModelSpec("qwen-3-235b-a22b-instruct-2507", "Qwen 3 235B A22B Instruct", "cerebras", "cerebras_api", "qwen", 131072, "medium", preview=True),
    # OpenAI
    ModelSpec("gpt-5.4", "GPT-5.4", "openai", "openai_api", "gpt", 1048576, "fast", supports_vision=True),
    ModelSpec("gpt-5.4-mini", "GPT-5.4 Mini", "openai", "openai_api", "gpt", 400000, "fast", supports_vision=True),
    ModelSpec("gpt-5.4-nano", "GPT-5.4 Nano", "openai", "openai_api", "gpt", 400000, "fast", supports_vision=True),
    ModelSpec("gpt-4.1", "GPT-4.1", "openai", "openai_api", "gpt", 1048576, "medium", supports_vision=True),
    ModelSpec("gpt-4.1-mini", "GPT-4.1 Mini", "openai", "openai_api", "gpt", 1048576, "fast", supports_vision=True),
    ModelSpec("gpt-4.1-nano", "GPT-4.1 Nano", "openai", "openai_api", "gpt", 1048576, "fast", supports_vision=True),
    ModelSpec("gpt-4o", "GPT-4o", "openai", "openai_api", "gpt", 128000, "fast", supports_vision=True),
    ModelSpec("gpt-4o-mini", "GPT-4o Mini", "openai", "openai_api", "gpt", 128000, "fast", supports_vision=True),
    ModelSpec("o3", "o3", "openai", "openai_api", "o-series", 200000, "medium"),
    ModelSpec("o4-mini", "o4 Mini", "openai", "openai_api", "o-series", 200000, "fast"),
    # OpenRouter
    ModelSpec("openai/gpt-5.4", "OpenAI GPT-5.4", "openrouter", "openrouter_api", "gpt", 1048576, "medium", supports_vision=True),
    ModelSpec("openai/gpt-5.4-mini", "OpenAI GPT-5.4 Mini", "openrouter", "openrouter_api", "gpt", 400000, "fast", supports_vision=True),
    ModelSpec("openai/gpt-5.4-nano", "OpenAI GPT-5.4 Nano", "openrouter", "openrouter_api", "gpt", 400000, "fast", supports_vision=True),
    ModelSpec("openai/gpt-4.1", "OpenAI GPT-4.1", "openrouter", "openrouter_api", "gpt", 1048576, "medium", supports_vision=True),
    ModelSpec("openai/gpt-4.1-mini", "OpenAI GPT-4.1 Mini", "openrouter", "openrouter_api", "gpt", 1048576, "fast", supports_vision=True),
    ModelSpec("openai/gpt-4.1-nano", "OpenAI GPT-4.1 Nano", "openrouter", "openrouter_api", "gpt", 1048576, "fast", supports_vision=True),
    ModelSpec("openai/gpt-4o", "OpenAI GPT-4o", "openrouter", "openrouter_api", "gpt", 128000, "fast", supports_vision=True),
    ModelSpec("openai/gpt-4o-mini", "OpenAI GPT-4o Mini", "openrouter", "openrouter_api", "gpt", 128000, "fast", supports_vision=True),
    ModelSpec("openai/o3", "OpenAI o3", "openrouter", "openrouter_api", "o-series", 200000, "medium"),
    ModelSpec("openai/o4-mini", "OpenAI o4 Mini", "openrouter", "openrouter_api", "o-series", 200000, "fast"),
    ModelSpec("openai/gpt-oss-20b", "OpenAI GPT OSS 20B", "openrouter", "openrouter_api", "gpt-oss", 131072, "fast"),
    ModelSpec("openai/gpt-oss-120b", "OpenAI GPT OSS 120B", "openrouter", "openrouter_api", "gpt-oss", 131072, "medium"),
    ModelSpec("google/gemini-3.1-pro-preview", "Gemini 3.1 Pro Preview", "openrouter", "openrouter_api", "gemini", 1048576, "medium", supports_vision=True, preview=True),
    ModelSpec("google/gemini-3.1-flash-preview", "Gemini 3.1 Flash Preview", "openrouter", "openrouter_api", "gemini", 1048576, "fast", supports_vision=True, preview=True),
    ModelSpec("google/gemini-3.1-flash-lite-preview", "Gemini 3.1 Flash Lite Preview", "openrouter", "openrouter_api", "gemini", 1048576, "fast", supports_vision=True, preview=True),
    ModelSpec("google/gemini-2.5-pro", "Gemini 2.5 Pro", "openrouter", "openrouter_api", "gemini", 1048576, "medium", supports_vision=True),
    ModelSpec("google/gemini-2.5-flash", "Gemini 2.5 Flash", "openrouter", "openrouter_api", "gemini", 1048576, "fast", supports_vision=True),
    ModelSpec("google/gemini-2.5-flash-lite", "Gemini 2.5 Flash Lite", "openrouter", "openrouter_api", "gemini", 1048576, "fast", supports_vision=True),
    ModelSpec("x-ai/grok-4-fast", "Grok 4 Fast", "openrouter", "openrouter_api", "grok", 2000000, "fast", supports_vision=True),
    ModelSpec("x-ai/grok-4", "Grok 4", "openrouter", "openrouter_api", "grok", 256000, "medium", supports_vision=True),
    ModelSpec("x-ai/grok-4.1-fast", "Grok 4.1 Fast", "openrouter", "openrouter_api", "grok", 2000000, "fast", supports_vision=True),
    ModelSpec("x-ai/grok-code-fast-1", "Grok Code Fast 1", "openrouter", "openrouter_api", "grok", 256000, "fast"),
    ModelSpec("x-ai/grok-3", "Grok 3", "openrouter", "openrouter_api", "grok", 131072, "medium"),
    ModelSpec("x-ai/grok-3-mini", "Grok 3 Mini", "openrouter", "openrouter_api", "grok", 131072, "fast"),
    ModelSpec("anthropic/claude-opus-4.6", "Claude Opus 4.6", "openrouter", "openrouter_api", "claude", 1000000, "medium"),
    ModelSpec("anthropic/claude-opus-4.1", "Claude Opus 4.1", "openrouter", "openrouter_api", "claude", 200000, "medium"),
    ModelSpec("anthropic/claude-sonnet-4.6", "Claude Sonnet 4.6", "openrouter", "openrouter_api", "claude", 1000000, "fast"),
    ModelSpec("anthropic/claude-sonnet-4.5", "Claude Sonnet 4.5", "openrouter", "openrouter_api", "claude", 1000000, "fast"),
    ModelSpec("anthropic/claude-sonnet-4", "Claude Sonnet 4", "openrouter", "openrouter_api", "claude", 200000, "fast"),
    ModelSpec("anthropic/claude-haiku-4.5", "Claude Haiku 4.5", "openrouter", "openrouter_api", "claude", 200000, "fast"),
    ModelSpec("anthropic/claude-3.7-sonnet", "Claude 3.7 Sonnet", "openrouter", "openrouter_api", "claude", 200000, "fast"),
    ModelSpec("anthropic/claude-3.5-haiku", "Claude 3.5 Haiku", "openrouter", "openrouter_api", "claude", 200000, "fast"),
    ModelSpec("meta-llama/llama-4-scout", "Llama 4 Scout", "openrouter", "openrouter_api", "llama", 131072, "fast", supports_vision=True),
    ModelSpec("meta-llama/llama-4-maverick", "Llama 4 Maverick", "openrouter", "openrouter_api", "llama", 131072, "medium", supports_vision=True),
    ModelSpec("qwen/qwen3-32b", "Qwen3 32B", "openrouter", "openrouter_api", "qwen", 131072, "fast"),
)


VOICE_CATALOG: tuple[VoiceSpec, ...] = (
    VoiceSpec("pt-BR-Neural2-A", "Google Neural2 A", "google", "pt-BR"),
    VoiceSpec("pt-BR-Neural2-B", "Google Neural2 B", "google", "pt-BR"),
    VoiceSpec("pt-BR-Neural2-C", "Google Neural2 C", "google", "pt-BR"),
    VoiceSpec("pt-BR-Wavenet-A", "Google Wavenet A", "google", "pt-BR"),
    VoiceSpec("pt-BR-Wavenet-B", "Google Wavenet B", "google", "pt-BR"),
    VoiceSpec("pt-BR-Wavenet-C", "Google Wavenet C", "google", "pt-BR"),
    VoiceSpec("pt-BR-Standard-A", "Google Standard A", "google", "pt-BR"),
    VoiceSpec("pt-BR-Standard-B", "Google Standard B", "google", "pt-BR"),
    VoiceSpec("pt-BR-Standard-C", "Google Standard C", "google", "pt-BR"),
    VoiceSpec("pt-BR-AntonioNeural", "Edge Antonio", "edge", "pt-BR"),
    VoiceSpec("pt-BR-BrendaNeural", "Edge Brenda", "edge", "pt-BR"),
    VoiceSpec("pt-BR-DonatoNeural", "Edge Donato", "edge", "pt-BR"),
    VoiceSpec("pt-BR-ElzaNeural", "Edge Elza", "edge", "pt-BR"),
    VoiceSpec("pt-BR-FabioNeural", "Edge Fabio", "edge", "pt-BR"),
    VoiceSpec("pt-BR-FranciscaNeural", "Edge Francisca", "edge", "pt-BR"),
    VoiceSpec("pt-BR-GiovannaNeural", "Edge Giovanna", "edge", "pt-BR"),
    VoiceSpec("pt-BR-HumbertoNeural", "Edge Humberto", "edge", "pt-BR"),
    VoiceSpec("pt-BR-JulioNeural", "Edge Julio", "edge", "pt-BR"),
    VoiceSpec("pt-BR-LeilaNeural", "Edge Leila", "edge", "pt-BR"),
    VoiceSpec("pt-BR-LeticiaNeural", "Edge Leticia", "edge", "pt-BR"),
    VoiceSpec("pt-BR-ManuelaNeural", "Edge Manuela", "edge", "pt-BR"),
    VoiceSpec("pt-BR-NicolauNeural", "Edge Nicolau", "edge", "pt-BR"),
    VoiceSpec("pt-BR-ThalitaNeural", "Edge Thalita", "edge", "pt-BR"),
    VoiceSpec("pt-BR-ValerioNeural", "Edge Valerio", "edge", "pt-BR"),
    VoiceSpec("pt-BR-YaraNeural", "Edge Yara", "edge", "pt-BR"),
    VoiceSpec("pt-BR-MacerioMultilingualNeural", "Edge Macerio Multilingual", "edge", "pt-BR"),
    VoiceSpec("pt-BR-ThalitaMultilingualNeural", "Edge Thalita Multilingual", "edge", "pt-BR"),
    VoiceSpec("pt-BR-Macerio:DragonHDLatestNeural", "Edge Macerio DragonHD", "edge", "pt-BR"),
    VoiceSpec("pt-BR-Thalita:DragonHDLatestNeural", "Edge Thalita DragonHD", "edge", "pt-BR"),
    VoiceSpec("pt-BR-AntonioNeural", "Azure Antonio", "azure", "pt-BR"),
    VoiceSpec("pt-BR-BrendaNeural", "Azure Brenda", "azure", "pt-BR"),
    VoiceSpec("pt-BR-DonatoNeural", "Azure Donato", "azure", "pt-BR"),
    VoiceSpec("pt-BR-ElzaNeural", "Azure Elza", "azure", "pt-BR"),
    VoiceSpec("pt-BR-FabioNeural", "Azure Fabio", "azure", "pt-BR"),
    VoiceSpec("pt-BR-FranciscaNeural", "Azure Francisca", "azure", "pt-BR"),
    VoiceSpec("pt-BR-GiovannaNeural", "Azure Giovanna", "azure", "pt-BR"),
    VoiceSpec("pt-BR-HumbertoNeural", "Azure Humberto", "azure", "pt-BR"),
    VoiceSpec("pt-BR-JulioNeural", "Azure Julio", "azure", "pt-BR"),
    VoiceSpec("pt-BR-LeilaNeural", "Azure Leila", "azure", "pt-BR"),
    VoiceSpec("pt-BR-LeticiaNeural", "Azure Leticia", "azure", "pt-BR"),
    VoiceSpec("pt-BR-ManuelaNeural", "Azure Manuela", "azure", "pt-BR"),
    VoiceSpec("pt-BR-NicolauNeural", "Azure Nicolau", "azure", "pt-BR"),
    VoiceSpec("pt-BR-ThalitaNeural", "Azure Thalita", "azure", "pt-BR"),
    VoiceSpec("pt-BR-ValerioNeural", "Azure Valerio", "azure", "pt-BR"),
    VoiceSpec("pt-BR-YaraNeural", "Azure Yara", "azure", "pt-BR"),
    VoiceSpec("pt-BR-MacerioMultilingualNeural", "Azure Macerio Multilingual", "azure", "pt-BR"),
    VoiceSpec("pt-BR-ThalitaMultilingualNeural", "Azure Thalita Multilingual", "azure", "pt-BR"),
    VoiceSpec("pt-BR-Macerio:DragonHDLatestNeural", "Azure Macerio DragonHD", "azure", "pt-BR"),
    VoiceSpec("pt-BR-Thalita:DragonHDLatestNeural", "Azure Thalita DragonHD", "azure", "pt-BR"),
    VoiceSpec("alloy", "OpenAI Alloy", "openai", "multi", supports_pitch=False, pitch_mode="style"),
    VoiceSpec("ash", "OpenAI Ash", "openai", "multi", supports_pitch=False, pitch_mode="style"),
    VoiceSpec("ballad", "OpenAI Ballad", "openai", "multi", supports_pitch=False, pitch_mode="style"),
    VoiceSpec("cedar", "OpenAI Cedar", "openai", "multi", supports_pitch=False, pitch_mode="style"),
    VoiceSpec("coral", "OpenAI Coral", "openai", "multi", supports_pitch=False, pitch_mode="style"),
    VoiceSpec("echo", "OpenAI Echo", "openai", "multi", supports_pitch=False, pitch_mode="style"),
    VoiceSpec("fable", "OpenAI Fable", "openai", "multi", supports_pitch=False, pitch_mode="style"),
    VoiceSpec("marin", "OpenAI Marin", "openai", "multi", supports_pitch=False, pitch_mode="style"),
    VoiceSpec("nova", "OpenAI Nova", "openai", "multi", supports_pitch=False, pitch_mode="style"),
    VoiceSpec("onyx", "OpenAI Onyx", "openai", "multi", supports_pitch=False, pitch_mode="style"),
    VoiceSpec("sage", "OpenAI Sage", "openai", "multi", supports_pitch=False, pitch_mode="style"),
    VoiceSpec("shimmer", "OpenAI Shimmer", "openai", "multi", supports_pitch=False, pitch_mode="style"),
)


def get_llm_providers() -> list[str]:
    return ["groq", "google_cloud", "cerebras", "openrouter", "openai"]


def get_tts_providers() -> list[str]:
    return ["elevenlabs", "google", "azure", "openai", "edge"]


def get_models_for_provider(provider: str, *, vision_only: bool = False, include_inactive: bool = False) -> list[ModelSpec]:
    provider_key = (provider or "").strip().lower()
    return [
        model
        for model in MODEL_CATALOG
        if model.provider == provider_key and (include_inactive or model.active) and (model.supports_vision or not vision_only)
    ]


def search_models_for_provider(provider: str, query: str = "", *, vision_only: bool = False) -> list[ModelSpec]:
    models = get_models_for_provider(provider, vision_only=vision_only)
    needle = (query or "").strip().lower()
    if not needle:
        return models
    return [model for model in models if needle in model.id.lower() or needle in model.label.lower() or needle in model.family.lower()]


def get_model_ids_for_provider(provider: str, *, vision_only: bool = False, query: str = "") -> list[str]:
    return [model.id for model in search_models_for_provider(provider, query=query, vision_only=vision_only)] + ["Outro..."]


def get_default_model(provider: str, *, vision_only: bool = False) -> str:
    models = get_models_for_provider(provider, vision_only=vision_only)
    if not models:
        return ""
    return models[0].id


def find_model(provider: str, model_id: str | None) -> ModelSpec | None:
    provider_key = (provider or "").strip().lower()
    model_key = (model_id or "").strip()
    for model in MODEL_CATALOG:
        if model.provider == provider_key and model.id == model_key:
            return model
    return None


def get_voices_for_provider(provider: str) -> list[VoiceSpec]:
    provider_key = (provider or "").strip().lower()
    return [voice for voice in VOICE_CATALOG if voice.provider == provider_key]


def search_voices_for_provider(provider: str, query: str = "") -> list[VoiceSpec]:
    voices = get_voices_for_provider(provider)
    needle = (query or "").strip().lower()
    if not needle:
        return voices
    return [voice for voice in voices if needle in voice.id.lower() or needle in voice.label.lower() or needle in voice.locale.lower()]


def get_voice_ids_for_provider(provider: str, query: str = "") -> list[str]:
    return [voice.id for voice in search_voices_for_provider(provider, query=query)]


def get_default_voice(provider: str) -> str:
    voices = get_voices_for_provider(provider)
    if not voices:
        return ""
    return voices[0].id


def find_voice(provider: str, voice_id: str | None) -> VoiceSpec | None:
    provider_key = (provider or "").strip().lower()
    voice_key = (voice_id or "").strip()
    for voice in VOICE_CATALOG:
        if voice.provider == provider_key and voice.id == voice_key:
            return voice
    return None
