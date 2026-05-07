import { useState } from "react";
// Will be translated in the sidebar anyway, but let's use a translation hook here for the fallback title
import { useTranslation } from "react-i18next";

import { Sidebar } from "./Sidebar";
import { MenuOption } from "../../models/types";

// Importando Ícones do Lucide
import { 
  MonitorDot, BrainCircuit, Database, HeartPulse,
  MonitorPlay, MessageSquareText, UserCircle,
  FileCode2, Cable, Paintbrush, ScrollText
} from "lucide-react";

// Importando as Páginas (Views)
import { TabGeral } from "../pages/TabGeral";
import { TabLLM } from "../pages/TabLLM";
import { TabPersonalizacao } from "../pages/TabPersonalizacao";
import { TabChat } from "../pages/TabChat";
import { TabConexoes } from "../pages/TabConexoes";
import { TabEmocoes } from "../pages/TabEmocoes";
import { TabVTube } from "../pages/TabVTube";
import { TabMemoria } from "../pages/TabMemoria";
import { TabLogs } from "../pages/TabLogs";
import { CyberBackground } from "../components/CyberBackground";

const menus: MenuOption[] = [
  { icon: <MonitorDot size={20} />, label: "sidebar.monitor_geral", id: "geral" },
  { icon: <BrainCircuit size={20} />, label: "sidebar.cerebro", id: "llm" },
  { icon: <Database size={20} />, label: "sidebar.memoria", id: "memoria" },
  { icon: <HeartPulse size={20} />, label: "sidebar.emocoes", id: "emocoes" },
  { icon: <MonitorPlay size={20} />, label: "sidebar.vtube", id: "vtube" },
  { icon: <MessageSquareText size={20} />, label: "sidebar.chat", id: "chat" },
  { icon: <UserCircle size={20} />, label: "sidebar.persona", id: "persona" },
  { icon: <FileCode2 size={20} />, label: "sidebar.prompts", id: "prompts" },
  { icon: <Cable size={20} />, label: "sidebar.conexoes", id: "conexoes" },
  { icon: <Paintbrush size={20} />, label: "sidebar.personalizacao", id: "personalizacao" },
  { icon: <ScrollText size={20} />, label: "sidebar.logs", id: "logs" },
];

export function MainLayout() {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState("geral");

  const isImplemented = ["geral", "llm", "personalizacao", "chat", "conexoes", "emocoes", "vtube", "memoria", "logs"].includes(activeTab);

  return (
    <div className="flex h-screen w-full text-[var(--text-primary)] bg-transparent">
      <CyberBackground />
      <Sidebar menus={menus} activeTab={activeTab} onTabChange={setActiveTab} />
      
      {/* Main Content com Efeito de Vidro */}
      <div className="flex-1 h-full p-6 overflow-hidden relative">
        {/* Luzes de fundo atmosféricas na área principal */}
        <div className="absolute top-[-10%] right-[-5%] w-[500px] h-[500px] bg-[var(--purple-neon)] rounded-full blur-[150px] opacity-10 pointer-events-none"></div>
        <div className="absolute bottom-[-10%] left-[20%] w-[400px] h-[400px] bg-[var(--cyan-neon)] rounded-full blur-[150px] opacity-10 pointer-events-none"></div>
        
        <div className="w-full h-full relative z-10 animate-fade-in">
          
          <div className={activeTab === "geral" ? "block w-full h-full" : "hidden"}>
            <TabGeral />
          </div>
          
          <div className={activeTab === "llm" ? "block w-full h-full" : "hidden"}>
            <TabLLM />
          </div>
          
          <div className={activeTab === "personalizacao" ? "block w-full h-full" : "hidden"}>
            <TabPersonalizacao />
          </div>

          <div className={activeTab === "chat" ? "block w-full h-full" : "hidden"}>
            <TabChat />
          </div>

          <div className={activeTab === "conexoes" ? "block w-full h-full" : "hidden"}>
            <TabConexoes />
          </div>

          <div className={activeTab === "emocoes" ? "block w-full h-full" : "hidden"}>
            <TabEmocoes />
          </div>

          <div className={activeTab === "vtube" ? "block w-full h-full" : "hidden"}>
            <TabVTube />
          </div>

          <div className={activeTab === "memoria" ? "block w-full h-full" : "hidden"}>
            <TabMemoria />
          </div>

          <div className={activeTab === "logs" ? "block w-full h-full" : "hidden"}>
            <TabLogs />
          </div>

          {!isImplemented && (
            <div className="w-full h-full bg-[rgba(15,15,20,0.5)] backdrop-blur-2xl border border-[var(--border-strong)] rounded-2xl p-8 overflow-y-auto">
              <h2 className="text-3xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-[var(--purple-neon)] to-[var(--cyan-neon)] mb-2">
                {t(menus.find(m => m.id === activeTab)?.label || "")}
              </h2>
              <p className="text-[var(--text-secondary)]">
                (Work in Progress - MVC Estruturado)
              </p>
            </div>
          )}

        </div>
      </div>
    </div>
  );
}
