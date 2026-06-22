/**
 * Definições de Tipos e Modelos de Dados (Camada Model - MVC)
 */

export interface MenuOption {
  icon?: React.ReactNode | string;
  iconPath?: string;
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
    whatsapp?: boolean;
  };
  services?: ServiceStatus[];
}

export type ServiceRunState =
  | "stopped"
  | "starting"
  | "running"
  | "degraded"
  | "error";

export interface ServiceLogLine {
  ts: string;
  stream: string;
  line: string;
}

export interface ServiceStatus {
  id: string;
  label: string;
  state: ServiceRunState;
  managed: boolean;
  external: boolean;
  pid: number | null;
  uptime_sec: number | null;
  health_http: boolean | null;
  connection: string | null;
  last_error: string | null;
  log_tail: ServiceLogLine[];
  command: string[];
  cwd: string;
}

export interface WhatsAppQrInfo {
  available: boolean;
  revision: number;
  fingerprint?: string;
  payload: string | null;
  updated_at: string | null;
}

export interface WhatsAppSession {
  connected: boolean;
  bridge_state: string;
  connection: string | null;
  qr: WhatsAppQrInfo;
  pairing_code: string | null;
  link_mode?: string | null;
  status_message?: string | null;
  disconnect_code?: number | null;
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

export type WatchdogQueuePhase =
  | "Healthy"
  | "Alerted"
  | "Backoff"
  | "Restarting"
  | "Verifying"
  | string;

export interface WatchdogQueueStatus {
  Phase: WatchdogQueuePhase;
  InRecovery: boolean;
  FailureCount: number;
  CircuitOpen: boolean;
  Healthy?: boolean;
  ServiceState?: string;
  Connection?: string;
}

export interface WatchdogHistoryPoint {
  ts: number;
  age_sec: number | null;
  queues: Record<string, WatchdogQueueStatus>;
}

export interface WatchdogHeartbeatStatus {
  status: string;
  last_heartbeat: string | null;
  age_sec: number | null;
  stale: boolean;
  stale_threshold_sec: number;
  watchdog_pid: number | null;
  uptime_sec: number | null;
  watchdog_version: number | string | null;
  queues: Record<string, WatchdogQueueStatus>;
  history: WatchdogHistoryPoint[];
}

