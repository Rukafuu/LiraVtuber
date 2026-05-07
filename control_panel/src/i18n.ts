import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

const resources = {
  en: {
    translation: {
      sidebar: {
        monitor_geral: "Dashboard",
        cerebro: "Brain",
        memoria: "Memory",
        emocoes: "Lira's Mind",
        vtube: "VTube Studio",
        chat: "Control Chat",
        persona: "Persona",
        prompts: "Prompts",
        conexoes: "Connections",
        personalizacao: "Personalization",
        logs: "Logs",
        system_online: "SYSTEM ONLINE",
        stable_connection: "Stable Connection"
      },
      geral: {
        titulo: "General Monitor",
        subtitulo: "Real-time status of Lira's ecosystem and hardware",
        hardware_status: "Hardware Status",
        live: "Live",
        cpu: "CPU",
        processamento: "Processing",
        ram: "RAM",
        memoria: "Memory",
        intel_central: "Central Intelligence",
        llm_engine: "LLM Engine",
        modelo_core: "Core Model",
        system_log: "System Log",
        conexoes_modulos: "Connections & Modules",
        llm_principal: "Main LLM",
        voz_tts: "Voice (TTS)",
        ouvido_stt: "Hearing (STT)",
        visao_comp: "Computer Vision",
        vtube_studio: "VTube Studio",
        bot_discord: "Discord Bot",
        online: "Online",
        offline: "Offline",
        ws_fallback: "WebSocket unavailable, using fallback."
      },
      personalizacao: {
        titulo: "Personalization",
        subtitulo: "Change accent colors, visual theme and connect with Lira's identity.",
        cores_sistema: "System Colors",
        transparencia: "Background Transparency",
        cor_customizada: "Custom Color (HEX)",
        aplicar: "Apply",
        salvar_tema: "Save Theme",
        sucesso: "Theme applied successfully!"
      }
    }
  },
  pt: {
    translation: {
      sidebar: {
        monitor_geral: "Monitor Geral",
        cerebro: "Cérebro",
        memoria: "Memória",
        emocoes: "Mente da Lira",
        vtube: "VTube Studio",
        chat: "Chat do Controle",
        persona: "Persona",
        prompts: "Prompts",
        conexoes: "Conexões",
        personalizacao: "Personalização",
        logs: "Logs",
        system_online: "SYSTEM ONLINE",
        stable_connection: "Conexão Estável"
      },
      geral: {
        titulo: "Monitor Geral",
        subtitulo: "Status em tempo real do ecossistema e hardware da Lira",
        hardware_status: "Status de Hardware",
        live: "Live",
        cpu: "CPU",
        processamento: "Processamento",
        ram: "RAM",
        memoria: "Memória",
        intel_central: "Inteligência Central",
        llm_engine: "Motor LLM",
        modelo_core: "Modelo Core",
        system_log: "System Log",
        conexoes_modulos: "Conexões & Módulos",
        llm_principal: "LLM Principal",
        voz_tts: "Voz (TTS)",
        ouvido_stt: "Ouvido (STT)",
        visao_comp: "Visão Computacional",
        vtube_studio: "VTube Studio",
        bot_discord: "Bot Discord",
        online: "Online",
        offline: "Offline",
        ws_fallback: "WebSocket não disponível, usando fallback."
      },
      personalizacao: {
        titulo: "Personalização",
        subtitulo: "Altere as cores de acento, tema visual e conecte-se com a identidade da Lira.",
        cores_sistema: "Cores do Sistema",
        transparencia: "Transparência do Fundo",
        cor_customizada: "Cor Customizada (HEX)",
        aplicar: "Aplicar",
        salvar_tema: "Salvar Tema",
        sucesso: "Tema aplicado com sucesso!"
      }
    }
  }
};

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources,
    fallbackLng: 'en',
    keySeparator: '.',
    interpolation: {
      escapeValue: false
    }
  });

export default i18n;
