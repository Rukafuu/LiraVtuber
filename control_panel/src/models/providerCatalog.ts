export interface ModelSpec {
  id: string;
  label: string;
  provider: string;
  supportsVision: boolean;
  custom?: boolean;
}

export interface VoiceSpec {
  id: string;
  label: string;
  provider: string;
  supportsRate?: boolean;
  supportsPitch?: boolean;
  pitchMode?: string;
}

export const LLM_PROVIDERS = ["groq", "google_cloud", "cerebras", "openrouter", "openai"];
export const TTS_PROVIDERS = ["elevenlabs", "google", "azure", "openai", "edge"];

export const MODEL_CATALOG: ModelSpec[] = [
  // Groq
  { id: "groq/compound", label: "Groq Compound", provider: "groq", supportsVision: false },
  { id: "llama-3.1-8b-instant", label: "Llama 3.1 8B Instant", provider: "groq", supportsVision: false },
  { id: "llama-3.3-70b-versatile", label: "Llama 3.3 70B Versatile", provider: "groq", supportsVision: false },
  { id: "meta-llama/llama-4-scout-17b-16e-instruct", label: "Llama 4 Scout 17B 16E", provider: "groq", supportsVision: true },
  { id: "openai/gpt-oss-20b", label: "GPT OSS 20B", provider: "groq", supportsVision: false },
  { id: "openai/gpt-oss-120b", label: "GPT OSS 120B", provider: "groq", supportsVision: false },
  { id: "qwen/qwen3-32b", label: "Qwen3 32B", provider: "groq", supportsVision: false },

  // Google
  { id: "gemini-2.5-flash", label: "Gemini 2.5 Flash", provider: "google_cloud", supportsVision: true },
  { id: "gemini-2.5-flash-lite", label: "Gemini 2.5 Flash Lite", provider: "google_cloud", supportsVision: true },
  { id: "gemini-2.5-pro", label: "Gemini 2.5 Pro", provider: "google_cloud", supportsVision: true },
  { id: "gemini-3-flash-preview", label: "Gemini 3 Flash Preview", provider: "google_cloud", supportsVision: true },
  { id: "gemini-3-pro-preview", label: "Gemini 3 Pro Preview", provider: "google_cloud", supportsVision: true },
  { id: "gemini-3.1-flash-lite-preview", label: "Gemini 3.1 Flash Lite Preview", provider: "google_cloud", supportsVision: true },

  // Cerebras
  { id: "gpt-oss-120b", label: "GPT OSS 120B", provider: "cerebras", supportsVision: false },
  { id: "llama3.1-8b", label: "Llama 3.1 8B", provider: "cerebras", supportsVision: false },
  { id: "zai-glm-4.7", label: "GLM 4.7", provider: "cerebras", supportsVision: false },
  { id: "qwen-3-235b-a22b-instruct-2507", label: "Qwen 3 235B A22B", provider: "cerebras", supportsVision: false },

  // OpenAI
  { id: "gpt-5.4", label: "GPT-5.4", provider: "openai", supportsVision: true },
  { id: "gpt-5.4-mini", label: "GPT-5.4 Mini", provider: "openai", supportsVision: true },
  { id: "gpt-5.4-nano", label: "GPT-5.4 Nano", provider: "openai", supportsVision: true },
  { id: "gpt-4.1", label: "GPT-4.1", provider: "openai", supportsVision: true },
  { id: "gpt-4.1-mini", label: "GPT-4.1 Mini", provider: "openai", supportsVision: true },
  { id: "gpt-4o", label: "GPT-4o", provider: "openai", supportsVision: true },
  { id: "gpt-4o-mini", label: "GPT-4o Mini", provider: "openai", supportsVision: true },
  { id: "o3", label: "o3", provider: "openai", supportsVision: false },
  { id: "o4-mini", label: "o4 Mini", provider: "openai", supportsVision: false },

  // OpenRouter
  { id: "openai/gpt-5.4", label: "OpenAI GPT-5.4", provider: "openrouter", supportsVision: true },
  { id: "openai/gpt-4.1", label: "OpenAI GPT-4.1", provider: "openrouter", supportsVision: true },
  { id: "google/gemini-2.5-flash", label: "Gemini 2.5 Flash", provider: "openrouter", supportsVision: true },
  { id: "x-ai/grok-4", label: "Grok 4", provider: "openrouter", supportsVision: true },
  { id: "anthropic/claude-opus-4.6", label: "Claude Opus 4.6", provider: "openrouter", supportsVision: false },
  { id: "anthropic/claude-sonnet-4.6", label: "Claude Sonnet 4.6", provider: "openrouter", supportsVision: false },
  { id: "meta-llama/llama-4-scout", label: "Llama 4 Scout", provider: "openrouter", supportsVision: true }
];

export const VOICE_CATALOG: VoiceSpec[] = [
  // Google
  { id: "pt-BR-Neural2-A", label: "Google Neural2 A", provider: "google" },
  { id: "pt-BR-Neural2-B", label: "Google Neural2 B", provider: "google" },
  { id: "pt-BR-Neural2-C", label: "Google Neural2 C", provider: "google" },
  { id: "pt-BR-Wavenet-A", label: "Google Wavenet A", provider: "google" },

  // Edge
  { id: "pt-BR-AntonioNeural", label: "Edge Antonio", provider: "edge" },
  { id: "pt-BR-FranciscaNeural", label: "Edge Francisca", provider: "edge" },
  { id: "pt-BR-ThalitaNeural", label: "Edge Thalita", provider: "edge" },

  // Azure
  { id: "pt-BR-AntonioNeural", label: "Azure Antonio", provider: "azure" },
  { id: "pt-BR-FranciscaNeural", label: "Azure Francisca", provider: "azure" },
  { id: "pt-BR-ThalitaNeural", label: "Azure Thalita", provider: "azure" },

  // OpenAI
  { id: "alloy", label: "OpenAI Alloy", provider: "openai" },
  { id: "echo", label: "OpenAI Echo", provider: "openai" },
  { id: "fable", label: "OpenAI Fable", provider: "openai" },
  { id: "nova", label: "OpenAI Nova", provider: "openai" },
  { id: "shimmer", label: "OpenAI Shimmer", provider: "openai" }
];

export const ELEVENLABS_TTS_MODELS = [
  "eleven_flash_v2_5",
  "eleven_multilingual_v2",
  "eleven_turbo_v2_5",
  "eleven_v3",
];

export const OPENAI_TTS_MODELS = [
  "gpt-4o-mini-tts",
];
