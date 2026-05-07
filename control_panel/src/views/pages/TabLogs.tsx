import { useState, useEffect, useRef } from "react";
import { ApiController } from "../../controllers/api";
import { TerminalSquare, RefreshCw, Trash2, Pause, Play } from "lucide-react";

interface LogEntry {
  timestamp: string;
  level: string;
  message: string;
  logger: string;
}

export function TabLogs() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [isPaused, setIsPaused] = useState(false);
  const [filterLevel, setFilterLevel] = useState<string>("ALL");
  const scrollRef = useRef<HTMLDivElement>(null);
  const isPausedRef = useRef(isPaused); // Para aceder no setInterval

  // Mantém a ref sincronizada para o setInterval
  useEffect(() => {
    isPausedRef.current = isPaused;
  }, [isPaused]);

  const fetchLogs = async () => {
    if (isPausedRef.current) return;
    const data = await ApiController.getSystemLogs(200);
    setLogs(data.logs || []);
  };

  useEffect(() => {
    fetchLogs(); // Primeira vez
    const interval = setInterval(fetchLogs, 1500); // Polling a cada 1.5s
    return () => clearInterval(interval);
  }, []);

  // Auto-scroll
  useEffect(() => {
    if (scrollRef.current && !isPaused) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs, isPaused]);

  const getLevelColor = (level: string) => {
    switch (level.toUpperCase()) {
      case "INFO": return "text-green-400 drop-shadow-[0_0_5px_rgba(34,197,94,0.5)]";
      case "WARNING": return "text-yellow-400 drop-shadow-[0_0_5px_rgba(234,179,8,0.5)]";
      case "ERROR": 
      case "CRITICAL": return "text-red-400 font-bold drop-shadow-[0_0_5px_rgba(239,68,68,0.5)]";
      case "DEBUG": return "text-gray-400";
      default: return "text-white";
    }
  };

  const getRowBg = (level: string, index: number) => {
    if (level === "ERROR" || level === "CRITICAL") return "bg-red-500/10 border-l-2 border-red-500";
    if (level === "WARNING") return "bg-yellow-500/5 border-l-2 border-yellow-500/50";
    return index % 2 === 0 ? "bg-[rgba(255,255,255,0.02)]" : "bg-transparent";
  };

  const filteredLogs = filterLevel === "ALL" ? logs : logs.filter(l => l.level === filterLevel);

  return (
    <div className="w-full h-full bg-[var(--bg-sidebar)] backdrop-blur-2xl border border-[var(--border-strong)] rounded-2xl overflow-hidden shadow-2xl relative flex flex-col transition-all duration-500">
      
      {/* HEADER / TOOLBAR */}
      <div className="bg-[rgba(10,10,15,0.9)] border-b border-[var(--border-strong)] p-4 z-10 shadow-lg backdrop-blur-xl flex flex-col md:flex-row md:items-center justify-between gap-4 shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-black/50 flex items-center justify-center border border-white/10 shadow-inner">
            <TerminalSquare size={24} className="text-gray-300" />
          </div>
          <div>
            <h2 className="text-xl font-black text-white tracking-widest uppercase">System.Logs</h2>
            <p className="text-[10px] text-[var(--text-muted)] font-mono">Stream direto do core Python da Lira</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Filtros */}
          <div className="flex bg-black/50 border border-white/10 rounded-lg p-1">
            {["ALL", "INFO", "WARNING", "ERROR"].map(lvl => (
              <button
                key={lvl}
                onClick={() => setFilterLevel(lvl)}
                className={`px-3 py-1.5 text-[10px] font-bold font-mono rounded transition-colors ${filterLevel === lvl ? 'bg-white/10 text-white' : 'text-gray-500 hover:text-gray-300'}`}
              >
                {lvl}
              </button>
            ))}
          </div>

          <div className="h-6 w-px bg-white/10"></div>

          {/* Acções */}
          <button 
            onClick={() => setIsPaused(!isPaused)}
            className={`p-2 rounded-lg border transition-all ${isPaused ? 'bg-yellow-500/20 border-yellow-500/50 text-yellow-400' : 'bg-white/5 border-white/10 text-white hover:bg-white/10'}`}
            title={isPaused ? "Retomar Scroll e Leitura" : "Pausar Leitura (Congelar Ecrã)"}
          >
            {isPaused ? <Play size={16} /> : <Pause size={16} />}
          </button>
          
          <button 
            onClick={() => { fetchLogs(); if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight; }}
            className="p-2 rounded-lg bg-white/5 border border-white/10 text-white hover:bg-white/10 transition-all"
            title="Forçar Atualização"
          >
            <RefreshCw size={16} />
          </button>

          <button 
            onClick={() => setLogs([])}
            className="p-2 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 hover:bg-red-500/20 transition-all"
            title="Limpar Consola"
          >
            <Trash2 size={16} />
          </button>
        </div>
      </div>

      {/* TERMINAL AREA */}
      <div 
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-4 custom-scrollbar bg-[#0a0a0c] font-mono text-xs relative"
      >
        {filteredLogs.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full opacity-30">
            <TerminalSquare size={48} className="mb-4" />
            <span className="tracking-widest uppercase">Nenhum log capturado no buffer.</span>
          </div>
        ) : (
          <div className="flex flex-col">
            {filteredLogs.map((log, i) => (
              <div key={i} className={`flex items-start gap-4 py-1.5 px-3 hover:bg-white/5 transition-colors ${getRowBg(log.level, i)}`}>
                <span className="text-gray-500 shrink-0 select-none">[{log.timestamp}]</span>
                <span className={`w-20 shrink-0 font-bold ${getLevelColor(log.level)} select-none`}>
                  {log.level.padEnd(8)}
                </span>
                <span className="text-gray-400 shrink-0 truncate w-32 select-none" title={log.logger}>
                  {log.logger.split('.').pop()}
                </span>
                <span className={`flex-1 break-all whitespace-pre-wrap ${log.level === 'ERROR' ? 'text-red-300' : 'text-gray-200'}`}>
                  {log.message}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
