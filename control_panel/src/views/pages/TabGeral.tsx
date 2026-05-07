import { useEffect, useState } from "react";
import { ApiController } from "../../controllers/api";
import { SystemStatus } from "../../models/types";

import { MonitorDot, BrainCircuit, Mic, Video, Eye, MessageSquareText, PlugZap, Activity, TerminalSquare } from "lucide-react";
import { useTranslation } from "react-i18next";

// Componente auxiliar para Anel Circular Sci-Fi
function CircularGauge({ value, label, subLabel, colorClass, shadowClass }: { value: number, label: string, subLabel: string, colorClass: string, shadowClass: string }) {
  const radius = 40;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (value / 100) * circumference;

  return (
    <div className="relative flex flex-col items-center justify-center">
      <div className="relative w-32 h-32 flex items-center justify-center">
        {/* Fundo do Anel */}
        <svg className="absolute inset-0 w-full h-full transform -rotate-90">
          <circle 
            cx="64" cy="64" r={radius} 
            className="stroke-white/5 fill-transparent" 
            strokeWidth="8" 
          />
          {/* Anel de Progresso */}
          <circle 
            cx="64" cy="64" r={radius} 
            className={`fill-transparent transition-all duration-1000 ease-out ${colorClass} ${shadowClass}`}
            strokeWidth="8"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            stroke="currentColor"
          />
        </svg>
        <div className="absolute flex flex-col items-center justify-center animate-fade-in">
          <span className="text-xl font-black font-mono text-white tracking-tighter">
            {value.toFixed(0)}<span className="text-xs text-[var(--text-muted)]">%</span>
          </span>
        </div>
      </div>
      <div className="mt-2 text-center">
        <div className="text-xs font-bold uppercase tracking-widest text-[var(--text-secondary)]">{label}</div>
        <div className="text-[9px] font-mono text-[var(--text-muted)]">{subLabel}</div>
      </div>
    </div>
  );
}

