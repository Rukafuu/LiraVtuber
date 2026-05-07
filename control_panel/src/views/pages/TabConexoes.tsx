import { useEffect, useState } from "react";
import { ApiController } from "../../controllers/api";
import { ConnectionsConfig } from "../../models/types";

const HOTKEYS = [
  "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12",
  "CapsLock", "ScrollLock", "Insert", "Home", "End", "PageUp", "PageDown",
];

import { PlugZap, Mic, Eye, Video, MessageSquareText, ShieldAlert, Keyboard } from "lucide-react";
import { useAudioUI } from "../../hooks/useAudioUI";

export function TabConexoes() {
  const [config, setConfig] = useState<ConnectionsConfig | null>(null);
  const audio = useAudioUI();

  useEffect(() => {
    ApiController.getConnectionsConfig()
      .then(setConfig)
      .catch(console.error);
  }, []);

  const updateConfig = (newConfig: ConnectionsConfig) => {
    setConfig(newConfig);
    ApiController.updateConnectionsConfig(newConfig);
  };

  const toggleField = (field: keyof ConnectionsConfig) => {
    if (!config) return;
    const newState = !config[field];
    if (newState) audio.playToggleOn();
    else audio.playToggleOff();
    updateConfig({ ...config, [field]: newState });
  };

  const updateKey = (field: "pttKey" | "stopKey", value: string) => {
    if (!config) return;
    updateConfig({ ...config, [field]: value });
  };

  if (!config) {
    return <div className="w-full h-full flex items-center justify-center"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--cyan-neon)]"></div></div>;
  }

  const renderModuleCard = (
    id: keyof ConnectionsConfig, 
    title: string, 
    description: string, 
    icon: React.ReactNode, 
    colorVarName: string, // Ex: "purple"
    hasHotkey?: "pttKey" | "stopKey"
  ) => {
    const isActive = config[id] as boolean;
    const neonColor = `var(--${colorVarName}-neon)`;

    return (
      <div 
        className={`relative overflow-hidden bg-[rgba(0,0,0,0.4)] backdrop-blur-md border rounded-2xl p-6 transition-all duration-500 hover:shadow-[0_0_20px_rgba(255,255,255,0.05)] group flex flex-col h-full`}
        style={{
          borderColor: isActive ? neonColor : 'var(--border-strong)',
          boxShadow: isActive ? `0 0 30px ${neonColor}20` : 'none'
        }}
      >
        {/* Glow de fundo ativo */}
        {isActive && (
          <div 
            className="absolute top-[-50px] right-[-50px] w-40 h-40 rounded-full blur-[60px] opacity-20 pointer-events-none transition-all duration-1000"
            style={{ backgroundColor: neonColor }}
          ></div>
        )}

        <div className="flex items-start justify-between gap-4 relative z-10 mb-4">
          <div className="flex items-center gap-4">
            <div 
              className={`w-14 h-14 rounded-xl flex items-center justify-center text-3xl transition-all duration-500 ${!isActive ? 'bg-[rgba(255,255,255,0.02)] text-[var(--text-muted)]' : ''}`}
              style={isActive ? { backgroundColor: `${neonColor}20`, color: neonColor, boxShadow: `0 0 20px ${neonColor}30`, transform: 'scale(1.05)' } : {}}
            >
              {icon}
            </div>
            <div className="flex flex-col">
              <h3 className={`font-black text-xl tracking-wide uppercase transition-colors duration-500 ${isActive ? 'text-white' : 'text-[var(--text-secondary)]'}`}>
                {title}
              </h3>
              <div className="flex items-center gap-2 mt-1">
                <span className={`w-2 h-2 rounded-full ${isActive ? 'animate-pulse' : 'opacity-50'}`} style={isActive ? { backgroundColor: neonColor, boxShadow: `0 0 10px ${neonColor}` } : { backgroundColor: 'var(--text-muted)' }}></span>
                <span className={`text-[10px] font-bold font-mono tracking-widest uppercase ${isActive ? '' : 'text-[var(--text-muted)]'}`} style={isActive ? { color: neonColor } : {}}>
                  {isActive ? 'Módulo Activo' : 'Offline'}
                </span>
              </div>
            </div>
          </div>

          <div className="shrink-0">
            {/* Toggle Switch */}
            <label 
              className="relative inline-flex items-center cursor-pointer group/switch"
              onMouseEnter={() => audio.playHover()}
            >
              <input 
                type="checkbox" 
                className="sr-only peer" 
                checked={isActive}
                onChange={() => toggleField(id)}
              />
              <div 
                className={`w-16 h-8 bg-black/60 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[4px] after:left-[4px] after:bg-[var(--text-muted)] peer-checked:after:bg-white after:border-gray-300 after:rounded-full after:h-6 after:w-6 after:transition-all duration-300 ${!isActive ? 'border border-[var(--border-strong)]' : 'border-transparent'}`}
                style={isActive ? { backgroundColor: `${neonColor}80`, boxShadow: `inset 0 0 15px ${neonColor}` } : {}}
              ></div>
            </label>
          </div>
        </div>
        
        <p className="text-sm text-[var(--text-muted)] leading-relaxed relative z-10 flex-1">
          {description}
        </p>

        {/* Selector de Hotkey */}
        {hasHotkey && (
          <div className={`mt-5 pt-4 border-t border-white/5 flex items-center justify-between gap-2 relative z-10 transition-all duration-500 ${isActive ? 'opacity-100' : 'opacity-30 pointer-events-none'}`}>
            <span className="text-xs font-bold uppercase tracking-widest text-[var(--text-secondary)]">Atalho (Hotkey)</span>
            <select
              value={config[hasHotkey]}
              onChange={(e) => updateKey(hasHotkey, e.target.value)}
              disabled={!isActive}
              className={`bg-black/60 rounded-xl px-4 py-2 outline-none font-mono text-sm font-bold cursor-pointer disabled:cursor-not-allowed transition-all border shadow-inner`}
              style={isActive ? { borderColor: `${neonColor}50`, color: neonColor } : { borderColor: 'var(--border-strong)', color: 'var(--text-secondary)' }}
            >
              {HOTKEYS.map(k => <option key={k} value={k} className="bg-gray-900">{k}</option>)}
            </select>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="w-full h-full bg-[var(--bg-sidebar)] backdrop-blur-2xl border border-[var(--border-strong)] rounded-2xl p-8 overflow-y-auto custom-scrollbar shadow-2xl relative transition-all duration-500">
      {/* HEADER */}
      <div className="mb-8">
        <h2 className="flex items-center gap-3 text-3xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-[var(--cyan-neon)] mb-2 transition-all duration-500">
          <PlugZap size={32} className="text-[var(--cyan-neon)] drop-shadow-[0_0_10px_var(--cyan-neon)]" /> Conexões & Módulos
        </h2>
        <p className="text-sm text-[var(--text-muted)]">
          Controle central dos sentidos e integrações da Lira. As alterações são aplicadas instantaneamente ao Core.
        </p>
      </div>

      {/* LISTA DE MÓDULOS EM GRID (Para melhor aproveitamento visual) */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5 pb-10">
        {renderModuleCard(
          "tts", 
          "Síntese de Voz (TTS)", 
          "Habilita a fala da Lira para responder com áudio gerado.", 
          <Mic size={24} />, 
          "blue"
        )}

        {renderModuleCard(
          "stt", 
          "Reconhecimento de Voz (STT)", 
          "Ouvido da Lira via Whisper. Permite que ela entenda o que você diz pelo microfone.", 
          <Mic size={24} />, 
          "purple"
        )}

        {renderModuleCard(
          "ptt", 
          "Pressione para Falar (PTT)", 
          "Ativa um Hotkey Global. Enquanto a tecla estiver pressionada, o microfone escutará sua voz de qualquer lugar do Windows.", 
          <Keyboard size={24} />, 
          "cyan",
          "pttKey"
        )}

        {renderModuleCard(
          "stopHotkey", 
          "Parar Resposta (Hotkey)", 
          "Hotkey global de pânico para interromper imediatamente a fala (TTS), geração de texto ou mídia atual.", 
          <ShieldAlert size={24} />, 
          "red",
          "stopKey"
        )}

        {renderModuleCard(
          "visao", 
          "Visão (Sob Demanda)", 
          "Permite que a Lira enxergue a tela do seu PC ou imagens antes de responder. (Pode consumir mais tokens).", 
          <Eye size={24} />, 
          "purple"
        )}

        {renderModuleCard(
          "vts", 
          "VTube Studio", 
          "Integração nativa para controle de expressões, lábios (LipSync) e avatar 2D/3D da Lira no VTube Studio.", 
          <Video size={24} />, 
          "cyan"
        )}

        {renderModuleCard(
          "discord", 
          "Bot do Discord", 
          "Ativa a conexão com o Discord. A Lira responderá e interajirá diretamente nos servidores configurados.", 
          <MessageSquareText size={24} />, 
          "blue"
        )}
      </div>

    </div>
  );
}
