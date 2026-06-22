import { useEffect, useState } from "react";
import { MenuOption } from "../../models/types";
import { useTranslation } from "react-i18next";
import { ChevronLeft, ChevronRight, Globe } from "lucide-react";
import { LordIcon } from "../components/LordIcon";

const SIDEBAR_COLLAPSED_KEY = "lira_sidebar_collapsed";

interface SidebarProps {
  menus: MenuOption[];
  activeTab: string;
  onTabChange: (id: string) => void;
  mobileOpen?: boolean;
  isMobile?: boolean;
  onMobileClose?: () => void;
}

export function Sidebar({
  menus,
  activeTab,
  onTabChange,
  mobileOpen = false,
  isMobile = false,
  onMobileClose,
}: SidebarProps) {
  const { t, i18n } = useTranslation();
  const [collapsed, setCollapsed] = useState(
    () => localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === "1",
  );

  useEffect(() => {
    localStorage.setItem(SIDEBAR_COLLAPSED_KEY, collapsed ? "1" : "0");
  }, [collapsed]);

  const toggleLanguage = () => {
    i18n.changeLanguage(i18n.language.startsWith("pt") ? "en" : "pt");
  };

  const langLabel = i18n.language.startsWith("pt") ? "PT-BR" : "EN-US";

  const handleTab = (id: string) => {
    onTabChange(id);
    if (isMobile) onMobileClose?.();
  };

  const drawerExpanded = isMobile ? true : !collapsed;
  const widthClass = isMobile
    ? "w-[min(280px,88vw)]"
    : collapsed
      ? "w-[72px]"
      : "w-[240px]";

  return (
    <div
      className={`
        h-full flex flex-col bg-[var(--bg-sidebar)] border-r border-[var(--border-strong)]
        shrink-0 backdrop-blur-xl overflow-hidden shadow-[5px_0_15px_rgba(0,0,0,0.5)]
        transition-[width,transform] duration-300 ease-in-out
        ${widthClass}
        ${
          isMobile
            ? `fixed top-0 left-0 z-50 h-[100dvh] pt-[env(safe-area-inset-top)] ${
                mobileOpen ? "translate-x-0" : "-translate-x-full pointer-events-none"
              }`
            : "relative z-50"
        }
      `}
    >
      <div className="absolute top-0 left-0 w-full h-32 bg-gradient-to-b from-[var(--purple-dark)] to-transparent opacity-50 pointer-events-none" />

      {!isMobile ? (
        <button
          type="button"
          onClick={() => setCollapsed((v) => !v)}
          title={collapsed ? t("sidebar.expand") : t("sidebar.collapse")}
          aria-label={collapsed ? t("sidebar.expand") : t("sidebar.collapse")}
          className={`absolute top-4 z-20 p-1.5 rounded-lg border border-white/10 bg-black/30 text-[var(--text-secondary)] hover:text-white hover:bg-white/10 transition-all duration-300 ${
            collapsed ? "right-2" : "right-3"
          }`}
        >
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      ) : null}

      <div
        className={`flex flex-col items-center relative z-10 transition-all duration-300 ${
          drawerExpanded ? "pt-[30px] pb-[20px]" : "pt-14 pb-3"
        }`}
      >
        <div
          className={`rounded-full bg-[var(--bg-darkest)] flex items-center justify-center shadow-[0_0_20px_var(--purple-dark)] glow-border border border-[var(--purple-neon)] transition-all duration-300 hover:scale-105 cursor-pointer overflow-hidden group ${
            drawerExpanded ? "w-[80px] h-[80px] mb-3" : "w-10 h-10 mb-0"
          }`}
        >
          <img
            src="/lira_perfil.png"
            alt="Lira Profile"
            className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-110"
          />
        </div>
        <div
          className={`flex flex-col items-center overflow-hidden transition-all duration-300 ${
            drawerExpanded ? "max-h-20 opacity-100" : "max-h-0 opacity-0"
          }`}
        >
          <h1 className="font-mono text-xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-[var(--cyan-neon)] to-[var(--purple-neon)] m-0 tracking-wider whitespace-nowrap">
            LIRA OS
          </h1>
          <p className="text-xs text-[var(--text-secondary)] mt-1 opacity-70 font-mono tracking-widest whitespace-nowrap">
            NEXUS v2.0
          </p>
        </div>
      </div>

      <div
        className={`h-px bg-gradient-to-r from-transparent via-[var(--purple-neon)] to-transparent opacity-50 transition-all duration-300 ${
          drawerExpanded ? "mx-[20px] mb-4" : "mx-3 mb-2"
        }`}
      />

      <div
        className={`flex-1 overflow-y-auto overflow-x-hidden py-2 flex flex-col gap-1.5 custom-scrollbar relative z-10 transition-all duration-300 ${
          drawerExpanded ? "px-4" : "px-2"
        }`}
      >
        {menus.map((menu) => {
          const isActive = activeTab === menu.id;
          const label = t(menu.label);
          return (
            <button
              key={menu.id}
              type="button"
              onClick={() => handleTab(menu.id)}
              title={drawerExpanded ? undefined : label}
              aria-label={label}
              className={`
                group flex items-center rounded-xl text-sm text-left transition-all duration-300 relative overflow-hidden
                ${drawerExpanded ? "gap-3 px-4 py-3" : "justify-center px-0 py-3"}
                ${
                  isActive
                    ? "bg-[rgba(168,85,247,0.15)] text-white font-bold shadow-[inset_0_0_10px_rgba(168,85,247,0.3)] border border-[rgba(168,85,247,0.3)]"
                    : "text-[var(--text-secondary)] hover:bg-[rgba(255,255,255,0.05)] hover:text-white border border-transparent"
                }
              `}
            >
              {!isActive && (
                <div className="absolute inset-0 bg-gradient-to-r from-[rgba(168,85,247,0.2)] to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
              )}

              {isActive && (
                <div
                  className={`absolute top-1/2 -translate-y-1/2 h-1/2 bg-[var(--cyan-neon)] rounded-r-full shadow-[0_0_10px_var(--cyan-neon)] ${
                    drawerExpanded ? "left-0 w-1.5" : "left-0 w-1"
                  }`}
                />
              )}

              <span
                className={`text-lg transition-transform duration-300 shrink-0 ${
                  isActive ? "scale-110" : "group-hover:scale-110"
                }`}
              >
                {menu.iconPath ? (
                  <LordIcon src={menu.iconPath} isActive={isActive} size={22} />
                ) : (
                  menu.icon
                )}
              </span>
              <span
                className={`relative z-10 tracking-wide whitespace-nowrap transition-all duration-300 ${
                  drawerExpanded ? "w-auto opacity-100" : "w-0 opacity-0 overflow-hidden"
                }`}
              >
                {label}
              </span>
            </button>
          );
        })}
      </div>

      <div
        className={`mt-auto relative z-10 flex flex-col gap-3 transition-all duration-300 ${
          drawerExpanded ? "p-4" : "p-2"
        }`}
      >
        <button
          type="button"
          onClick={toggleLanguage}
          title={drawerExpanded ? undefined : `Language: ${langLabel}`}
          className={`bg-[rgba(255,255,255,0.05)] border border-[rgba(255,255,255,0.1)] rounded-lg hover:bg-[rgba(255,255,255,0.1)] transition-all duration-300 text-xs text-[var(--text-secondary)] hover:text-white ${
            drawerExpanded
              ? "flex items-center justify-between px-4 py-2"
              : "flex items-center justify-center p-2.5"
          }`}
        >
          <div className={`flex items-center gap-2 ${collapsed ? "" : ""}`}>
            <Globe size={14} className="shrink-0" />
            <span
              className={`transition-all duration-300 whitespace-nowrap ${
                drawerExpanded ? "w-auto opacity-100" : "w-0 opacity-0 overflow-hidden"
              }`}
            >
              Language:
            </span>
          </div>
          <span
            className={`font-bold text-[var(--purple-neon)] uppercase transition-all duration-300 ${
              drawerExpanded ? "w-auto opacity-100" : "w-0 opacity-0 overflow-hidden"
            }`}
          >
            {langLabel}
          </span>
        </button>

        <div
          className={`bg-[rgba(0,0,0,0.3)] border border-[rgba(255,255,255,0.05)] rounded-xl backdrop-blur-md transition-all duration-300 ${
            drawerExpanded ? "p-3 flex items-center gap-3" : "p-2 flex items-center justify-center"
          }`}
          title={drawerExpanded ? undefined : t("sidebar.system_online")}
        >
          <div className="relative flex items-center justify-center shrink-0">
            <span className="absolute w-3 h-3 bg-green-500 rounded-full animate-ping opacity-75" />
            <span className="relative w-2 h-2 bg-green-500 rounded-full" />
          </div>
          <div
            className={`flex flex-col overflow-hidden transition-all duration-300 ${
              drawerExpanded ? "w-auto opacity-100" : "w-0 opacity-0"
            }`}
          >
            <span className="text-[10px] font-bold text-green-400 uppercase tracking-widest leading-none mb-1 whitespace-nowrap">
              {t("sidebar.system_online")}
            </span>
            <span className="text-[11px] text-[var(--text-muted)] font-mono leading-none whitespace-nowrap">
              {t("sidebar.stable_connection")}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}