import { useEffect, useState } from "react";
import { ApiController } from "../../controllers/api";
import {
  AlertTriangle,
  BrainCircuit,
  ChevronDown,
  ChevronUp,
  Database,
  Network,
  Pencil,
  Plus,
  RefreshCw,
  Save,
  Search,
  Trash2,
  X,
} from "lucide-react";

type GraphFact = { subject: string; relation: string; object: string };
type RagMemory = { id: string; text: string; metadata: any };

const EMPTY_FACT: GraphFact = { subject: "", relation: "", object: "" };
const MEMORY_PREVIEW_LIMIT = 420;

export function TabMemoria() {
  const [activeTab, setActiveTab] = useState<"graph" | "rag">("graph");
  const [isLoading, setIsLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [statusMessage, setStatusMessage] = useState("");

  const [facts, setFacts] = useState<GraphFact[]>([]);
  const [memories, setMemories] = useState<RagMemory[]>([]);
  const [expandedMemories, setExpandedMemories] = useState<Set<string>>(() => new Set());

  const [factForm, setFactForm] = useState<GraphFact>(EMPTY_FACT);
  const [editingFact, setEditingFact] = useState<GraphFact | null>(null);
  const [memoryText, setMemoryText] = useState("");
  const [editingMemory, setEditingMemory] = useState<RagMemory | null>(null);

  const loadData = async () => {
    setIsLoading(true);
    setStatusMessage("");
    try {
      if (activeTab === "graph") {
        const { facts } = await ApiController.getMemoryGraph();
        setFacts(facts || []);
      } else {
        const { memories } = await ApiController.getMemoryRag();
        setMemories(memories || []);
      }
    } catch (e) {
      console.error("Erro ao carregar dados:", e);
      setStatusMessage("Falha ao carregar memorias.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [activeTab]);

  const resetFactEditor = () => {
    setFactForm(EMPTY_FACT);
    setEditingFact(null);
  };

  const resetMemoryEditor = () => {
    setMemoryText("");
    setEditingMemory(null);
  };

  const handleSaveFact = async () => {
    const subject = factForm.subject.trim();
    const relation = factForm.relation.trim();
    const object = factForm.object.trim();
    if (!subject || !relation || !object) {
      setStatusMessage("Preencha sujeito, relacao e objeto.");
      return;
    }

    if (editingFact) {
      await ApiController.deleteMemoryGraph(editingFact.subject, editingFact.relation, editingFact.object);
    }

    const ok = await ApiController.createMemoryGraph(subject, relation, object);
    if (!ok) {
      setStatusMessage("Nao foi possivel salvar o fato.");
      return;
    }

    resetFactEditor();
    setStatusMessage("Fato salvo.");
    await loadData();
  };

  const handleDeleteFact = async (fact: GraphFact) => {
    if (!confirm(`Remover o fato "${fact.subject} -> ${fact.relation} -> ${fact.object}" permanentemente?`)) return;
    const ok = await ApiController.deleteMemoryGraph(fact.subject, fact.relation, fact.object);
    if (ok) {
      setFacts(prev => prev.filter(item => item.subject !== fact.subject || item.relation !== fact.relation || item.object !== fact.object));
      if (editingFact && editingFact.subject === fact.subject && editingFact.relation === fact.relation && editingFact.object === fact.object) {
        resetFactEditor();
      }
    }
  };

  const handleSaveMemory = async () => {
    const text = memoryText.trim();
    if (text.length < 3) {
      setStatusMessage("Texto de memoria muito curto.");
      return;
    }

    const ok = editingMemory
      ? await ApiController.updateMemoryRag(editingMemory.id, text, editingMemory.metadata || {})
      : Boolean(await ApiController.createMemoryRag(text));

    if (!ok) {
      setStatusMessage("Nao foi possivel salvar a memoria.");
      return;
    }

    resetMemoryEditor();
    setStatusMessage("Memoria salva.");
    await loadData();
  };

  const handleDeleteMemory = async (memory: RagMemory) => {
    if (!confirm("Remover esta memoria semantica permanentemente?")) return;
    const ok = await ApiController.deleteMemoryRag(memory.id);
    if (ok) {
      setMemories(prev => prev.filter(item => item.id !== memory.id));
      if (editingMemory?.id === memory.id) {
        resetMemoryEditor();
      }
    }
  };

  const toggleMemoryExpanded = (id: string) => {
    setExpandedMemories(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const filteredFacts = facts.filter(f =>
    f.subject.toLowerCase().includes(searchTerm.toLowerCase()) ||
    f.object.toLowerCase().includes(searchTerm.toLowerCase()) ||
    f.relation.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const filteredMemories = memories.filter(m =>
    m.text.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="w-full h-full bg-[rgba(15,15,20,0.5)] backdrop-blur-2xl border border-[var(--border-strong)] rounded-2xl overflow-hidden shadow-2xl relative flex flex-col">
      <div className="bg-[rgba(10,10,15,0.85)] border-b border-[var(--border-strong)] p-6 z-10 shadow-lg backdrop-blur-md flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-full bg-[var(--purple-dark)] flex items-center justify-center border border-[var(--purple-neon)] shadow-[0_0_15px_var(--purple-dark)]">
            <BrainCircuit size={24} className="text-[var(--purple-neon)]" />
          </div>
          <div>
            <h2 className="text-2xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-[var(--purple-neon)] to-[var(--cyan-neon)]">
              Nucleo de Memoria
            </h2>
            <p className="text-[11px] text-[var(--text-muted)] uppercase tracking-widest font-bold">
              Base de conhecimento, fatos e RAG da Lira
            </p>
          </div>
        </div>

        <div className="flex bg-black/40 p-1.5 rounded-xl border border-white/5">
          <button
            onClick={() => setActiveTab("graph")}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-bold text-xs uppercase tracking-wider transition-all ${
              activeTab === "graph"
                ? "bg-[var(--purple-dark)] text-white border border-[var(--purple-neon)]/50 shadow-lg"
                : "text-[var(--text-muted)] hover:text-white hover:bg-white/5"
            }`}
          >
            <Network size={14} /> Fatos
          </button>
          <button
            onClick={() => setActiveTab("rag")}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-bold text-xs uppercase tracking-wider transition-all ${
              activeTab === "rag"
                ? "bg-blue-900/40 text-blue-400 border border-blue-500/50 shadow-lg"
                : "text-[var(--text-muted)] hover:text-white hover:bg-white/5"
            }`}
          >
            <Database size={14} /> Textos RAG
          </button>
        </div>
      </div>

      <div className="px-6 py-4 border-b border-[var(--border-strong)] bg-black/20 flex flex-col gap-4">
        <div className="flex gap-4">
          <div className="flex-1 relative">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
            <input
              type="text"
              placeholder={activeTab === "graph" ? "Buscar por entidade ou relacao..." : "Buscar nos textos de memoria..."}
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full bg-black/40 border border-white/5 rounded-xl py-2 pl-9 pr-4 text-sm text-white placeholder:text-[var(--text-muted)] focus:outline-none focus:border-[var(--purple-neon)]/50 transition-colors"
            />
          </div>
          <button
            onClick={loadData}
            className="px-4 py-2 bg-white/5 border border-white/10 rounded-xl hover:bg-white/10 transition-colors text-[var(--text-muted)] hover:text-white flex items-center justify-center"
            title="Recarregar"
          >
            <RefreshCw size={16} className={isLoading ? "animate-spin" : ""} />
          </button>
        </div>

        {activeTab === "graph" ? (
          <div className="grid grid-cols-1 md:grid-cols-[1fr_1fr_1fr_auto] gap-3 bg-black/30 border border-white/5 rounded-xl p-3">
            <input className="bg-black/50 border border-white/10 rounded-lg px-3 py-2 text-sm text-white outline-none focus:border-[var(--purple-neon)]/50" placeholder="Sujeito" value={factForm.subject} onChange={(e) => setFactForm(prev => ({ ...prev, subject: e.target.value }))} />
            <input className="bg-black/50 border border-white/10 rounded-lg px-3 py-2 text-sm text-white outline-none focus:border-[var(--purple-neon)]/50" placeholder="Relacao" value={factForm.relation} onChange={(e) => setFactForm(prev => ({ ...prev, relation: e.target.value }))} />
            <input className="bg-black/50 border border-white/10 rounded-lg px-3 py-2 text-sm text-white outline-none focus:border-[var(--purple-neon)]/50" placeholder="Objeto" value={factForm.object} onChange={(e) => setFactForm(prev => ({ ...prev, object: e.target.value }))} />
            <div className="flex gap-2">
              <button onClick={handleSaveFact} className="px-4 py-2 bg-[var(--purple-dark)] border border-[var(--purple-neon)]/50 rounded-lg text-white text-sm font-bold flex items-center gap-2 hover:bg-[var(--purple-neon)]/30 transition-colors">
                {editingFact ? <Save size={15} /> : <Plus size={15} />} {editingFact ? "Salvar" : "Criar"}
              </button>
              {editingFact && (
                <button onClick={resetFactEditor} className="px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-[var(--text-muted)] hover:text-white transition-colors">
                  <X size={15} />
                </button>
              )}
            </div>
          </div>
        ) : (
          <div className="bg-black/30 border border-white/5 rounded-xl p-3">
            <textarea
              className="w-full min-h-[100px] bg-black/50 border border-white/10 rounded-lg px-3 py-2 text-sm text-white outline-none focus:border-blue-500/50 resize-y custom-scrollbar"
              placeholder="Escreva uma memoria semantica manual..."
              value={memoryText}
              onChange={(e) => setMemoryText(e.target.value)}
            />
            <div className="mt-3 flex items-center justify-between gap-3">
              <span className="text-xs text-[var(--text-muted)]">
                {editingMemory ? `Editando ID ${editingMemory.id.slice(0, 8)}...` : "Nova memoria RAG manual"}
              </span>
              <div className="flex gap-2">
                {editingMemory && (
                  <button onClick={resetMemoryEditor} className="px-4 py-2 bg-white/5 border border-white/10 rounded-lg text-[var(--text-muted)] hover:text-white text-sm font-bold transition-colors">
                    Cancelar
                  </button>
                )}
                <button onClick={handleSaveMemory} className="px-4 py-2 bg-blue-900/50 border border-blue-500/50 rounded-lg text-white text-sm font-bold flex items-center gap-2 hover:bg-blue-500/30 transition-colors">
                  {editingMemory ? <Save size={15} /> : <Plus size={15} />} {editingMemory ? "Salvar memoria" : "Criar memoria"}
                </button>
              </div>
            </div>
          </div>
        )}

        {statusMessage && (
          <div className="text-xs text-[var(--cyan-neon)] font-mono">{statusMessage}</div>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-6 custom-scrollbar relative bg-gradient-to-b from-transparent to-black/40">
        {isLoading ? (
          <div className="absolute inset-0 flex items-center justify-center flex-col gap-4">
            <div className="w-10 h-10 border-4 border-[var(--purple-neon)] border-t-transparent rounded-full animate-spin"></div>
            <p className="text-[var(--text-muted)] font-mono text-sm">Acessando redes neurais...</p>
          </div>
        ) : activeTab === "graph" ? (
          filteredFacts.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-[var(--text-muted)] opacity-50">
              <Network size={64} className="mb-4" />
              <p>Nenhum fato logico encontrado no Knowledge Graph.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredFacts.map((fact, i) => (
                <div key={`${fact.subject}-${fact.relation}-${fact.object}-${i}`} className="bg-black/40 border border-white/10 hover:border-[var(--purple-neon)]/50 rounded-xl p-4 transition-all group flex flex-col gap-3 shadow-lg">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-mono text-[var(--purple-neon)] bg-[var(--purple-dark)]/30 px-2 py-0.5 rounded border border-[var(--purple-neon)]/20 uppercase">Fato Logico</span>
                    <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        onClick={() => {
                          setEditingFact(fact);
                          setFactForm(fact);
                        }}
                        className="text-[var(--text-muted)] hover:text-[var(--cyan-neon)] p-1 hover:bg-white/10 rounded"
                        title="Editar memoria"
                      >
                        <Pencil size={16} />
                      </button>
                      <button
                        onClick={() => handleDeleteFact(fact)}
                        className="text-[var(--text-muted)] hover:text-red-400 p-1 hover:bg-red-500/10 rounded"
                        title="Apagar memoria"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </div>
                  <div className="flex flex-col gap-1.5 mt-1">
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] uppercase text-[var(--text-muted)] w-16">Sujeito:</span>
                      <span className="text-white font-bold text-sm bg-white/5 px-2 py-1 rounded truncate">{fact.subject}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] uppercase text-[var(--text-muted)] w-16">Relacao:</span>
                      <span className="text-[var(--cyan-neon)] font-mono text-xs">{fact.relation}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] uppercase text-[var(--text-muted)] w-16">Objeto:</span>
                      <span className="text-white font-bold text-sm bg-white/5 px-2 py-1 rounded truncate">{fact.object}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )
        ) : (
          filteredMemories.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-[var(--text-muted)] opacity-50">
              <Database size={64} className="mb-4" />
              <p>Nenhuma memoria semantica encontrada no RAG.</p>
            </div>
          ) : (
            <div className="flex flex-col gap-4">
              {filteredMemories.map((mem) => {
                const isExpanded = expandedMemories.has(mem.id);
                const isLong = mem.text.length > MEMORY_PREVIEW_LIMIT;
                const visibleText = isExpanded || !isLong ? mem.text : `${mem.text.slice(0, MEMORY_PREVIEW_LIMIT)}...`;

                return (
                  <div key={mem.id} className="bg-black/40 border border-white/10 hover:border-blue-500/50 rounded-xl p-5 transition-all group flex flex-col gap-2 shadow-lg">
                    <div className="flex items-start justify-between gap-4">
                      <p className="text-sm text-gray-200 leading-relaxed flex-1 whitespace-pre-wrap">{visibleText}</p>
                      <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                        <button
                          onClick={() => {
                            setEditingMemory(mem);
                            setMemoryText(mem.text);
                          }}
                          className="text-[var(--text-muted)] hover:text-blue-400 p-2 hover:bg-white/10 rounded"
                          title="Editar memoria"
                        >
                          <Pencil size={18} />
                        </button>
                        <button
                          onClick={() => handleDeleteMemory(mem)}
                          className="text-[var(--text-muted)] hover:text-red-400 p-2 hover:bg-red-500/10 rounded"
                          title="Apagar memoria"
                        >
                          <Trash2 size={18} />
                        </button>
                      </div>
                    </div>

                    {isLong && (
                      <button
                        onClick={() => toggleMemoryExpanded(mem.id)}
                        className="self-start mt-1 text-xs font-bold text-blue-400 hover:text-blue-300 flex items-center gap-1"
                      >
                        {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                        {isExpanded ? "Ver menos" : "Ver mais"}
                      </button>
                    )}

                    <div className="mt-2 pt-3 border-t border-white/5 flex flex-wrap gap-2">
                      <span className="text-[10px] font-mono text-blue-400 bg-blue-900/30 px-2 py-0.5 rounded border border-blue-500/20">
                        ID: {mem.id.slice(0, 8)}...
                      </span>
                      {mem.metadata?.source && (
                        <span className="text-[10px] font-mono text-gray-400 bg-white/5 px-2 py-0.5 rounded border border-white/10">
                          SRC: {mem.metadata.source}
                        </span>
                      )}
                      {mem.metadata?.role && (
                        <span className="text-[10px] font-mono text-gray-400 bg-white/5 px-2 py-0.5 rounded border border-white/10">
                          ROLE: {mem.metadata.role}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )
        )}
      </div>

      <div className="bg-red-500/10 border-t border-red-500/20 p-3 px-6 flex items-center gap-3">
        <AlertTriangle size={16} className="text-red-400 shrink-0" />
        <p className="text-xs text-red-300 font-medium">
          Aviso: apagar uma memoria remove contexto permanentemente. Edite fatos do grafo com cuidado.
        </p>
      </div>
    </div>
  );
}
