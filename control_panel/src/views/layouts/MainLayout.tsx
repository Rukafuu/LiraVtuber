import { useState } from "react";
import { useTranslation } from "react-i18next";

import { Sidebar } from "./Sidebar";
import { MobileBottomNav } from "./MobileBottomNav";
import { useIsMobile } from "../../hooks/useIsMobile";
import { MenuOption } from "../../models/types";

import {
  MonitorDot, BrainCircuit, Database, HeartPulse,
  MonitorPlay, MessageSquareText, UserCircle,
  FileCode2, Cable, Radio, Coins, Boxes, Paintbrush, ScrollText, ShieldAlert
} from "lucide-react";

import { TabGeral } from "../pages/TabGeral";
import { TabLLM } from "../pages/TabLLM";
import { TabPersonalizacao } from "../pages/TabPersonalizacao";
import { TabChat } from "../pages/TabChat";
import { TabConexoes } from "../pages/TabConexoes";
import { TabServicos } from "../pages/TabServicos";
import { TabMCP } from "../pages/TabMCP";
import { TabEmocoes } from "../pages/TabEmocoes";
import { TabVTube } from "../pages/TabVTube";
import { TabMemoria } from "../pages/TabMemoria";
import { TabLogs } from "../pages/TabLogs";
import { TabFinancas } from "../pages/TabFinancas";
import { TabWatchdog } from "../pages/TabWatchdog";
import { TabPersona } from "../pages/TabPersona";
import { TabPrompts } from "../pages/TabPrompts";
import { CyberBackground } from "../components/CyberBackground";

const menus: MenuOption[] = [
  { icon: <MonitorDot size={20} />, iconPath: "https://cdn.lordicon.com/xhebrhsj.json", label: "sidebar.monitor_geral", id: "geral" },
  { icon: <BrainCircuit size={20} />, iconPath: "https://cdn.lordicon.com/pvbjsfif.json", label: "sidebar.cerebro", id: "llm" },
  { icon: <Database size={20} />, iconPath: "https://cdn.lordicon.com/itykargr.json", label: "sidebar.memoria", id: "memoria" },
  { icon: <HeartPulse size={20} />, iconPath: "https://cdn.lordicon.com/ulnswmkk.json", label: "sidebar.emocoes", id: "emocoes" },
  { icon: <MonitorPlay size={20} />, iconPath: "https://cdn.lordicon.com/lupuorrc.json", label: "sidebar.vtube", id: "vtube" },
  { icon: <MessageSquareText size={20} />, iconPath: "https://cdn.lordicon.com/cnyeuzxc.json", label: "sidebar.chat", id: "chat" },
  { icon: <UserCircle size={20} />, iconPath: "https://cdn.lordicon.com/dxjqoygy.json", label: "sidebar.persona", id: "persona" },
  { icon: <FileCode2 size={20} />, iconPath: "https://cdn.lordicon.com/sygggnra.json", label: "sidebar.prompts", id: "prompts" },
  { icon: <Cable size={20} />, iconPath: "https://cdn.lordicon.com/zpxybbhl.json", label: "sidebar.conexoes", id: "conexoes" },
  { icon: <Radio size={20} />, iconPath: "https://cdn.lordicon.com/tltikfri.json", label: "sidebar.servicos", id: "servicos" },
  { icon: <ShieldAlert size={20} />, iconPath: "https://cdn.lordicon.com/dsinqpcb.json", label: "sidebar.watchdog", id: "watchdog" },
  { icon: <Coins size={20} />, iconPath: "https://cdn.lordicon.com/smauprql.json", label: "sidebar.financas", id: "financas" },
  { icon: <Boxes size={20} />, iconPath: "https://cdn.lordicon.com/sbnjyzil.json", label: "sidebar.mcp", id: "mcp" },
  { icon: <Paintbrush size={20} />, iconPath: "https://cdn.lordicon.com/adwosptt.json", label: "sidebar.personalizacao", id: "personalizacao" },
  { icon: <ScrollText size={20} />, iconPath: "https://cdn.lordicon.com/yxczfiyc.json", label: "sidebar.logs", id: "logs" },
];

const IMPLEMENTED_TABS = [
  "geral", "llm", "personalizacao", "chat", "conexoes", "servicos",
  "financas", "mcp", "emocoes", "vtube", "memoria", "logs",
  "watchdog", "persona", "prompts",
];