export function TabGeral() {
  const { t } = useTranslation();
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [logs, setLogs] = useState<string[]>([]);

  useEffect(() => {
    // Tenta conectar via WebSocket
    let ws: WebSocket | null = null;
    try {
      ws = ApiController.connectStatusWebSocket((data) => {
        setStatus(data);
      });
    } catch (e) {
      console.log("WebSocket não disponível, usando fallback.");
    }

    // Loop fallback caso não tenha backend
    const interval = setInterval(() => {
      if (!ws || ws.readyState !== WebSocket.OPEN) {
        ApiController.getSystemStatus().then(setStatus).catch(() => {});
      }
    }, 2000);

    // Simulated Live Logs para dar ambiente sci-fi
    const logInterval = setInterval(() => {
      const messages = [
        "SISTEMA: Conexão neural estável...",
        "VTB: Parâmetros faciais atualizados.",
        "MEM: Indexação de vetores RAG concluída.",
        "LLM: Aguardando input do utilizador.",
        "SYS: Verificação térmica do CPU OK.",
        "LIRA: Heartbeat sincronizado.",
        "NET: Latência < 12ms",
        "STT: Escuta ativa no microfone principal."
      ];
      setLogs(prev => {
        const newLogs = [...prev, `[${new Date().toLocaleTimeString()}] ${messages[Math.floor(Math.random() * messages.length)]}`];
        return newLogs.slice(-6); // Mantém os últimos 6
      });
    }, 4500);

    return () => {
      clearInterval(interval);
      clearInterval(logInterval);
      if (ws) ws.close();
    };
  }, []);

  const getCpuColor = (cpu: number) => {
    if (cpu > 80) return "text-red-500 shadow-[0_0_15px_rgba(239,68,68,0.5)]";
    if (cpu > 50) return "text-yellow-500 shadow-[0_0_15px_rgba(234,179,8,0.5)]";
    return "text-[var(--purple-neon)] drop-shadow-[0_0_8px_var(--purple-neon)]";
  };

  return (
    <div className="w-full h-full bg-[var(--bg-sidebar)] backdrop-blur-2xl border border-[var(--border-strong)] rounded-2xl p-8 overflow-y-auto custom-scrollbar shadow-2xl relative transition-all duration-500">
      {/* HEADER */}
      <div className="mb-8">
        <h2 className="flex items-center gap-3 text-3xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-[var(--purple-neon)] to-[var(--cyan-neon)] mb-2">
          <MonitorDot size={32} className="text-[var(--purple-neon)]" /> {t('geral.titulo')}
        </h2>
        <p className="text-sm text-[var(--text-muted)]">
          {t('geral.subtitulo')}
        </p>
      </div>

      {/* CARDS GRID */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        
        {/* CARD: RECURSOS DO SISTEMA (Com Anéis Sci-Fi) */}
        <div className="bg-[rgba(0,0,0,0.4)] backdrop-blur-md border border-[var(--border-strong)] rounded-2xl p-6 flex flex-col justify-center shadow-lg transition-all hover:shadow-[0_0_30px_rgba(168,85,247,0.1)] relative overflow-hidden group">
          <div className="absolute top-[-50px] right-[-50px] w-40 h-40 bg-[var(--purple-neon)] rounded-full blur-[80px] opacity-20 pointer-events-none group-hover:opacity-40 transition-opacity duration-1000"></div>
          
          <div className="flex items-center justify-between mb-6 relative z-10">
            <h3 className="font-bold text-[var(--text-primary)] text-lg flex items-center gap-2">
              <Activity size={20} className="text-[var(--purple-neon)]" /> {t('geral.hardware_status')}
            </h3>
            <div className="flex gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse"></span>
              <span className="text-[9px] font-mono font-bold text-green-400 uppercase tracking-widest">{t('geral.live')}</span>
            </div>
          </div>
          
          <div className="flex justify-around items-center relative z-10 py-4">
            <CircularGauge 
              value={status?.cpu || 0} 
              label={t('geral.cpu')} 
              subLabel={t('geral.processamento')} 
              colorClass={status ? getCpuColor(status.cpu) : "text-[var(--purple-neon)]"}
              shadowClass=""
            />
            
            <div className="h-20 w-px bg-gradient-to-b from-transparent via-white/10 to-transparent"></div>

            <CircularGauge 
              value={status?.ramPercent || 0} 
              label={t('geral.ram')} 
              subLabel={status ? `${status.ramUsedStr} / ${status.ramTotalStr} GB` : t('geral.memoria')}
              colorClass="text-[var(--cyan-neon)] drop-shadow-[0_0_8px_var(--cyan-neon)]"
              shadowClass=""
            />
          </div>
        </div>

        {/* CARD: MOTOR LLM ATIVO & TERMINAL */}
        <div className="bg-[rgba(0,0,0,0.4)] backdrop-blur-md border border-[var(--border-strong)] rounded-2xl p-6 flex flex-col shadow-lg transition-all hover:shadow-[0_0_30px_rgba(34,211,238,0.1)] relative overflow-hidden">
          <div className="absolute bottom-0 right-0 w-32 h-32 bg-[var(--cyan-neon)] rounded-full blur-[80px] opacity-10 pointer-events-none"></div>

          <h3 className="font-bold text-[var(--text-primary)] mb-4 text-lg flex items-center gap-2">
            <BrainCircuit size={20} className="text-[var(--cyan-neon)]" /> {t('geral.intel_central')}
          </h3>
          
          <div className="grid grid-cols-2 gap-3 relative z-10 mb-4">
            <div className="flex flex-col bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.05)] rounded-xl p-3 hover:bg-[rgba(255,255,255,0.04)] transition-colors">
              <span className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider mb-1 font-bold">{t('geral.llm_engine')}</span>
              <span className="font-mono text-sm text-[var(--text-primary)] font-black">{status ? status.llmProvider.toUpperCase() : "—"}</span>
            </div>
            
            <div className="flex flex-col bg-gradient-to-br from-[var(--purple-dark)] to-transparent border border-[var(--purple-neon)]/30 rounded-xl p-3">
              <span className="text-[10px] text-[var(--purple-neon)] opacity-80 uppercase tracking-wider mb-1 font-bold">{t('geral.modelo_core')}</span>
              <span className="font-mono text-sm text-white font-black truncate">{status ? status.llmModel : "—"}</span>
            </div>
          </div>

          <div className="flex-1 min-h-[100px] bg-black/60 border border-white/5 rounded-xl p-3 relative overflow-hidden flex flex-col font-mono text-[10px]">
            <div className="flex items-center gap-2 mb-2 text-[var(--text-muted)] border-b border-white/5 pb-1">
              <TerminalSquare size={12} />
              <span className="uppercase tracking-widest">{t('geral.system_log')}</span>
            </div>
            <div className="flex-1 flex flex-col justify-end gap-1">
              {logs.map((log, i) => (
                <div key={i} className="text-green-400/80 animate-fade-in break-all whitespace-pre-wrap">{log}</div>
              ))}
            </div>
            <div className="absolute top-0 left-0 w-1 h-full bg-gradient-to-b from-transparent via-green-500/50 to-transparent animate-pulse"></div>
          </div>
        </div>

        {/* CARD: MÓDULOS ATIVOS (Ocupa 2 colunas) */}
        <div className="bg-[rgba(0,0,0,0.4)] backdrop-blur-md border border-[var(--border-strong)] rounded-2xl p-6 md:col-span-2 shadow-lg transition-all relative overflow-hidden group hover:border-[var(--purple-neon)]/50 hover:shadow-[0_0_30px_rgba(168,85,247,0.15)]">
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full h-full bg-gradient-to-r from-transparent via-[rgba(168,85,247,0.03)] to-transparent pointer-events-none"></div>

          <h3 className="font-bold text-[var(--text-primary)] mb-6 text-lg flex items-center gap-2 relative z-10">
            <PlugZap size={20} className="text-green-400" /> {t('geral.conexoes_modulos')}
          </h3>
          
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4 relative z-10">
            {[
              { id: "llm", label: t('geral.llm_principal'), icon: <BrainCircuit size={20} /> },
              { id: "tts", label: t('geral.voz_tts'), icon: <Mic size={20} /> },
              { id: "stt", label: t('geral.ouvido_stt'), icon: <Mic size={20} /> },
              { id: "visao", label: t('geral.visao_comp'), icon: <Eye size={20} /> },
              { id: "vtube_studio", label: t('geral.vtube_studio'), icon: <Video size={20} /> },
              { id: "discord", label: t('geral.bot_discord'), icon: <MessageSquareText size={20} /> },
            ].map((mod) => {
              const isAtivo = status ? status.modules[mod.id as keyof SystemStatus["modules"]] : false;
              
              return (
                <div key={mod.id} className={`group bg-[rgba(0,0,0,0.4)] border ${isAtivo ? 'border-green-500/30 shadow-[inset_0_0_15px_rgba(34,197,94,0.1)]' : 'border-[rgba(255,255,255,0.05)]'} rounded-xl p-4 flex items-center gap-4 transition-all hover:scale-[1.02]`}>
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center text-lg ${isAtivo ? 'bg-green-500/20 text-green-400' : 'bg-white/5 text-gray-500'}`}>
                    {mod.icon}
                  </div>
                  <div className="flex flex-col">
                    <span className={`text-sm font-bold ${isAtivo ? 'text-[var(--text-primary)]' : 'text-[var(--text-muted)]'}`}>
                      {mod.label}
                    </span>
                    <span className={`text-[10px] uppercase font-bold tracking-widest ${isAtivo ? 'text-green-400 drop-shadow-[0_0_5px_rgba(34,197,94,0.5)]' : 'text-red-500/70'}`}>
                      {isAtivo ? t('geral.online') : t('geral.offline')}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

      </div>
    </div>
  );
}
