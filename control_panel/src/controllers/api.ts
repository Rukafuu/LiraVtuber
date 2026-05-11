/**
 * Controller principal da API (Camada de Controle - MVC)
 * Gerencia a comunicação entre a View (React) e o Backend (Rust/Python)
 */
const HOST = window.location.hostname;
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
    return {
      cpu: 0, ramPercent: 0, ramUsedStr: "0.0", ramTotalStr: "0.0",
      llmProvider: "—", llmModel: "—", ttsProvider: "—",
      modules: { llm: false, tts: false, stt: false, visao: false, vtube_studio: false, discord: false }
    };
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
  }
};
