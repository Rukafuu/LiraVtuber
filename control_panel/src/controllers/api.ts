/**
 * Controller principal da API (Camada de Controle - MVC)
 * Gerencia a comunicação entre a View (React) e o Backend (Rust/Python)
 */
import type { ServiceStatus, WatchdogHeartbeatStatus, WhatsAppSession } from "../models/types";
// Em ambiente Tauri, window.location.hostname pode ser tauri.localhost ou similar.
// Forçamos 127.0.0.1 para conectar ao backend Python local.
const HOST = "127.0.0.1";
const BACKEND_URL = `http://${HOST}:8042`;
const WS_URL = `ws://${HOST}:8042`;


export const ApiController = {
  // === WEBSOCKET ===
  connectEmotionsWebSocket: (onMessage: (data: any) => void) => {
    const ws = new WebSocket(`${WS_URL}/ws/emotions`);
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessage(data);
      } catch (e) {
        console.error("Erro ao parsear emoções via WS:", e);
      }
    };
    ws.onerror = (error) => console.error("Erro no WebSocket de Emoções:", error);
    return ws;
  },

  connectStatusWebSocket: (onMessage: (data: any) => void) => {
    const ws = new WebSocket(`${WS_URL}/ws/status`);
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessage(data);
      } catch (e) {
        console.error("Erro ao parsear status via WS:", e);
      }
    };
    ws.onerror = (error) => console.error("Erro no WebSocket de Status:", error);
    return ws;
  },

  // === GET/POST REST API ===
  getSystemStatus: async () => {
    try {
      // Tenta buscar o status via REST se o WS falhar ou como inicialização
      const res = await fetch(`${BACKEND_URL}/api/status`);
      if (res.ok) return await res.json();
      throw new Error("Falha na API de Status");
    } catch (error) {
      return {
        cpu: 0, ramPercent: 0, ramUsedStr: "0.0", ramTotalStr: "0.0",
        llmProvider: "—", llmModel: "—", ttsProvider: "—",
        modules: { llm: false, tts: false, stt: false, visao: false, vtube_studio: false, discord: false }
      };
    }
  },

  getLlmConfig: async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/config/llm`);
      if (res.ok) return await res.json();
      throw new Error("Falha na API");
    } catch (error) {
      const savedConfig = localStorage.getItem("lira_llm_config");
      if (savedConfig) return JSON.parse(savedConfig);
      return { llmProvider: "openai", llmModel: "gpt-4o", llmFilter: "", llmTemperature: 0.85, visionModel: "", ttsProvider: "elevenlabs", ttsVoice: "", ttsModel: "", ttsFilter: "", ttsSpeed: 1.0, ttsPitch: 0.0, ttsStability: 0.5, ttsSimilarity: 0.75, ttsStyle: 0.0, ttsSpeakerBoost: true };
    }
  },

  updateLlmConfig: async (config: any) => {
    try {
      localStorage.setItem("lira_llm_config", JSON.stringify(config));
      await fetch(`${BACKEND_URL}/api/config/llm`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(config)
      });
      return true;
    } catch (error) {
      console.error("Backend não conectado. Salvo apenas localmente.");
      return true;
    }
  },

  speakText: async (text: string) => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/tts/speak`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text })
      });
      return res.ok;
    } catch (error) {
      console.error("Erro ao reproduzir TTS:", error);
      return false;
    }
  },

  // === CONEXOES ===
  getConnectionsConfig: async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/config/conexoes`);
      if (res.ok) return await res.json();
      throw new Error("Falha na API");
    } catch (error) {
      const savedConfig = localStorage.getItem("lira_conexoes_config");
      if (savedConfig) return JSON.parse(savedConfig);
      return { tts: true, stt: true, ptt: false, pttKey: "F2", stopHotkey: true, stopKey: "F4", vts: false, discord: false, visao: false };
    }
  },

  updateConnectionsConfig: async (config: any) => {
    try {
      localStorage.setItem("lira_conexoes_config", JSON.stringify(config));
      await fetch(`${BACKEND_URL}/api/config/conexoes`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(config)
      });
      return true;
    } catch (error) {
      console.error("Backend não conectado. Salvo apenas localmente.");
      return true;
    }
  },

  // === CHAT WEBSOCKET ===
  /**
   * Conecta ao WebSocket de chat e já envia a mensagem quando abrir.
   * Retorna { ws, send } onde send() pode ser usado para reenviar sem reconectar.
   */
  connectChatWebSocket: (
    message: string,
    images_b64: string[],
    provider: string,
    model: string,
    history: { role: string; content: string }[],
    onMessageChunk: (text: string) => void,
    onReplaceContent: (text: string) => void,
    onMeta: (meta: any) => void,
    onMedia: (media: any) => void,
    onDone: () => void,
    onError: (err: any) => void
  ): { ws: WebSocket; send: (msg: string, imgs?: string[]) => void } => {
    const ws = new WebSocket(`${WS_URL}/ws/chat`);

    ws.onopen = () => {
      ws.send(JSON.stringify({ text: message, images_b64, provider, model, history }));
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "chunk") {
          onMessageChunk(data.content);
        } else if (data.type === "replace_content") {
          onReplaceContent(data.content);
        } else if (data.type === "meta") {
          onMeta(data.meta);
        } else if (data.type === "media") {
          onMedia(data.media);
        } else if (data.type === "done") {
          onDone();
        } else if (data.type === "error") {
          onError(data.content);
        }
      } catch (e) {
        console.error("Erro no ws chat:", e);
      }
    };
    ws.onerror = (error) => onError(error);

    return {
      ws,
      send: (msg: string, imgs?: string[]) => {
        ws.send(JSON.stringify({ text: msg, images_b64: imgs || [], provider, model, history }));
      }
    };
  },

  // Cancela a resposta atual do chat
  cancelChatResponse: async () => {
    try {
      await fetch(`${BACKEND_URL}/api/chat/cancel`, { method: "POST" });
    } catch (error) {
      console.error("Erro ao cancelar resposta:", error);
    }
  },

  // === HISTORICO DO CHAT ===
  getChatHistory: async (limit: number = 50): Promise<{messages: {role: string, content: string}[]}> => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/chat/history?limit=${limit}`);
      if (res.ok) return await res.json();
      throw new Error("Falha na API");
    } catch (error) {
      console.error("Erro ao carregar historico:", error);
      return { messages: [] };
    }
  },

  // === LOGS DO SISTEMA ===
  getSystemLogs: async (limit: number = 100): Promise<{logs: {timestamp: string, level: string, message: string, logger: string}[]}> => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/logs?limit=${limit}`);
      if (res.ok) return await res.json();
      throw new Error("Falha na API");
    } catch (error) {
      console.error("Erro ao carregar logs:", error);
      return { logs: [] };
    }
  },

  // === PERSONA & PROMPTS ===
  getPersona: async (): Promise<{ text: string; path?: string; error?: string }> => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/config/persona`);
      if (res.ok) return await res.json();
      throw new Error("Falha na API");
    } catch (error) {
      console.error("Erro ao carregar persona:", error);
      return { text: "" };
    }
  },

  savePersona: async (text: string): Promise<boolean> => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/config/persona`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      const data = await res.json();
      return res.ok && data.status === "ok";
    } catch (error) {
      console.error("Erro ao salvar persona:", error);
      return false;
    }
  },

  getPromptRules: async (): Promise<{ rules: Record<string, string>; path?: string; error?: string }> => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/config/prompt`);
      if (res.ok) return await res.json();
      throw new Error("Falha na API");
    } catch (error) {
      console.error("Erro ao carregar prompts:", error);
      return { rules: {} };
    }
  },

  savePromptRules: async (rules: Record<string, string>): Promise<boolean> => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/config/prompt`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rules }),
      });
      const data = await res.json();
      return res.ok && data.status === "ok";
    } catch (error) {
      console.error("Erro ao salvar prompts:", error);
      return false;
    }
  },

  getMemoryStatus: async (): Promise<{
    sqlite_messages: number;
    graph_facts: number;
    rag_memories: number;
    chroma_ready: boolean;
    chroma_env: boolean;
    memory_ready: boolean;
  }> => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/memory/status`);
      if (res.ok) return await res.json();
      throw new Error("Falha na API");
    } catch (error) {
      return {
        sqlite_messages: 0,
        graph_facts: 0,
        rag_memories: 0,
        chroma_ready: false,
        chroma_env: false,
        memory_ready: false,
      };
    }
  },

  // === MEMORIA (KNOWLEDGE GRAPH E RAG) ===
  getMemoryGraph: async (): Promise<{facts: {subject: string, relation: string, object: string}[]}> => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/memory/graph`);
      if (res.ok) return await res.json();
      throw new Error("Falha na API");
    } catch (error) {
      console.error("Erro ao carregar knowledge graph:", error);
      return { facts: [] };
    }
  },

  deleteMemoryGraph: async (subject: string, relation: string, object: string): Promise<boolean> => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/memory/graph`, {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ subject, relation, object })
      });
      return res.ok;
    } catch (error) {
      console.error("Erro ao deletar fato do grafo:", error);
      return false;
    }
  },

  createMemoryGraph: async (subject: string, relation: string, object: string): Promise<boolean> => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/memory/graph`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ subject, relation, object })
      });
      return res.ok;
    } catch (error) {
      console.error("Erro ao criar fato do grafo:", error);
      return false;
    }
  },

  getMemoryRag: async (): Promise<{memories: {id: string, text: string, metadata: any}[]}> => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/memory/rag`);
      if (res.ok) return await res.json();
      throw new Error("Falha na API");
    } catch (error) {
      console.error("Erro ao carregar memoria RAG:", error);
      return { memories: [] };
    }
  },

  deleteMemoryRag: async (id: string): Promise<boolean> => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/memory/rag/${id}`, {
        method: "DELETE"
      });
      return res.ok;
    } catch (error) {
      console.error("Erro ao deletar memoria RAG:", error);
      return false;
    }
  },

  createMemoryRag: async (text: string): Promise<{id: string, text: string, metadata: any} | null> => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/memory/rag`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text })
      });
      if (!res.ok) return null;
      const data = await res.json();
      return data.memory || null;
    } catch (error) {
      console.error("Erro ao criar memoria RAG:", error);
      return null;
    }
  },

  updateMemoryRag: async (id: string, text: string, metadata: any): Promise<boolean> => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/memory/rag/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, metadata })
      });
      return res.ok;
    } catch (error) {
      console.error("Erro ao atualizar memoria RAG:", error);
      return false;
    }
  },

  getCatalog: async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/catalog`);
      if (res.ok) return await res.json();
      throw new Error("Falha na API");
    } catch (error) {
      console.error("Erro ao carregar catalogo:", error);
      return null;
    }
  },

  upsertCustomModel: async (provider: string, id: string, label: string, supportsVision: boolean) => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/catalog/custom-models`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider, id, label, supportsVision })
      });
      if (!res.ok) return null;
      const data = await res.json();
      return data.model || null;
    } catch (error) {
      console.error("Erro ao salvar modelo customizado:", error);
      return null;
    }
  },

  deleteCustomModel: async (provider: string, id: string): Promise<boolean> => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/catalog/custom-models`, {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider, id })
      });
      return res.ok;
    } catch (error) {
      console.error("Erro ao remover modelo customizado:", error);
      return false;
    }
  },

  getWatchdogHeartbeat: async (): Promise<WatchdogHeartbeatStatus | null> => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/watchdog/heartbeat`);
      if (!res.ok) throw new Error("Falha na API");
      return await res.json();
    } catch (error) {
      console.error("Erro ao carregar watchdog:", error);
      return null;
    }
  },

  getServices: async (): Promise<{ services: ServiceStatus[]; updated_at: number }> => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/services`);
      if (!res.ok) throw new Error("Falha na API");
      return await res.json();
    } catch (error) {
      console.error("Erro ao carregar serviços:", error);
      return { services: [], updated_at: 0 };
    }
  },

  startService: async (id: string): Promise<{ status: string; message?: string; pid?: number; log_file?: string }> => {
    const res = await fetch(`${BACKEND_URL}/api/services/${id}/start`, { method: "POST" });
    const data = await res.json();
    if (!res.ok && !data.message) {
      data.status = "error";
      data.message = `HTTP ${res.status}`;
    }
    return data;
  },

  stopService: async (id: string): Promise<{ status: string; message?: string }> => {
    const res = await fetch(`${BACKEND_URL}/api/services/${id}/stop`, { method: "POST" });
    return res.json();
  },

  getWhatsAppSession: async (): Promise<WhatsAppSession> => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/services/whatsapp_bridge/session`);
      if (!res.ok) throw new Error("Falha na API");
      return await res.json();
    } catch {
      return {
        connected: false,
        bridge_state: "stopped",
        connection: null,
        qr: { available: false, revision: 0, payload: null, updated_at: null },
        pairing_code: null,
      };
    }
  },

  resetWhatsAppSession: async (): Promise<{ status: string; message?: string }> => {
    const res = await fetch(`${BACKEND_URL}/api/services/whatsapp_bridge/reset-session`, {
      method: "POST",
    });
    return res.json();
  },

  getMcpStatus: async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/mcp/status`);
      if (res.ok) return await res.json();
      return { status: "error" };
    } catch {
      return { status: "error" };
    }
  },

  getMcpServers: async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/mcp/servers`);
      if (res.ok) return await res.json();
      return { servers: [] };
    } catch {
      return { servers: [] };
    }
  },

  setMcpServerEnabled: async (serverId: string, enabled: boolean) => {
    const res = await fetch(`${BACKEND_URL}/api/mcp/servers/${serverId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled }),
    });
    return res.json();
  },

  getMcpTools: async (server?: string, refresh = false) => {
    try {
      const q = new URLSearchParams();
      if (server) q.set("server", server);
      if (refresh) q.set("refresh", "true");
      const res = await fetch(`${BACKEND_URL}/api/mcp/tools?${q}`);
      if (res.ok) return await res.json();
      return { tools: [] };
    } catch {
      return { tools: [] };
    }
  },

  getMcpAllowlist: async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/mcp/allowlist`);
      if (res.ok) return await res.json();
      return { allowed: [] };
    } catch {
      return { allowed: [] };
    }
  },

  setMcpAllowlist: async (allowed: string[]) => {
    const res = await fetch(`${BACKEND_URL}/api/mcp/allowlist`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ allowed }),
    });
    return res.json();
  },

  callMcp: async (
    server: string,
    tool: string,
    args: Record<string, unknown> = {}
  ): Promise<{ ok: boolean; result?: string; error?: string; detail?: unknown; tool?: string }> => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/mcp/call`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ server, tool, arguments: args }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const err =
          typeof data.detail === "string"
            ? data.detail
            : data.message || res.statusText || "MCP call failed";
        return { ok: false, error: err, detail: data };
      }
      return { ok: true, result: data.result, tool: data.tool };
    } catch (e) {
      return { ok: false, error: e instanceof Error ? e.message : String(e) };
    }
  },

  // === FINANCE ===
  getFinanceSummary: async (dias: number = 30) => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/finance/summary?dias=${dias}`);
      if (res.ok) return await res.json();
      throw new Error("Falha na API de Finanças");
    } catch (error) {
      console.error("Erro ao carregar resumo financeiro:", error);
      return { status: "error", message: String(error) };
    }
  },

  saveFinanceTransaction: async (payload: { id?: number; tipo: string; valor: number; estabelecimento?: string; categoria?: string; descricao?: string }) => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/finance/transactions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (res.ok) return await res.json();
      throw new Error("Falha ao salvar transação");
    } catch (error) {
      console.error("Erro ao salvar transação:", error);
      return { status: "error", message: String(error) };
    }
  },

  deleteFinanceTransaction: async (txId: number) => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/finance/transactions/${txId}`, {
        method: "DELETE"
      });
      if (res.ok) return await res.json();
      throw new Error("Falha ao excluir transação");
    } catch (error) {
      console.error("Erro ao excluir transação:", error);
      return { status: "error", message: String(error) };
    }
  },
};

