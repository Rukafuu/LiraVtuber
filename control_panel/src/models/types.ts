/**
 * Definições de Tipos e Modelos de Dados (Camada Model - MVC)
 */

export interface MenuOption {
  icon: React.ReactNode | string;
  label: string;
  id: string;
}

export interface ConnectionsConfig {
  tts: boolean;
  stt: boolean;
  ptt: boolean;
  pttKey: string;
  stopHotkey: boolean;
  stopKey: string;
  vts: boolean;
  discord: boolean;
  visao: boolean;
}

export interface SystemStatus {
  cpu: number;
  ramPercent: number;
  ramUsedStr: string;
  ramTotalStr: string;
  llmProvider: string;
  llmModel: string;
  ttsProvider: string;
  modules: {
    llm: boolean;
    tts: boolean;
    stt: boolean;
    visao: boolean;
    vtube_studio: boolean;
    discord: boolean;
  };
}

export interface LlmConfig {
  llmProvider: string;
  llmModel: string;
  llmFilter: string;
  llmTemperature: number;
  visionModel: string;
  ttsProvider: string;
  ttsVoice: string;
  ttsModel: string;
  ttsFilter: string;
  ttsSpeed: number;
  ttsPitch: number;
  ttsStability: number;
  ttsSimilarity: number;
  ttsStyle: number;
  ttsSpeakerBoost: boolean;
}

export interface ChatMessage {
  id: string;
  role: "user" | "lira" | "system";
  content: string;
  timestamp: string;
  meta?: {
    provider: string;
    model: string;
    tokens?: number;
  };
  attachments?: string[];
  images_b64?: string[];
  media?: {
    type: 'image' | 'music';
    url?: string;
    job_id?: string;
  }[];
}

export interface EmotionEvent {
  timestamp: number;
  emotion: string;
  turno: number;
}

export interface EmotionState {
  mood: number;
  current_emotion: string;
  turno: number;
  last_thought: string;
  history: EmotionEvent[];
  updated_at: number;
}
