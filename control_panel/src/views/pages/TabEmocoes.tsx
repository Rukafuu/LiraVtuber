import { useEffect, useState } from "react";
import { ApiController } from "../../controllers/api";
import { EmotionState } from "../../models/types";
import { HeartPulse, BrainCircuit, Activity, Clock } from "lucide-react";

const EMOJI_MAP: Record<string, string> = {
  "HAPPY": "😄", "SAD": "😔", "ANGRY": "😡", "SHY": "😳",
  "SURPRISED": "😲", "SMUG": "😏", "NEUTRAL": "😐",
  "LOVE": "😍", "SCARED": "😨", "CONFUSED": "🤔"
};

export function TabEmocoes() {
  const [state, setState] = useState<EmotionState | null>(null);

  useEffect(() => {
    const ws = ApiController.connectEmotionsWebSocket((data) => {
      setState(data);
    });
    return () => ws.close();
  }, []);

  if (!state) {
    return (
      <div className="w-full h-full flex flex-col items-center justify-center gap-4">
        <div className="animate-ping h-8 w-8 rounded-full bg-[var(--purple-neon)] opacity-75"></div>
        <p className="text-[var(--text-muted)] font-mono text-xs uppercase tracking-widest">Aguardando sinais neurais...</p>
      </div>
    );
  }

  const getMoodColor = (mood: number) => {
    if (mood > 0.3) return "text-green-400";
    if (mood < -0.3) return "text-red-400";
    return "text-[var(--purple-neon)]";
  };

  const getMoodBarColor = (mood: number) => {
    if (mood > 0.3) return "bg-green-500 shadow-[0_0_15px_rgba(34,197,94,0.5)]";
    if (mood < -0.3) return "bg-red-500 shadow-[0_0_15px_rgba(239,68,68,0.5)]";
    return "bg-[var(--purple-neon)] shadow-[0_0_15px_rgba(168,85,247,0.5)]";
  };

  const getMoodLabel = (mood: number) => {
    if (mood > 0.6) return "Radiante";
    if (mood > 0.2) return "Feliz";
    if (mood > -0.2) return "Equilibrada";
    if (mood > -0.6) return "Melancólica";
    return "Hostil";
  };

  return (
    <div className="w-full h-full bg-[var(--bg-sidebar)] backdrop-blur-2xl border border-[var(--border-strong)] rounded-2xl p-8 overflow-y-auto custom-scrollbar shadow-2xl relative transition-all duration-500">
      {/* HEADER */}
      <div className="mb-8">
        <h2 className="flex items-center gap-3 text-3xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-pink-400 to-[var(--purple-neon)] mb-2 transition-all duration-500">
          <HeartPulse size={32} className="text-pink-400 drop-shadow-[0_0_10px_rgba(244,114,182,0.5)]" /> Mente da Lira
        </h2>
        <p className="text-sm text-[var(--text-muted)]">
          Análise em tempo real do processamento cognitivo e estado afetivo.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        
        {/* CARD: HUMOR ATUAL */}
        <div className="bg-[rgba(0,0,0,0.4)] backdrop-blur-md border border-[var(--border-strong)] hover:border-pink-500/50 rounded-2xl p-8 flex flex-col items-center justify-center shadow-lg relative overflow-hidden group transition-all hover:shadow-[0_0_30px_rgba(244,114,182,0.15)]">
          <div className="absolute top-[-50px] left-[-50px] w-40 h-40 bg-pink-500 rounded-full blur-[80px] opacity-10 pointer-events-none transition-all duration-1000 group-hover:opacity-30"></div>
          
          <span className="text-8xl mb-4 drop-shadow-[0_0_20px_rgba(255,255,255,0.2)] transform transition-transform group-hover:scale-110 duration-500 relative z-10">
             {EMOJI_MAP[state.current_emotion] || "😐"}
          </span>
          
          <h3 className={`text-2xl font-black uppercase tracking-tighter mb-1 relative z-10 ${getMoodColor(state.mood)} drop-shadow-[0_0_8px_currentColor]`}>
            {getMoodLabel(state.mood)}
          </h3>
          <p className="text-[10px] text-[var(--text-muted)] uppercase font-bold tracking-[0.3em] mb-8 relative z-10">Estado de Humor</p>
          
          <div className="w-full space-y-3 relative z-10">
             <div className="flex justify-between items-center text-[10px] font-black text-[var(--text-muted)] uppercase tracking-widest px-1">
                <span className="text-red-400/80">Irritada</span>
                <span className="text-[var(--text-primary)] font-mono bg-black/50 px-3 py-1 rounded-lg border border-white/5">Score: {state.mood.toFixed(2)}</span>
                <span className="text-green-400/80">Eufórica</span>
             </div>
             <div className="w-full h-4 bg-black/60 rounded-full border border-white/5 p-0.5 overflow-hidden shadow-inner">
                <div 
                  className={`h-full rounded-full transition-all duration-1000 ease-out ${getMoodBarColor(state.mood)}`}
                  style={{ width: `${(state.mood + 1) * 50}%` }}
                ></div>
             </div>
          </div>
        </div>

        {/* CARD: EMOÇÃO ATIVA */}
        <div className="bg-[rgba(0,0,0,0.4)] backdrop-blur-md border border-[var(--border-strong)] hover:border-[var(--cyan-neon)]/50 rounded-2xl p-8 flex flex-col items-center justify-center shadow-lg relative overflow-hidden group transition-all hover:shadow-[0_0_30px_rgba(34,211,238,0.15)]">
           <div className="absolute top-[-50px] right-[-50px] w-40 h-40 bg-[var(--cyan-neon)] rounded-full blur-[80px] opacity-10 pointer-events-none transition-all duration-1000 group-hover:opacity-30"></div>
           
           <div className="relative mb-6">
              <div className="absolute inset-0 rounded-full bg-[var(--cyan-neon)] blur-xl opacity-20 animate-pulse"></div>
              <div className="w-24 h-24 rounded-full bg-black/50 backdrop-blur-md border-4 border-[var(--cyan-neon)] flex items-center justify-center shadow-[0_0_25px_rgba(34,211,238,0.4)] relative z-10 transition-transform duration-500 group-hover:scale-105">
                 <Activity size={32} className="text-[var(--cyan-neon)] drop-shadow-[0_0_10px_rgba(34,211,238,0.8)]" />
              </div>
           </div>

           <h3 className="text-4xl font-mono font-black text-white mb-2 drop-shadow-[0_0_10px_rgba(255,255,255,0.5)] relative z-10 uppercase">
             {state.current_emotion}
           </h3>
           <div className="flex items-center gap-2 px-4 py-1.5 bg-black/60 rounded-full border border-[var(--cyan-neon)]/30 relative z-10 shadow-inner">
              <Clock size={12} className="text-[var(--cyan-neon)] animate-spin-slow" />
              <span className="text-[11px] font-bold text-[var(--text-secondary)] uppercase tracking-wider">Turno Ativo: <span className="text-white">{state.turno}</span></span>
           </div>
        </div>

        {/* CARD: PENSAMENTO INTERNO */}
        <div className="md:col-span-2 bg-[rgba(0,0,0,0.4)] backdrop-blur-md border border-[var(--border-strong)] rounded-2xl p-6 shadow-lg relative overflow-hidden group hover:border-[var(--purple-neon)]/50 transition-all hover:shadow-[0_0_30px_rgba(168,85,247,0.15)]">
          {/* Scanline Matrix Effect */}
          <div className="absolute top-0 left-0 w-full h-1 bg-[var(--purple-neon)] opacity-30 shadow-[0_0_15px_var(--purple-neon)] transform -translate-y-full animate-[fadeInSlideUp_4s_infinite]"></div>

          <div className="flex items-center gap-3 mb-4 relative z-10">
             <div className="w-10 h-10 rounded-xl bg-[var(--purple-dark)] flex items-center justify-center border border-[var(--purple-neon)] shadow-[0_0_15px_var(--purple-dark)]">
                <BrainCircuit size={20} className="text-[var(--purple-neon)]" />
             </div>
             <h3 className="font-bold text-white text-sm uppercase tracking-widest">Processamento Subjacente</h3>
          </div>
          
          <div className="bg-black/60 border border-[var(--purple-neon)]/30 rounded-xl p-5 font-mono text-sm text-[var(--text-secondary)] leading-relaxed shadow-inner italic relative z-10">
            <span className="text-[var(--purple-neon)] font-bold mr-2 drop-shadow-[0_0_5px_var(--purple-neon)]">LIRA_THOUGHT {">"}</span>
            <span className="text-gray-300">{state.last_thought || "Silêncio cognitivo no momento. Aguardando input."}</span>
          </div>
        </div>

        {/* CARD: HISTÓRICO DE FLUTUAÇÃO */}
        <div className="md:col-span-2 bg-[rgba(0,0,0,0.4)] backdrop-blur-md border border-[var(--border-strong)] rounded-2xl p-6 shadow-lg">
           <h3 className="font-bold text-white text-sm uppercase tracking-widest mb-6 px-2 flex items-center gap-2">
             <Activity size={16} className="text-[var(--text-muted)]" /> Histórico de Flutuação Afetiva
           </h3>
           
           <div className="grid grid-cols-1 gap-2 max-h-60 overflow-y-auto pr-2 custom-scrollbar">
              {state.history.slice().reverse().map((event, i) => (
                <div key={i} className="flex items-center justify-between bg-white/5 hover:bg-white/10 border border-white/5 rounded-xl px-4 py-3 transition-colors group">
                   <div className="flex items-center gap-4">
                      <span className="text-xl">{EMOJI_MAP[event.emotion] || "😐"}</span>
                      <div className="flex flex-col">
                         <span className="text-sm font-bold text-white tracking-wide">{event.emotion}</span>
                         <span className="text-[10px] text-[var(--text-muted)] font-mono">Turno {event.turno}</span>
                      </div>
                   </div>
                   <div className="text-right flex flex-col">
                      <span className="text-[11px] font-mono text-[var(--text-secondary)]">
                        {new Date(event.timestamp * 1000).toLocaleTimeString('pt-BR')}
                      </span>
                      <span className="text-[9px] font-bold text-[var(--purple-neon)] uppercase opacity-0 group-hover:opacity-100 transition-opacity">Neural Log</span>
                   </div>
                </div>
              ))}
           </div>
        </div>

      </div>
    </div>
  );
}
