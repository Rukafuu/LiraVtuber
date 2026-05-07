import { MenuOption } from "../../models/types";
import { useTranslation } from "react-i18next";
import { Globe } from "lucide-react";

interface SidebarProps {
  menus: MenuOption[];
  activeTab: string;
  onTabChange: (id: string) => void;
}

export function Sidebar({ menus, activeTab, onTabChange }: SidebarProps) {
  const { t, i18n } = useTranslation();
  
  const toggleLanguage = () => {
    i18n.changeLanguage(i18n.language.startsWith('pt') ? 'en' : 'pt');
  };

  return (
    <div className="w-[240px] h-full flex flex-col bg-[var(--bg-sidebar)] border-r border-[var(--border-strong)] shrink-0 backdrop-blur-xl relative overflow-hidden z-50 shadow-[5px_0_15px_rgba(0,0,0,0.5)]">
      
      {/* Luz de fundo do Menu */}
      <div className="absolute top-0 left-0 w-full h-32 bg-gradient-to-b from-[var(--purple-dark)] to-transparent opacity-50 pointer-events-none"></div>

      {/* Profile / Header */}
      <div className="flex flex-col items-center pt-[30px] pb-[20px] relative z-10">
        <div className="w-[80px] h-[80px] rounded-full bg-[var(--bg-darkest)] flex items-center justify-center mb-3 shadow-[0_0_20px_var(--purple-dark)] glow-border border border-[var(--purple-neon)] transition-transform hover:scale-105 cursor-pointer overflow-hidden group">
          <img src="/lira_perfil.png" alt="Lira Profile" className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-110" />
        </div>
        <h1 className="font-mono text-xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-[var(--cyan-neon)] to-[var(--purple-neon)] m-0 tracking-wider">LIRA OS</h1>
        <p className="text-xs text-[var(--text-secondary)] mt-1 opacity-70 font-mono tracking-widest">NEXUS v2.0</p>
      </div>

      {/* Separator com Gradiente */}
      <div className="h-px bg-gradient-to-r from-transparent via-[var(--purple-neon)] to-transparent mx-[20px] mb-4 opacity-50" />

      {/* Navigation */}
      <div className="flex-1 overflow-y-auto py-2 px-4 flex flex-col gap-1.5 custom-scrollbar relative z-10">
        {menus.map((menu) => {
          const isActive = activeTab === menu.id;
          return (
            <button
              key={menu.id}
              onClick={() => onTabChange(menu.id)}
              className={`
                group flex items-center gap-3 px-4 py-3 rounded-xl text-sm text-left transition-all duration-300 relative overflow-hidden
                ${isActive 
                  ? "bg-[rgba(168,85,247,0.15)] text-white font-bold shadow-[inset_0_0_10px_rgba(168,85,247,0.3)] border border-[rgba(168,85,247,0.3)]" 
                  : "text-[var(--text-secondary)] hover:bg-[rgba(255,255,255,0.05)] hover:text-white border border-transparent"
                }
              `}
            >
              {/* Efeito Glow no Hover para inativos */}
              {!isActive && (
                <div className="absolute inset-0 bg-gradient-to-r from-[rgba(168,85,247,0.2)] to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
              )}
              
              {/* Barra lateral indicadora */}
              {isActive && (
                <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1.5 h-1/2 bg-[var(--cyan-neon)] rounded-r-full shadow-[0_0_10px_var(--cyan-neon)]"></div>
              )}

              <span className={`text-lg transition-transform duration-300 ${isActive ? "scale-110 drop-shadow-[0_0_8px_rgba(255,255,255,0.8)]" : "group-hover:scale-110"}`}>
                {menu.icon}
              </span>
              <span className="relative z-10 tracking-wide">{t(menu.label)}</span>
            </button>
          );
        })}
      </div>

      {/* Status na Base com Efeito Vidro e Language Toggle */}
      <div className="mt-auto p-4 relative z-10 flex flex-col gap-3">
        
        {/* Toggle de Idioma */}
        <button 
          onClick={toggleLanguage}
          className="flex items-center justify-between px-4 py-2 bg-[rgba(255,255,255,0.05)] border border-[rgba(255,255,255,0.1)] rounded-lg hover:bg-[rgba(255,255,255,0.1)] transition-colors text-xs text-[var(--text-secondary)] hover:text-white"
        >
          <div className="flex items-center gap-2">
            <Globe size={14} />
            <span>Language: </span>
          </div>
          <span className="font-bold text-[var(--purple-neon)] uppercase">{i18n.language.startsWith('pt') ? 'PT-BR' : 'EN-US'}</span>
        </button>

        <div className="bg-[rgba(0,0,0,0.3)] border border-[rgba(255,255,255,0.05)] rounded-xl p-3 flex items-center gap-3 backdrop-blur-md">
          <div className="relative flex items-center justify-center">
            <span className="absolute w-3 h-3 bg-green-500 rounded-full animate-ping opacity-75"></span>
            <span className="relative w-2 h-2 bg-green-500 rounded-full"></span>
          </div>
          <div className="flex flex-col">
            <span className="text-[10px] font-bold text-green-400 uppercase tracking-widest leading-none mb-1">{t('sidebar.system_online')}</span>
            <span className="text-[11px] text-[var(--text-muted)] font-mono leading-none">{t('sidebar.stable_connection')}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