export function MainLayout() {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState("geral");
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const isMobile = useIsMobile();

  const isImplemented = IMPLEMENTED_TABS.includes(activeTab);

  const handleTabChange = (id: string) => {
    setActiveTab(id);
    setIsDrawerOpen(false);
  };

  return (
    <div
      className={`text-[var(--text-primary)] bg-transparent overflow-hidden ${
        isMobile
          ? "flex flex-col h-[100dvh] w-full"
          : "flex flex-row h-screen w-full"
      }`}
    >
      <CyberBackground />

      {/* Desktop: sidebar permanente */}
      {!isMobile && (
        <Sidebar menus={menus} activeTab={activeTab} onTabChange={handleTabChange} />
      )}

      {/* Mobile: drawer deslizante + overlay */}
      {isMobile && (
        <>
          {isDrawerOpen && (
            <div
              className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm"
              onClick={() => setIsDrawerOpen(false)}
              aria-hidden="true"
            />
          )}
          <Sidebar
            menus={menus}
            activeTab={activeTab}
            onTabChange={handleTabChange}
            isMobile={true}
            mobileOpen={isDrawerOpen}
            onMobileClose={() => setIsDrawerOpen(false)}
          />
        </>
      )}

      {/* Área de conteúdo principal */}
      <div
        className={`relative overflow-hidden ${
          isMobile ? "flex-1 min-h-0 p-3" : "flex-1 h-full p-6"
        }`}
      >
        {/* Luzes de fundo atmosféricas */}
        <div className="absolute top-[-10%] right-[-5%] w-[500px] h-[500px] bg-[var(--purple-neon)] rounded-full blur-[150px] opacity-10 pointer-events-none" />
        <div className="absolute bottom-[-10%] left-[20%] w-[400px] h-[400px] bg-[var(--cyan-neon)] rounded-full blur-[150px] opacity-10 pointer-events-none" />

        <div className="w-full h-full relative z-10 animate-fade-in">
          <div className={activeTab === "geral" ? "block w-full h-full" : "hidden"}><TabGeral /></div>
          <div className={activeTab === "llm" ? "block w-full h-full" : "hidden"}><TabLLM /></div>
          <div className={activeTab === "personalizacao" ? "block w-full h-full" : "hidden"}><TabPersonalizacao /></div>
          <div className={activeTab === "chat" ? "block w-full h-full" : "hidden"}><TabChat /></div>
          <div className={activeTab === "conexoes" ? "block w-full h-full" : "hidden"}><TabConexoes /></div>
          <div className={activeTab === "servicos" ? "block w-full h-full" : "hidden"}><TabServicos /></div>
          <div className={activeTab === "mcp" ? "block w-full h-full" : "hidden"}><TabMCP /></div>
          <div className={activeTab === "emocoes" ? "block w-full h-full" : "hidden"}><TabEmocoes /></div>
          <div className={activeTab === "vtube" ? "block w-full h-full" : "hidden"}><TabVTube /></div>
          <div className={activeTab === "memoria" ? "block w-full h-full" : "hidden"}><TabMemoria /></div>
          <div className={activeTab === "logs" ? "block w-full h-full" : "hidden"}><TabLogs /></div>
          <div className={activeTab === "financas" ? "block w-full h-full" : "hidden"}><TabFinancas /></div>
          <div className={activeTab === "watchdog" ? "block w-full h-full" : "hidden"}><TabWatchdog /></div>
          <div className={activeTab === "persona" ? "block w-full h-full" : "hidden"}><TabPersona /></div>
          <div className={activeTab === "prompts" ? "block w-full h-full" : "hidden"}><TabPrompts /></div>

          {!isImplemented && (
            <div className="w-full h-full bg-[rgba(15,15,20,0.5)] backdrop-blur-2xl border border-[var(--border-strong)] rounded-2xl p-8 overflow-y-auto">
              <h2 className="text-3xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-[var(--purple-neon)] to-[var(--cyan-neon)] mb-2">
                {t(menus.find((m) => m.id === activeTab)?.label || "")}
              </h2>
              <p className="text-[var(--text-secondary)]">(Work in Progress)</p>
            </div>
          )}
        </div>
      </div>

      {/* Mobile: bottom nav */}
      {isMobile && (
        <MobileBottomNav
          activeTab={activeTab}
          onTabChange={handleTabChange}
          onOpenMenu={() => setIsDrawerOpen(true)}
        />
      )}
    </div>
  );
}
