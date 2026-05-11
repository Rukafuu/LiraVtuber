import { useEffect, useState } from "react";
import { MonitorPlay, Settings, Power, RefreshCcw, Activity } from "lucide-react";

interface VtsState {
  status: string;
  connected: boolean;
  authenticated: boolean;
  host: string;
  port: number;
  hotkeys: number;
  expressions: number;
  mouth_parameter: string;
  tracking_mode: string;
  last_error: string;
  last_expression: string;
  updated_at: number;
}

export function TabVTube() {
  const [state, setState] = useState<VtsState | null>(null);

  // Polling simples para ler o vts_state.json
  const [isLive, setIsLive] = useState(false);
  const [log, setLog] = useState<string>("Iniciando conexão neural...");

  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const HOST = window.location.hostname;
        const res = await fetch(`http://${HOST}:8042/api/vts/state`);
        if (res.ok) {
           const data = await res.json();
           setState(data);
           setIsLive(data.authenticated);
           if (data.last_error && data.last_error !== "Nenhum erro") {
             setLog(data.last_error);
           } else if (data.authenticated) {
             setLog("VTube Studio Auth: OK. LipSync Ativo.");
           } else {
             setLog("Aguardando VTube Studio...");
           }
        } else {
           setIsLive(false);
        }
      } catch (e) {
        setIsLive(false);
        setLog("Erro ao comunicar com a API do Control Center.");
      }
    }, 1500);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="w-full h-full bg-[var(--bg-sidebar)] backdrop-blur-2xl border border-[var(--border-strong)] rounded-2xl p-8 overflow-y-auto custom-scrollbar shadow-2xl relative transition-all duration-500">
      {/* HEADER */}
      <div className="mb-8">
        <h2 className="flex items-center gap-3 text-3xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-[var(--cyan-neon)] to-blue-500 mb-2">
          <MonitorPlay size={32} className="text-[var(--cyan-neon)]" /> VTube Studio
        </h2>
        <p className="text-sm text-[var(--text-muted)]">
          Integração nativa com o avatar 2D/3D da Lira. Sincronização labial e expressões.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        
        {/* CARD: STATUS DE CONEXÃO E BIOMETRIA */}
        <div className="bg-[rgba(0,0,0,0.4)] backdrop-blur-md border border-[var(--border-strong)] rounded-2xl p-6 shadow-lg flex flex-col relative overflow-hidden group hover:shadow-[0_0_30px_rgba(34,211,238,0.1)] transition-all">
           {/* Efeito Sweep Scan */}
           <div className="absolute top-0 left-0 w-full h-1 bg-[var(--cyan-neon)] opacity-50 shadow-[0_0_15px_var(--cyan-neon)] transform -translate-y-full animate-[fadeInSlideUp_3s_infinite]"></div>

           <h3 className="font-bold text-[var(--text-primary)] mb-6 text-sm uppercase tracking-widest flex items-center gap-2">
             <Activity size={16} className="text-[var(--cyan-neon)]" /> Estado do Avatar
           </h3>

           <div className="flex-1 flex flex-col items-center justify-center text-center">
             <div className="relative mb-6">
               {/* Círculos pulsantes de status */}
               <div className={`absolute inset-0 rounded-full ${isLive ? 'bg-green-500' : 'bg-red-500'} blur-xl opacity-20 animate-pulse`}></div>
               <div className={`w-24 h-24 rounded-full flex items-center justify-center border-4 relative z-10 bg-black/50 backdrop-blur-md transition-colors duration-1000 ${isLive ? 'border-green-500 text-green-400' : 'border-red-500 text-red-400'}`}>
                 <Power size={40} className={isLive ? "drop-shadow-[0_0_10px_rgba(34,197,94,0.8)]" : ""} />
               </div>
             </div>

             <h3 className="text-xl font-black text-white mb-1 uppercase tracking-widest">
                {isLive ? "Sincronizado" : "Desconectado"}
             </h3>
             <p className="text-xs text-[var(--text-muted)] font-mono bg-white/5 px-3 py-1 rounded-lg border border-white/5 mb-6">
               {state?.host || "localhost"}:{state?.port || "8001"}
             </p>
           </div>

           <div className="flex flex-col w-full gap-2 mt-auto">
              <div className="flex justify-between items-center text-[10px] bg-black/40 p-3 rounded-lg border border-white/5">
                 <span className="text-[var(--text-muted)] uppercase font-bold tracking-widest">Status WebSock</span>
                 <span className={`font-bold ${isLive ? 'text-green-400' : 'text-red-400'}`}>{state?.status || "OFFLINE"}</span>
              </div>
           </div>
        </div>

        {/* CARD: MODELO E PARÂMETROS */}
        <div className="md:col-span-2 bg-[rgba(0,0,0,0.4)] backdrop-blur-md border border-[var(--border-strong)] rounded-2xl p-6 shadow-lg relative group flex flex-col hover:border-[var(--cyan-neon)]/50 transition-all">
           <div className="absolute top-[-50px] right-[-50px] w-40 h-40 bg-[var(--cyan-neon)] rounded-full blur-[80px] opacity-10 pointer-events-none transition-opacity duration-1000 group-hover:opacity-30"></div>

           <div className="flex items-center justify-between mb-6 relative z-10">
              <div className="flex items-center gap-3">
                 <div className="w-8 h-8 rounded-lg bg-[var(--cyan-dark)] flex items-center justify-center border border-[var(--cyan-neon)]/30">
                    <Settings size={16} className="text-[var(--cyan-neon)]" />
                 </div>
                 <h3 className="font-bold text-white text-sm uppercase tracking-widest">Parâmetros de Tracking</h3>
              </div>
              <button className="p-2 bg-white/5 hover:bg-[var(--cyan-dark)] border border-white/10 hover:border-[var(--cyan-neon)] rounded-lg transition-all text-[var(--text-muted)] hover:text-white flex items-center gap-2 text-xs font-bold uppercase">
                 <RefreshCcw size={12} /> Recarregar
              </button>
           </div>

           <div className="grid grid-cols-2 gap-4 relative z-10 mb-6">
              <div className="bg-black/40 border border-white/10 hover:border-[var(--cyan-neon)]/50 transition-colors rounded-xl p-5 flex flex-col justify-between">
                 <span className="text-[10px] text-[var(--text-muted)] uppercase tracking-widest font-black mb-3">LipSync Activo</span>
                 <div className="flex items-end justify-between">
                    <span className="text-sm text-[var(--cyan-neon)] font-mono font-bold drop-shadow-[0_0_5px_var(--cyan-neon)]">{state?.mouth_parameter || "N/A"}</span>
                    {isLive && (
                      <div className="flex gap-1 h-6 items-end opacity-80">
                         {[0.3, 0.8, 0.5, 0.9, 0.4].map((h, i) => (
                           <div key={i} className="w-1.5 bg-[var(--cyan-neon)] rounded-t-sm animate-pulse shadow-[0_0_8px_var(--cyan-neon)]" style={{ height: `${h * 100}%`, animationDelay: `${i * 100}ms` }}></div>
                         ))}
                      </div>
                    )}
                 </div>
              </div>

              <div className="bg-black/40 border border-white/10 hover:border-[var(--cyan-neon)]/50 transition-colors rounded-xl p-5 flex flex-col justify-between">
                 <span className="text-[10px] text-[var(--text-muted)] uppercase tracking-widest font-black mb-3">Modo Ocular/Facial</span>
                 <span className="text-sm text-white font-bold">{state?.tracking_mode || "Standard"}</span>
              </div>

              <div className="bg-black/40 border border-white/10 rounded-xl p-5 flex flex-col items-center justify-center text-center">
                 <span className="text-[10px] text-[var(--text-muted)] uppercase tracking-widest font-black mb-1">Expressões Guardadas</span>
                 <span className="text-3xl font-black text-white">{state?.expressions || 0}</span>
              </div>

              <div className="bg-black/40 border border-white/10 rounded-xl p-5 flex flex-col items-center justify-center text-center">
                 <span className="text-[10px] text-[var(--text-muted)] uppercase tracking-widest font-black mb-1">Hotkeys Mapeadas</span>
                 <span className="text-3xl font-black text-white">{state?.hotkeys || 0}</span>
              </div>
           </div>

           {/* LOG TERMINAL VTS */}
           <div className="mt-auto bg-black/60 border border-white/5 rounded-xl p-3 flex flex-col font-mono text-[10px] relative overflow-hidden">
             <div className="absolute left-0 top-0 bottom-0 w-1 bg-[var(--cyan-neon)]"></div>
             <span className="text-[var(--text-muted)] mb-1 pl-2">System.Log.VTS</span>
             <span className={`${state?.last_error && state.last_error !== "Nenhum erro" ? "text-red-400" : "text-green-400"} pl-2`}>
               {">"} {log}
             </span>
           </div>
        </div>

        {/* FOOTER ACTIONS */}
        <div className="md:col-span-3 flex justify-end gap-3 mt-4">
           <button 
             onClick={async () => {
                const HOST = window.location.hostname;
                await fetch(`http://${HOST}:8042/api/config/conexoes`, {
                   method: "POST",
                   headers: { "Content-Type": "application/json" },
                   body: JSON.stringify({ vts: true })
                });
             }}
             className="px-6 py-2.5 rounded-xl bg-white/5 border border-white/10 text-[var(--text-secondary)] text-sm font-bold hover:bg-white/10 transition-all"
           >
              Ligar Módulo
           </button>
           <button className="px-6 py-2.5 rounded-xl bg-[var(--cyan-dark)] border border-[var(--cyan-neon)] text-[var(--cyan-neon)] text-sm font-bold hover:bg-[var(--cyan-neon)] hover:text-black transition-all shadow-[0_0_15px_rgba(34,211,238,0.2)]">
              Tentar Reconectar
           </button>
        </div>

      </div>
    </div>
  );
}
