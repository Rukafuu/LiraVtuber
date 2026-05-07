import { useState, useEffect } from "react";
import { Paintbrush, Save, CheckCircle2, Palette } from "lucide-react";
import { useTranslation } from "react-i18next";

const PRESET_COLORS = [
  { name: "🌸 Rosa Floral", hex: "#f472b6" },
  { name: "💜 Roxo Neon", hex: "#a855f7" },
  { name: "💙 Azul Cyberpunk", hex: "#3b82f6" },
  { name: "💚 Verde Matrix", hex: "#4ade80" },
  { name: "🧡 Laranja Sunset", hex: "#fb923c" },
  { name: "❤️ Vermelho Rubi", hex: "#f43f5e" },
  { name: "✨ Dourado", hex: "#fbbf24" },
  { name: "🩵 Ciano", hex: "#22d3ee" },
];

export function TabPersonalizacao() {
  const { t } = useTranslation();
  const [accentColor, setAccentColor] = useState("#a855f7"); // Default Roxo Neon
  const [customHex, setCustomHex] = useState("#a855f7");
  const [opacity, setOpacity] = useState(1.0);

  // O ideal seria carregar isso do Backend na inicialização
  useEffect(() => {
    // Exemplo: ApiController.getThemeConfig().then(...)
    const savedColor = localStorage.getItem("lira_accent_color") || "#a855f7";
    const savedOpacity = parseFloat(localStorage.getItem("lira_bg_opacity") || "1.0");
    setAccentColor(savedColor);
    setCustomHex(savedColor);
    setOpacity(savedOpacity);
    applyColorToTheme(savedColor);
    applyOpacityToTheme(savedOpacity);
  }, []);

  const applyColorToTheme = (hex: string) => {
    // Aplica a cor de acento como CSS Variable no :root
    document.documentElement.style.setProperty('--purple-neon', hex);
    // Cria um brilho mais suave para a cor glow baseada na cor de acento
    document.documentElement.style.setProperty('--purple-glow', hex);
    document.documentElement.style.setProperty('--purple-dark', `${hex}20`); // Hex + alpha
  };

  const applyOpacityToTheme = (val: number) => {
    document.documentElement.style.setProperty('--bg-opacity', val.toString());
  };

  const handleColorSelect = (hex: string) => {
    setAccentColor(hex);
    setCustomHex(hex);
    applyColorToTheme(hex);
    localStorage.setItem("lira_accent_color", hex); // Salva na hora
  };

  const handleOpacityChange = (val: number) => {
    setOpacity(val);
    applyOpacityToTheme(val);
    localStorage.setItem("lira_bg_opacity", val.toString()); // Salva na hora
  };

  const handleSave = () => {
    // Salva explicitamente (e enviaria ao backend via Tauri)
    localStorage.setItem("lira_accent_color", accentColor);
    localStorage.setItem("lira_bg_opacity", opacity.toString());
    
    // Aqui chamariamos o ApiController.updateThemeConfig(accentColor)
    // ApiController.updateConfig({ GUI: { accent_color: accentColor } })

    const alertBox = document.getElementById("save-alert");
    if (alertBox) {
      alertBox.classList.remove("opacity-0", "translate-y-4");
      alertBox.classList.add("opacity-100", "translate-y-0");
      setTimeout(() => {
        alertBox.classList.remove("opacity-100", "translate-y-0");
        alertBox.classList.add("opacity-0", "translate-y-4");
      }, 3000);
    }
  };

  return (
    <div className="w-full h-full bg-[var(--bg-sidebar)] backdrop-blur-2xl border border-[var(--border-strong)] rounded-2xl p-8 overflow-y-auto custom-scrollbar shadow-2xl relative transition-all duration-300">
      {/* HEADER */}
      <div className="mb-8">
        <h2 className="flex items-center gap-3 text-3xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-[var(--purple-neon)] to-[var(--cyan-neon)] mb-2 transition-all duration-500">
          <Paintbrush size={32} className="text-[var(--purple-neon)]" /> {t('personalizacao.titulo')}
        </h2>
        <p className="text-sm text-[var(--text-muted)]">
          {t('personalizacao.subtitulo')}
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-[1.2fr_1fr] gap-6">
        
        {/* CARD: PALETA DE CORES */}
        <div className="bg-[rgba(0,0,0,0.4)] backdrop-blur-md border border-[var(--border-strong)] rounded-2xl p-6 shadow-lg relative overflow-hidden flex flex-col">
          <div className="absolute top-[-50px] right-[-50px] w-40 h-40 rounded-full blur-[80px] opacity-20 pointer-events-none transition-all duration-500" style={{ backgroundColor: accentColor }}></div>
          
          <h3 className="font-bold text-[var(--text-primary)] mb-6 text-lg flex items-center gap-2">
            <Palette size={20} style={{ color: accentColor }} className="transition-colors duration-500" /> {t('personalizacao.cores_sistema')}
          </h3>
          
          <div className="grid grid-cols-4 gap-4 mb-8">
            {PRESET_COLORS.map((preset) => (
              <button
                key={preset.name}
                onClick={() => handleColorSelect(preset.hex)}
                className="group flex flex-col items-center gap-2"
              >
                <div 
                  className={`w-14 h-14 rounded-full border-2 transition-all duration-300 shadow-lg ${accentColor === preset.hex ? 'scale-110 border-white shadow-[0_0_15px_currentColor]' : 'border-transparent hover:scale-105'}`}
                  style={{ backgroundColor: preset.hex, color: preset.hex }}
                ></div>
                <span className="text-[10px] text-center text-[var(--text-secondary)] font-medium opacity-80 group-hover:opacity-100">{preset.name.split(" ")[1]}</span>
              </button>
            ))}
          </div>

          <div className="bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.05)] rounded-xl p-4 mb-6">
            <span className="text-xs text-[var(--text-muted)] uppercase tracking-wider mb-2 block">{t('personalizacao.transparencia')}</span>
            <div className="flex items-center gap-4 mb-6">
              <input 
                type="range" min="0.1" max="1" step="0.05"
                className="w-full h-2 bg-[rgba(0,0,0,0.5)] rounded-lg appearance-none cursor-pointer"
                style={{ accentColor: accentColor }}
                value={opacity}
                onChange={(e) => handleOpacityChange(parseFloat(e.target.value))}
              />
              <span className="text-sm font-bold font-mono text-white bg-[rgba(255,255,255,0.1)] px-3 py-1 rounded-lg">
                {Math.round(opacity * 100)}%
              </span>
            </div>

            <span className="text-xs text-[var(--text-muted)] uppercase tracking-wider mb-2 block">{t('personalizacao.cor_customizada')}</span>
            <div className="flex gap-3">
              <input 
                type="text" 
                value={customHex}
                onChange={(e) => setCustomHex(e.target.value)}
                className="flex-1 bg-[rgba(0,0,0,0.5)] border border-[var(--border-strong)] text-[var(--text-primary)] rounded-lg p-2.5 outline-none font-mono text-sm focus:ring-2 transition-all"
                style={{ '--tw-ring-color': accentColor } as React.CSSProperties}
              />
              <button 
                onClick={() => handleColorSelect(customHex)}
                className="px-4 py-2.5 rounded-lg text-white font-bold text-sm transition-all hover:scale-105"
                style={{ backgroundColor: accentColor, boxShadow: `0 0 15px ${accentColor}40` }}
              >
                {t('personalizacao.aplicar')}
              </button>
            </div>
          </div>

          <div className="mt-auto pt-4 border-t border-[var(--border-strong)] flex items-center justify-between">
            <div 
              className="px-6 py-3 rounded-xl font-bold font-mono text-white transition-all duration-500 shadow-inner"
              style={{ backgroundColor: accentColor }}
            >
              LIRA_OS_ACTIVE
            </div>

            <button 
              onClick={handleSave}
              className="flex items-center gap-2 bg-[rgba(0,0,0,0.5)] border border-[rgba(255,255,255,0.1)] hover:bg-[rgba(255,255,255,0.05)] text-white px-6 py-3 rounded-xl font-bold text-sm transition-all hover:scale-105"
            >
              <Save size={18} /> {t('personalizacao.salvar_tema')}
            </button>
          </div>
        </div>

        {/* CARD: FOTO / IDENTIDADE LIRA */}
        <div className="bg-[rgba(0,0,0,0.4)] backdrop-blur-md border border-[var(--border-strong)] rounded-2xl overflow-hidden shadow-lg relative flex flex-col items-center group">
          {/* Fundo dinâmico baseado na cor de acento */}
          <div className="absolute inset-0 opacity-20 transition-all duration-1000 group-hover:opacity-40" style={{ background: `linear-gradient(to bottom, transparent, ${accentColor})` }}></div>
          
          {/* Imagem da Lira do disco local */}
          <div className="w-full h-[350px] flex items-center justify-center relative z-10 overflow-hidden">
            <div className="absolute inset-0 bg-[url('/banner_lira.png')] bg-cover bg-center bg-no-repeat opacity-40 mix-blend-overlay transition-transform duration-1000 group-hover:scale-110"></div>
            
            <div className="w-48 h-48 rounded-full border-4 border-white/20 overflow-hidden shadow-[0_0_30px_rgba(0,0,0,0.8)] flex flex-col items-center justify-center transition-transform duration-500 group-hover:scale-105 group-hover:border-white/50 relative z-20">
              <img src="/logo_lira.png" alt="Lira Identidade" className="w-full h-full object-cover" />
            </div>
          </div>

          <div className="relative z-10 w-full p-6 text-center bg-gradient-to-t from-[rgba(10,10,15,1)] to-transparent mt-[-60px] pt-10 flex-1 flex flex-col justify-end">
            <h2 className="text-3xl font-mono font-extrabold tracking-[0.3em] mb-1 transition-colors duration-500" style={{ color: accentColor }}>L I R A</h2>
            <p className="text-sm text-[var(--text-secondary)] tracking-widest uppercase mb-4">Amarinth Lira</p>
            
            <div className="inline-flex items-center gap-2 bg-[rgba(255,255,255,0.05)] border border-[rgba(255,255,255,0.1)] rounded-full px-4 py-1.5 mx-auto">
              <span className="w-2 h-2 rounded-full animate-pulse" style={{ backgroundColor: accentColor }}></span>
              <span className="text-xs font-mono text-[var(--text-muted)]">NEXUS CONNECTED • v1.0</span>
            </div>
          </div>
        </div>

      </div>

      {/* Alerta de Sucesso Float */}
      <div 
        id="save-alert"
        className="fixed bottom-10 left-1/2 -translate-x-1/2 bg-green-500/20 border border-green-500/50 text-green-400 px-6 py-3 rounded-full font-bold shadow-[0_0_20px_rgba(34,197,94,0.3)] backdrop-blur-md opacity-0 translate-y-4 transition-all duration-300 z-50 flex items-center gap-2 pointer-events-none"
      >
        <CheckCircle2 size={20} /> {t('personalizacao.sucesso')}
      </div>
    </div>
  );
}
