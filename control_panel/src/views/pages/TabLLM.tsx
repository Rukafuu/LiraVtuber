import { useEffect, useState } from "react";
import { ApiController } from "../../controllers/api";
import { LlmConfig } from "../../models/types";
import { 
  LLM_PROVIDERS, 
  TTS_PROVIDERS, 
  MODEL_CATALOG, 
  VOICE_CATALOG, 
  ELEVENLABS_TTS_MODELS, 
  OPENAI_TTS_MODELS,
  ModelSpec,
  VoiceSpec,
} from "../../models/providerCatalog";

import { BrainCircuit, Eye, Mic, Plus, Save, Play, Trash2 } from "lucide-react";
import { useAudioUI } from "../../hooks/useAudioUI";

export function TabLLM() {
  const [config, setConfig] = useState<LlmConfig | null>(null);
  const [catalogModels, setCatalogModels] = useState<ModelSpec[]>(MODEL_CATALOG);
  const [catalogVoices, setCatalogVoices] = useState<VoiceSpec[]>(VOICE_CATALOG);
  const [llmProviders, setLlmProviders] = useState<string[]>(LLM_PROVIDERS);
  const [ttsProviders, setTtsProviders] = useState<string[]>(TTS_PROVIDERS);
  const [elevenlabsModels, setElevenlabsModels] = useState<string[]>(ELEVENLABS_TTS_MODELS);
  const [openaiTtsModels, setOpenaiTtsModels] = useState<string[]>(OPENAI_TTS_MODELS);
  const [customModelId, setCustomModelId] = useState("");
  const [customModelLabel, setCustomModelLabel] = useState("");
  const [customModelVision, setCustomModelVision] = useState(true);
  const [catalogStatus, setCatalogStatus] = useState("");
  const audio = useAudioUI();

  useEffect(() => {
    Promise.all([ApiController.getLlmConfig(), ApiController.getCatalog()])
      .then(([loadedConfig, catalog]) => {
        setConfig(loadedConfig);
        if (!catalog) return;
        setCatalogModels(catalog.models || MODEL_CATALOG);
        setCatalogVoices(catalog.voices || VOICE_CATALOG);
        setLlmProviders(catalog.llmProviders || LLM_PROVIDERS);
        setTtsProviders(catalog.ttsProviders || TTS_PROVIDERS);
        setElevenlabsModels(catalog.elevenlabsModels || ELEVENLABS_TTS_MODELS);
        setOpenaiTtsModels(catalog.openaiTtsModels || OPENAI_TTS_MODELS);
      })
      .catch(console.error);
  }, []);

  const handleSave = () => {
    if (config) {
      ApiController.updateLlmConfig(config).then(() => {
        alert("Configuração salva com sucesso!");
      });
    }
  };

  if (!config) {
    return <div className="w-full h-full flex items-center justify-center"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--purple-neon)]"></div></div>;
  }

  const updateField = (field: keyof LlmConfig, value: any) => {
    setConfig({ ...config, [field]: value });
    audio.playClick();
  };

  // Helper arrays dinâmicos
  const handleAddCustomModel = async () => {
    const id = customModelId.trim();
    const label = customModelLabel.trim() || id;
    if (!id) {
      setCatalogStatus("Digite o ID do modelo.");
      return;
    }

    const saved = await ApiController.upsertCustomModel(config.llmProvider, id, label, customModelVision);
    if (!saved) {
      setCatalogStatus("Nao foi possivel salvar o modelo customizado.");
      return;
    }

    setCatalogModels(prev => [
      ...prev.filter(model => !(model.provider === saved.provider && model.id === saved.id)),
      saved,
    ]);
    setConfig(prev => prev ? {
      ...prev,
      llmModel: saved.id,
      visionModel: saved.supportsVision ? (prev.visionModel || saved.id) : prev.visionModel,
    } : prev);
    setCustomModelId("");
    setCustomModelLabel("");
    setCatalogStatus("Modelo customizado salvo.");
    audio.playClick();
  };

  const handleRemoveSelectedCustomModel = async () => {
    const selected = catalogModels.find(model => model.provider === config.llmProvider && model.id === config.llmModel);
    if (!selected?.custom) return;
    if (!confirm(`Remover o modelo customizado "${selected.id}"?`)) return;

    const ok = await ApiController.deleteCustomModel(selected.provider, selected.id);
    if (!ok) {
      setCatalogStatus("Nao foi possivel remover o modelo customizado.");
      return;
    }

    setCatalogModels(prev => prev.filter(model => !(model.provider === selected.provider && model.id === selected.id)));
    setConfig(prev => prev ? {
      ...prev,
      llmModel: "",
      visionModel: prev.visionModel === selected.id ? "" : prev.visionModel,
    } : prev);
    setCatalogStatus("Modelo customizado removido.");
    audio.playClick();
  };

  const availableLlmModels = catalogModels.filter(m => m.provider === config.llmProvider);
  const filteredLlmModels = availableLlmModels.filter(m => 
    m.id.toLowerCase().includes(config.llmFilter.toLowerCase()) || 
    m.label.toLowerCase().includes(config.llmFilter.toLowerCase())
  );

  const availableVisionModels = availableLlmModels.filter(m => m.supportsVision);
  const selectedLlmModel = availableLlmModels.find(m => m.id === config.llmModel);

  const availableTtsVoices = catalogVoices.filter(v => v.provider === config.ttsProvider);
  const filteredTtsVoices = availableTtsVoices.filter(v => 
    v.id.toLowerCase().includes(config.ttsFilter.toLowerCase()) || 
    v.label.toLowerCase().includes(config.ttsFilter.toLowerCase())
  );

  const availableTtsModels = config.ttsProvider === "elevenlabs" 
    ? elevenlabsModels
    : (config.ttsProvider === "openai" ? openaiTtsModels : []);

  const ttsHasPitch = !["elevenlabs", "openai"].includes(config.ttsProvider);

  return (
    <div className="w-full h-full bg-[var(--bg-sidebar)] backdrop-blur-2xl border border-[var(--border-strong)] rounded-xl p-8 overflow-y-auto custom-scrollbar flex flex-col relative shadow-2xl transition-all duration-500">
      
      {/* HEADER */}
      <div className="mb-8 flex flex-col md:flex-row md:items-end justify-between gap-4 border-b border-white/5 pb-6">
        <div>
          <h2 className="flex items-center gap-3 text-3xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-[var(--purple-neon)] to-blue-400 mb-2">
            <BrainCircuit size={32} className="text-[var(--purple-neon)]" /> Cérebro & Voz
          </h2>
          <p className="text-sm text-[var(--text-muted)]">
            Configure a IA e a voz da Lira. As mudanças são aplicadas em tempo real.
          </p>
        </div>

        {/* Status Chip integrado no Header */}
        <div className="flex items-center gap-3 bg-black/40 border border-white/10 p-3 rounded-2xl px-5 shadow-inner">
           <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
              <span className="text-[10px] font-black text-white uppercase tracking-widest">Active Core</span>
           </div>
           <div className="w-px h-4 bg-white/10"></div>
           <div className="flex flex-col">
              <span className="text-[9px] text-[var(--text-muted)] uppercase font-bold">LLM: <span className="text-[var(--purple-neon)] font-mono">{config.llmProvider.toUpperCase()}</span></span>
              <span className="text-[9px] text-[var(--text-muted)] uppercase font-bold">TTS: <span className="text-blue-400 font-mono">{config.ttsProvider.toUpperCase()}</span></span>
           </div>
        </div>
      </div>

      <div className="flex flex-col gap-6">
        
        {/* CARD: LLM PRINCIPAL */}
        <div 
          className="relative overflow-hidden bg-[rgba(0,0,0,0.4)] backdrop-blur-md border border-[var(--border-strong)] rounded-2xl p-6 shadow-[0_0_20px_rgba(0,0,0,0.5)] transition-all hover:border-[var(--purple-neon)]/50 hover:shadow-[0_0_30px_rgba(168,85,247,0.15)] group"
          onMouseEnter={() => audio.playHover()}
        >
          <div className="absolute -top-10 -right-10 w-40 h-40 bg-[var(--purple-neon)] rounded-full blur-[90px] opacity-10 group-hover:opacity-20 transition-opacity"></div>
          
          <div className="flex items-center gap-3 mb-6 relative z-10">
            <div className="w-10 h-10 rounded-xl bg-[var(--purple-dark)] border border-[var(--purple-neon)] flex items-center justify-center text-[var(--purple-neon)] shadow-[0_0_15px_var(--purple-dark)]">
              <BrainCircuit size={20} />
            </div>
            <h3 className="font-bold text-[var(--text-primary)] text-lg tracking-wide">Motor Cognitivo (LLM)</h3>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-[120px_1fr_120px_1fr] gap-6 items-center relative z-10">
            
            <span className="text-sm font-bold text-[var(--text-secondary)] uppercase tracking-wider">Provedor:</span>
            <div className="relative">
              <select 
                className="w-full bg-black/60 border border-[var(--border-strong)] hover:border-[var(--purple-neon)]/50 text-[var(--text-primary)] rounded-lg p-2.5 outline-none font-mono text-sm focus:ring-2 focus:ring-[var(--purple-neon)] transition-all cursor-pointer appearance-none shadow-inner"
                value={config.llmProvider}
                onChange={(e) => updateField("llmProvider", e.target.value)}
              >
                {llmProviders.map(p => <option key={p} value={p}>{p.toUpperCase()}</option>)}
              </select>
              <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-[var(--purple-neon)] font-bold">▼</div>
            </div>

            <span className="text-sm font-bold text-[var(--text-secondary)] md:pl-4 uppercase tracking-wider">Filtro:</span>
            <input 
              className="w-full bg-black/60 border border-[var(--border-strong)] hover:border-[var(--purple-neon)]/50 text-[var(--purple-neon)] rounded-lg p-2.5 outline-none font-mono text-sm focus:ring-2 focus:ring-[var(--purple-neon)] transition-all placeholder:text-[var(--border-strong)] shadow-inner"
              placeholder="Buscar modelo..."
              value={config.llmFilter}
              onChange={(e) => updateField("llmFilter", e.target.value)}
            />

            <span className="text-sm font-bold text-[var(--text-secondary)] uppercase tracking-wider">Modelo Base:</span>
            <div className="relative">
              <select 
                className="w-full bg-black/60 border border-[var(--border-strong)] hover:border-[var(--purple-neon)]/50 text-white rounded-lg p-2.5 outline-none font-mono text-sm focus:ring-2 focus:ring-[var(--purple-neon)] transition-all cursor-pointer appearance-none shadow-[inset_0_0_10px_rgba(0,0,0,0.8)]"
                value={config.llmModel}
                onChange={(e) => updateField("llmModel", e.target.value)}
              >
                <option value="">{filteredLlmModels.length === 0 ? "— Nenhum modelo encontrado —" : "— Selecione —"}</option>
                {filteredLlmModels.map(m => <option key={m.id} value={m.id}>{m.label} ({m.id})</option>)}
                {filteredLlmModels.every(m => m.id !== config.llmModel) && config.llmModel && (
                   <option value={config.llmModel}>{config.llmModel} (Custom)</option>
                )}
              </select>
              <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-[var(--purple-neon)] font-bold">▼</div>
            </div>

            <span className="text-sm font-bold text-[var(--text-secondary)] md:pl-4 uppercase tracking-wider">Temperatura:</span>
            <div className="flex items-center gap-4 bg-[rgba(0,0,0,0.4)] p-2 rounded-lg border border-[var(--border-strong)] shadow-inner">
              <input 
                type="range" min="0" max="2" step="0.01"
                className="w-full accent-[var(--purple-neon)] h-2.5 bg-[rgba(255,255,255,0.05)] rounded-lg appearance-none cursor-pointer"
                value={config.llmTemperature}
                onChange={(e) => updateField("llmTemperature", parseFloat(e.target.value))}
              />
              <span className="text-sm font-bold font-mono text-white bg-[var(--purple-neon)] px-2 py-1 rounded w-[50px] text-center shadow-[0_0_10px_var(--purple-neon)]">
                {Number(config.llmTemperature || 0).toFixed(2)}
              </span>
            </div>
          </div>

          <div className="mt-6 pt-5 border-t border-white/5 relative z-10">
            <div className="mb-3 flex flex-col md:flex-row md:items-center md:justify-between gap-2">
              <div>
                <h4 className="text-sm font-bold text-white uppercase tracking-wider">Modelo customizado</h4>
                <p className="text-xs text-[var(--text-muted)]">
                  Use quando a API publicar um modelo novo antes do catalogo ser atualizado.
                </p>
              </div>
              {selectedLlmModel?.custom && (
                <button
                  onClick={handleRemoveSelectedCustomModel}
                  className="px-3 py-2 bg-red-500/10 border border-red-500/30 rounded-lg text-red-300 text-xs font-bold flex items-center gap-2 hover:bg-red-500/20 transition-colors"
                >
                  <Trash2 size={14} /> Remover selecionado
                </button>
              )}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-[1fr_1fr_auto_auto] gap-3">
              <input
                className="bg-black/60 border border-[var(--border-strong)] hover:border-[var(--purple-neon)]/50 text-white rounded-lg p-2.5 outline-none font-mono text-sm focus:ring-2 focus:ring-[var(--purple-neon)] transition-all"
                placeholder="ID do modelo, ex: gemini-3.1-pro-preview"
                value={customModelId}
                onChange={(e) => setCustomModelId(e.target.value)}
              />
              <input
                className="bg-black/60 border border-[var(--border-strong)] hover:border-[var(--purple-neon)]/50 text-white rounded-lg p-2.5 outline-none font-mono text-sm focus:ring-2 focus:ring-[var(--purple-neon)] transition-all"
                placeholder="Nome visivel opcional"
                value={customModelLabel}
                onChange={(e) => setCustomModelLabel(e.target.value)}
              />
              <label className="flex items-center gap-2 bg-black/40 border border-[var(--border-strong)] rounded-lg px-3 py-2 text-xs font-bold text-[var(--text-secondary)] uppercase tracking-wider cursor-pointer">
                <input
                  type="checkbox"
                  checked={customModelVision}
                  onChange={(e) => setCustomModelVision(e.target.checked)}
                  className="accent-[var(--purple-neon)]"
                />
                Vision
              </label>
              <button
                onClick={handleAddCustomModel}
                className="px-4 py-2 bg-[var(--purple-dark)] border border-[var(--purple-neon)]/50 rounded-lg text-white text-sm font-bold flex items-center justify-center gap-2 hover:bg-[var(--purple-neon)]/30 transition-colors"
              >
                <Plus size={15} /> Adicionar
              </button>
            </div>

            {catalogStatus && (
              <p className="mt-3 text-xs text-[var(--cyan-neon)] font-mono">{catalogStatus}</p>
            )}
          </div>
        </div>

        {/* CARD: MODELO DE VISÃO */}
        <div 
          className="relative overflow-hidden bg-[rgba(0,0,0,0.4)] backdrop-blur-md border border-white/5 rounded-2xl p-6 shadow-[0_0_20px_rgba(0,0,0,0.5)] transition-all hover:border-emerald-500/50 hover:shadow-[0_0_30px_rgba(16,185,129,0.15)] group"
          onMouseEnter={() => audio.playHover()}
        >
          <div className="absolute -bottom-10 -left-10 w-40 h-40 bg-emerald-500 rounded-full blur-[90px] opacity-10 group-hover:opacity-20 transition-opacity"></div>
          
          <div className="flex items-center gap-3 mb-6 relative z-10">
            <div className="w-10 h-10 rounded-xl bg-emerald-500/20 border border-emerald-500 flex items-center justify-center text-emerald-400 shadow-[0_0_15px_rgba(16,185,129,0.2)]">
              <Eye size={20} />
            </div>
            <h3 className="font-bold text-[var(--text-primary)] text-lg tracking-wide">Visão Computacional</h3>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-[120px_1fr] gap-6 items-center relative z-10">
            <span className="text-sm font-bold text-[var(--text-secondary)] uppercase tracking-wider">Modelo Vision:</span>
            <div className="relative w-full md:w-1/2">
              <select 
                className="w-full bg-black/60 border border-[var(--border-strong)] hover:border-emerald-500/50 text-emerald-400 rounded-lg p-2.5 outline-none font-mono text-sm focus:ring-2 focus:ring-emerald-500 transition-all cursor-pointer disabled:opacity-50 appearance-none shadow-inner"
                value={config.visionModel}
                onChange={(e) => updateField("visionModel", e.target.value)}
                disabled={availableVisionModels.length === 0}
              >
                {availableVisionModels.length === 0 ? (
                  <option value="">— Provider sem suporte a visão —</option>
                ) : (
                  <>
                    <option value="">— Selecione —</option>
                    {availableVisionModels.map(m => <option key={m.id} value={m.id}>{m.label}</option>)}
                    {availableVisionModels.every(m => m.id !== config.visionModel) && config.visionModel && (
                      <option value={config.visionModel}>{config.visionModel} (Custom)</option>
                    )}
                  </>
                )}
              </select>
              <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-emerald-500 font-bold">▼</div>
            </div>
          </div>
        </div>

        {/* CARD: VOZ (TTS) */}
        <div 
          className="relative overflow-hidden bg-[rgba(0,0,0,0.4)] backdrop-blur-md border border-white/5 rounded-2xl p-6 shadow-[0_0_20px_rgba(0,0,0,0.5)] transition-all hover:border-blue-500/50 hover:shadow-[0_0_30px_rgba(59,130,246,0.2)] group"
          onMouseEnter={() => audio.playHover()}
        >
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full h-full bg-gradient-to-r from-transparent via-blue-500/5 to-transparent pointer-events-none group-hover:via-blue-500/10 transition-colors"></div>
          
          <div className="flex items-center gap-3 mb-6 relative z-10">
            <div className="w-10 h-10 rounded-xl bg-blue-500/20 border border-blue-500 flex items-center justify-center text-blue-400 shadow-[0_0_15px_rgba(59,130,246,0.3)]">
              <Mic size={20} />
            </div>
            <h3 className="font-bold text-[var(--text-primary)] text-lg tracking-wide">Síntese de Voz (TTS)</h3>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-[120px_1fr_120px_1fr] gap-y-5 gap-x-6 items-center relative z-10">
            
            <span className="text-sm font-bold text-[var(--text-secondary)] uppercase tracking-wider">Provedor TTS:</span>
            <div className="relative">
              <select 
                className="w-full bg-black/60 border border-[var(--border-strong)] hover:border-blue-500/50 text-[var(--text-primary)] rounded-lg p-2.5 outline-none font-mono text-sm focus:ring-2 focus:ring-blue-500 transition-all cursor-pointer appearance-none shadow-inner"
                value={config.ttsProvider}
                onChange={(e) => updateField("ttsProvider", e.target.value)}
              >
                {ttsProviders.map(p => <option key={p} value={p}>{p.toUpperCase()}</option>)}
              </select>
              <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-blue-500 font-bold">▼</div>
            </div>

            <span className="text-sm font-bold text-[var(--text-secondary)] md:pl-4 uppercase tracking-wider">Filtro TTS:</span>
            <input 
              className="w-full bg-black/60 border border-[var(--border-strong)] hover:border-blue-500/50 text-blue-400 rounded-lg p-2.5 outline-none font-mono text-sm focus:ring-2 focus:ring-blue-500 transition-all placeholder:text-[var(--border-strong)] shadow-inner"
              placeholder="Buscar voz..."
              value={config.ttsFilter}
              onChange={(e) => updateField("ttsFilter", e.target.value)}
            />

            <span className="text-sm font-bold text-[var(--text-secondary)] uppercase tracking-wider">Voz:</span>
            <div className="relative">
              <select 
                className="w-full bg-black/60 border border-[var(--border-strong)] hover:border-blue-500/50 text-white rounded-lg p-2.5 outline-none font-mono text-sm focus:ring-2 focus:ring-blue-500 transition-all cursor-pointer appearance-none shadow-[inset_0_0_10px_rgba(0,0,0,0.8)]"
                value={config.ttsVoice}
                onChange={(e) => updateField("ttsVoice", e.target.value)}
              >
                {config.ttsProvider === "elevenlabs" ? (
                  <option value={config.ttsVoice || "lira_voice_id"}>{config.ttsVoice || "lira_voice_id"} (Manual)</option>
                ) : (
                  <>
                    <option value="">— Selecione —</option>
                    {filteredTtsVoices.map(v => <option key={v.id} value={v.id}>{v.label}</option>)}
                    {filteredTtsVoices.every(v => v.id !== config.ttsVoice) && config.ttsVoice && (
                      <option value={config.ttsVoice}>{config.ttsVoice} (Custom)</option>
                    )}
                  </>
                )}
              </select>
              <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-blue-500 font-bold">▼</div>
            </div>

            <span className="text-sm font-bold text-[var(--text-secondary)] md:pl-4 uppercase tracking-wider">Modelo TTS:</span>
            <div className="relative">
              <select 
                className="w-full bg-black/60 border border-[var(--border-strong)] hover:border-blue-500/50 text-[var(--text-primary)] rounded-lg p-2.5 outline-none font-mono text-sm focus:ring-2 focus:ring-blue-500 transition-all cursor-pointer disabled:opacity-50 appearance-none shadow-inner"
                value={config.ttsModel}
                onChange={(e) => updateField("ttsModel", e.target.value)}
                disabled={availableTtsModels.length === 0}
              >
                {availableTtsModels.length === 0 ? (
                  <option value="">— Padrão —</option>
                ) : (
                  availableTtsModels.map(m => <option key={m} value={m}>{m}</option>)
                )}
              </select>
              <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-blue-500 font-bold opacity-50">▼</div>
            </div>

            {/* SLIDERS TTS */}
            <span className="text-sm font-bold text-[var(--text-secondary)] uppercase tracking-wider">Velocidade:</span>
            <div className="flex items-center gap-4 bg-[rgba(0,0,0,0.4)] p-2 rounded-lg border border-[var(--border-strong)] shadow-inner">
              <input 
                type="range" min="0.7" max="1.5" step="0.01"
                className="w-full accent-blue-500 h-2.5 bg-[rgba(255,255,255,0.05)] rounded-lg appearance-none cursor-pointer"
                value={config.ttsSpeed}
                onChange={(e) => updateField("ttsSpeed", parseFloat(e.target.value))}
              />
              <span className="text-sm font-bold font-mono text-white bg-blue-500 px-2 py-1 rounded w-[60px] text-center shadow-[0_0_10px_rgba(59,130,246,0.8)]">{Number(config.ttsSpeed || 1).toFixed(2)}x</span>
            </div>

            <span className="text-sm font-bold text-[var(--text-secondary)] md:pl-4 uppercase tracking-wider">Pitch:</span>
            <div className={`flex items-center gap-4 bg-[rgba(0,0,0,0.4)] p-2 rounded-lg border border-[var(--border-strong)] shadow-inner ${!ttsHasPitch ? "opacity-50" : ""}`}>
              <input 
                type="range" min="-20" max="20" step="1" disabled={!ttsHasPitch}
                className="w-full accent-emerald-500 h-2.5 bg-[rgba(255,255,255,0.05)] rounded-lg appearance-none cursor-pointer disabled:cursor-not-allowed"
                value={config.ttsPitch}
                onChange={(e) => updateField("ttsPitch", parseFloat(e.target.value))}
              />
              <span className="text-sm font-bold font-mono text-white bg-emerald-500 px-2 py-1 rounded w-[60px] text-center shadow-[0_0_10px_rgba(16,185,129,0.8)]">{Number(config.ttsPitch || 0).toFixed(1)}</span>
            </div>

            {config.ttsProvider === "elevenlabs" && (
              <>
                <span className="text-sm font-bold text-[var(--text-secondary)] uppercase tracking-wider">Stability:</span>
                <div className="flex items-center gap-4 bg-[rgba(0,0,0,0.4)] p-2 rounded-lg border border-[var(--border-strong)] shadow-inner">
                  <input type="range" min="0" max="1" step="0.01" className="w-full accent-[var(--purple-neon)] h-2.5 bg-[rgba(255,255,255,0.05)] rounded-lg appearance-none cursor-pointer" value={config.ttsStability} onChange={(e) => updateField("ttsStability", parseFloat(e.target.value))} />
                  <span className="text-sm font-bold font-mono text-white bg-[var(--purple-neon)] px-2 py-1 rounded w-[60px] text-center shadow-[0_0_10px_var(--purple-neon)]">{Number(config.ttsStability || 0).toFixed(2)}</span>
                </div>

                <span className="text-sm font-bold text-[var(--text-secondary)] md:pl-4 uppercase tracking-wider">Similarity:</span>
                <div className="flex items-center gap-4 bg-[rgba(0,0,0,0.4)] p-2 rounded-lg border border-[var(--border-strong)] shadow-inner">
                  <input type="range" min="0" max="1" step="0.01" className="w-full accent-blue-400 h-2.5 bg-[rgba(255,255,255,0.05)] rounded-lg appearance-none cursor-pointer" value={config.ttsSimilarity} onChange={(e) => updateField("ttsSimilarity", parseFloat(e.target.value))} />
                  <span className="text-sm font-bold font-mono text-white bg-blue-500 px-2 py-1 rounded w-[60px] text-center shadow-[0_0_10px_rgba(59,130,246,0.8)]">{Number(config.ttsSimilarity || 0).toFixed(2)}</span>
                </div>

                <span className="text-sm font-bold text-[var(--text-secondary)] uppercase tracking-wider">Style:</span>
                <div className="flex items-center gap-4 bg-[rgba(0,0,0,0.4)] p-2 rounded-lg border border-[var(--border-strong)] shadow-inner">
                  <input type="range" min="0" max="1" step="0.01" className="w-full accent-amber-500 h-2.5 bg-[rgba(255,255,255,0.05)] rounded-lg appearance-none cursor-pointer" value={config.ttsStyle} onChange={(e) => updateField("ttsStyle", parseFloat(e.target.value))} />
                  <span className="text-sm font-bold font-mono text-white bg-amber-500 px-2 py-1 rounded w-[60px] text-center shadow-[0_0_10px_rgba(245,158,11,0.8)]">{Number(config.ttsStyle || 0).toFixed(2)}</span>
                </div>

                <div className="md:col-start-2 md:col-span-3 flex items-center pt-2">
                  <label className="flex items-center gap-3 cursor-pointer group">
                    <div className="relative flex items-center">
                      <input type="checkbox" className="peer sr-only" checked={config.ttsSpeakerBoost} onChange={(e) => updateField("ttsSpeakerBoost", e.target.checked)} />
                      <div className="w-12 h-6 bg-[rgba(0,0,0,0.5)] border border-[var(--border-strong)] peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-gray-400 after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[var(--purple-neon)] peer-checked:after:bg-white shadow-inner"></div>
                    </div>
                    <span className="text-sm font-bold text-[var(--text-secondary)] group-hover:text-[var(--text-primary)] transition-colors uppercase tracking-wider">Ativar Speaker Boost (ElevenLabs)</span>
                  </label>
                </div>
              </>
            )}

            <div className="col-span-1 md:col-span-4 flex flex-col md:flex-row md:items-center gap-4 mt-6 pt-6 border-t border-white/5">
              <button 
                onMouseEnter={() => audio.playHover()}
                onClick={async () => {
                  audio.playClick();
                  await ApiController.updateLlmConfig(config);
                  await ApiController.speakText("Oi, Amarinth. Teste de voz da Lira com lipsync ativo.");
                }}
                className="bg-gradient-to-r from-blue-600 to-blue-500 hover:to-blue-400 text-white transition-all shadow-[0_0_20px_rgba(37,99,235,0.4)] hover:shadow-[0_0_30px_rgba(59,130,246,0.6)] px-8 py-3 rounded-xl font-bold text-sm flex items-center justify-center gap-2 transform hover:scale-[1.02]"
              >
                <Play size={18} fill="currentColor" /> Testar Voz
              </button>
              <span className="text-xs text-[var(--text-secondary)] bg-[rgba(0,0,0,0.4)] px-4 py-2 rounded-lg border border-[var(--border-strong)] font-mono">
                <span className="text-blue-400">ℹ️ Info:</span> Pitch {config.ttsProvider === "elevenlabs" ? "indisponível" : (config.ttsProvider === "openai" ? "por estilo" : "nativo")}
              </span>
            </div>

          </div>
        </div>
      </div>

      {/* SAVE ACTIONS */}
      <div className="mt-8 pt-6 border-t border-white/5 flex justify-end">
        <button 
          onMouseEnter={() => audio.playHover()}
          onClick={() => {
            audio.playClick();
            handleSave();
          }}
          className="bg-gradient-to-br from-[var(--purple-neon)] to-[#7e22ce] text-white transition-all shadow-[0_0_25px_rgba(168,85,247,0.5)] hover:shadow-[0_0_40px_rgba(168,85,247,0.8)] px-8 py-3 rounded-xl font-extrabold text-sm flex items-center gap-2 transform hover:scale-[1.02] border border-white/10 backdrop-blur-md"
        >
          <Save size={18} /> SALVAR ALTERAÇÕES
        </button>
      </div>


    </div>
  );
}
