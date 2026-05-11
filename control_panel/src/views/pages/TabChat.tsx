import { useState, useRef, useEffect } from "react";
import { ApiController } from "../../controllers/api";
import { ChatMessage } from "../../models/types";
import { LLM_PROVIDERS, MODEL_CATALOG } from "../../models/providerCatalog";
import { 
  Send, 
  Paperclip, 
  Mic, 
  StopCircle, 
  Copy, 
  Volume2, 
  User, 
  Bot, 
  Terminal,
  Play,
  Pause,
  Music,
  MessageSquareText,
  BrainCircuit,
  ExternalLink,
  Download
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkBreaks from "remark-breaks";

function MediaRenderer({ media }: { media: any }) {
  const [playing, setPlaying] = useState(false);
  const audioRef = useRef<HTMLAudioElement>(null);

  // Corrige os IPs "chumbados" que o backend envia (127.0.0.1) para o IP correto da rede
  const HOST = window.location.hostname;
  const BACKEND_URL = `http://${HOST}:8042`;
  const mediaUrl = media.url ? media.url.replace("http://127.0.0.1:8042", BACKEND_URL).replace("http://localhost:8042", BACKEND_URL) : "";

  if (media.type === "image") {
    return (
      <div className="mt-4 rounded-2xl overflow-hidden border border-white/10 shadow-2xl bg-black/20">
        <img src={mediaUrl} alt="Lira Generated" className="w-full h-auto max-h-[400px] object-contain hover:scale-[1.02] transition-transform duration-500" />
        <div className="p-3 flex justify-between items-center bg-white/5 backdrop-blur-md">
           <span className="text-[10px] font-bold text-[var(--text-muted)] uppercase tracking-widest">Imagem Gerada</span>
           <div className="flex gap-2">
             <a href={mediaUrl} target="_blank" rel="noreferrer" className="p-1.5 hover:bg-white/10 rounded-lg transition-colors text-[var(--text-secondary)] hover:text-white">
               <ExternalLink size={14} />
             </a>
             <a href={mediaUrl} download className="p-1.5 hover:bg-white/10 rounded-lg transition-colors text-[var(--text-secondary)] hover:text-white">
               <Download size={14} />
             </a>
           </div>
        </div>
      </div>
    );
  }

  if (media.type === "music") {
    return (
      <div className="mt-4 bg-gradient-to-br from-blue-500/20 to-purple-500/20 border border-blue-500/30 rounded-2xl p-4 flex items-center gap-4 shadow-lg backdrop-blur-md relative overflow-hidden group">
        <div className="absolute top-0 left-0 w-1 h-full bg-blue-500 shadow-[0_0_10px_rgba(59,130,246,0.8)]"></div>
        
        <div className="w-12 h-12 rounded-xl bg-blue-500/30 flex items-center justify-center text-blue-400 shrink-0">
          {playing ? <Music size={24} className="animate-bounce" /> : <Music size={24} />}
        </div>
        
        <div className="flex-1 min-w-0">
          <p className="text-xs font-black text-white truncate uppercase tracking-wider mb-1">Música Gerada pela Lira</p>
          <p className="text-[10px] text-blue-300 font-mono opacity-70">ID: {media.job_id}</p>
          {mediaUrl && <audio ref={audioRef} src={mediaUrl} onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} />}
        </div>

        {mediaUrl ? (
          <button 
            onClick={() => {
              if (playing) audioRef.current?.pause();
              else audioRef.current?.play();
            }}
            className="w-10 h-10 rounded-full bg-blue-500 text-white flex items-center justify-center shadow-[0_0_15px_rgba(59,130,246,0.5)] hover:scale-110 active:scale-95 transition-all"
          >
            {playing ? <Pause size={20} fill="white" /> : <Play size={20} fill="white" className="ml-1" />}
          </button>
        ) : (
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 border-2 border-blue-400 border-t-transparent rounded-full animate-spin"></div>
            <span className="text-[10px] font-bold text-blue-400 animate-pulse">GERANDO...</span>
          </div>
        )}
      </div>
    );
  }

  return null;
}

export function TabChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "system-1",
      role: "system",
      content: "Control Center online. Este chat compartilha a mesma memória que o terminal, mas com suporte total a Markdown e Multimídia.",
      timestamp: new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }),
    }
  ]);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [provider, setProvider] = useState("openai");
  const [model, setModel] = useState("gpt-4o");
  const [attachments, setAttachments] = useState<{name: string, data: string, type: string}[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  
  const scrollRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const currentResponseRef = useRef("");

  const availableModels = MODEL_CATALOG.filter(m => m.provider === provider);

  useEffect(() => {
    const scrollToBottom = () => {
      if (scrollRef.current) {
        scrollRef.current.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
      }
    };
    
    scrollToBottom();
    const timeout = setTimeout(scrollToBottom, 150);
    
    // Salva as mensagens no LocalStorage
    localStorage.setItem("lira_chat_messages", JSON.stringify(messages));
    
    return () => clearTimeout(timeout);
  }, [messages, isTyping]);

  // Carrega as configurações de LLM e histórico do servidor
  useEffect(() => {
    ApiController.getLlmConfig().then(config => {
      setProvider(config.llmProvider);
      setModel(config.llmModel);
    });

    // Carrega o histórico persistente do servidor
    ApiController.getChatHistory(80).then(({ messages: serverMessages }) => {
      if (serverMessages.length === 0) return;
      
      // Converte msg {role, content} para ChatMessage {id, role, content, timestamp}
      const historyMsgs: ChatMessage[] = serverMessages
        .filter(m => m.role !== "system") // ignora system do histórico
        .map(m => ({
          id: `hist-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          role: m.role === "Amarinth" ? "user" as const : "lira" as const,
          content: m.content,
          timestamp: new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }),
        }));

      setMessages(prev => {
        // Se já tem mais que só a msg de sistema, mantém (pode ter carregado do localStorage)
        if (prev.length > 1) return prev;
        return [prev[0], ...historyMsgs.slice(-50)];
      });
    });
  }, []);

  // Limpeza do WebSocket ao desmontar
  useEffect(() => {
    return () => {
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  const stopCurrentResponse = () => {
    ApiController.cancelChatResponse();
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setIsTyping(false);
    setMessages(prev => {
      const last = prev[prev.length - 1];
      if (last && last.id === "streaming-res") {
        return [...prev.slice(0, -1), { ...last, id: Date.now().toString() }];
      }
      return prev;
    });
  };

  const handleSend = () => {
    if (!input.trim() && attachments.length === 0) return;

    // Se já estiver processando, não deixa mandar outra
    if (isTyping) return;

    // Fecha conexão anterior se existir
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      role: "user",
      content: input.trim(),
      timestamp: new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }),
      attachments: attachments.map(a => a.data)
    };
    const historyForBackend = messages
      .filter((msg) => msg.role === "user" || msg.role === "lira")
      .slice(-16)
      .map((msg) => ({ role: msg.role, content: msg.content }));

    setMessages(prev => [...prev, userMsg]);
    setInput("");
    setAttachments([]);
    setIsTyping(true);
    currentResponseRef.current = "";

    // Conecta WebSocket — a mensagem já é enviada no onopen automaticamente
    const { ws } = ApiController.connectChatWebSocket(
      userMsg.content,
      userMsg.attachments || [],
      provider,
      model,
      historyForBackend,
      // onChunk
      (chunk) => {
        currentResponseRef.current += chunk;
        setMessages(prev => {
          const last = prev[prev.length - 1];
          if (last && last.role === "lira" && last.id === "streaming-res") {
            return [...prev.slice(0, -1), { ...last, content: currentResponseRef.current }];
          } else {
            return [...prev, {
              id: "streaming-res",
              role: "lira",
              content: currentResponseRef.current,
              timestamp: new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
            }];
          }
        });
      },
      // onMeta
      (meta) => {
        setMessages(prev => {
          const last = prev[prev.length - 1];
          if (last && last.role === "lira" && last.id === "streaming-res") {
            return [...prev.slice(0, -1), { ...last, meta }];
          }
          return prev;
        });
      },
      // onMedia
      (media) => {
         setMessages(prev => {
           const last = prev[prev.length - 1];
           if (last && last.role === "lira") {
             let updatedMedia = last.media || [];
             const existingIndex = updatedMedia.findIndex(m => m.job_id === media.job_id);
             
             if (existingIndex !== -1) {
               updatedMedia = [
                 ...updatedMedia.slice(0, existingIndex),
                 { ...updatedMedia[existingIndex], ...media },
                 ...updatedMedia.slice(existingIndex + 1)
               ];
             } else {
               updatedMedia = [...updatedMedia, media];
             }
             
             return [...prev.slice(0, -1), { ...last, media: updatedMedia }];
           }
           return prev;
         });
      },
      // onDone
      () => {
        setIsTyping(false);
        // Finaliza a mensagem mudando o ID
        setMessages(prev => {
           const last = prev[prev.length - 1];
           if (last && last.id === "streaming-res") {
             return [...prev.slice(0, -1), { ...last, id: Date.now().toString() }];
           }
           return prev;
        });
      },
      // onError
      (err) => {
        console.error("Erro no chat:", err);
        setIsTyping(false);
        setMessages(prev => [...prev, {
          id: `err-${Date.now()}`,
          role: "system",
          content: "Erro na conexão com o servidor da Lira.",
          timestamp: new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
        }]);
      }
    );

    wsRef.current = ws;
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handlePaste = (e: React.ClipboardEvent) => {
    const items = e.clipboardData?.items;
    if (!items) return;

    for (let i = 0; i < items.length; i++) {
      if (items[i].type.indexOf("image") !== -1) {
        const file = items[i].getAsFile();
        if (file) {
          const reader = new FileReader();
          reader.onload = (ev) => {
            const base64 = ev.target?.result as string;
            setAttachments(prev => [...prev, { name: "pasted_image.png", data: base64, type: "image/png" }]);
          };
          reader.readAsDataURL(file);
        }
      }
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;

    Array.from(files).forEach(file => {
      const reader = new FileReader();
      reader.onload = (ev) => {
        const base64 = ev.target?.result as string;
        setAttachments(prev => [...prev, { name: file.name, data: base64, type: file.type }]);
      };
      reader.readAsDataURL(file);
    });
  };

  const removeAttachment = (index: number) => {
    setAttachments(prev => prev.filter((_, i) => i !== index));
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    const files = e.dataTransfer.files;
    if (!files) return;

    Array.from(files).forEach(file => {
      if (file.type.startsWith("image/")) {
        const reader = new FileReader();
        reader.onload = (ev) => {
          const base64 = ev.target?.result as string;
          setAttachments(prev => [...prev, { name: file.name, data: base64, type: file.type }]);
        };
        reader.readAsDataURL(file);
      }
    });
  };

  return (
    <div 
      className="w-full h-full bg-[var(--bg-sidebar)] backdrop-blur-2xl border border-[var(--border-strong)] rounded-2xl overflow-hidden shadow-2xl relative flex flex-col"
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {/* Overlay Drag & Drop */}
      {isDragging && (
        <div className="absolute inset-0 bg-[var(--purple-dark)]/80 backdrop-blur-md z-50 flex items-center justify-center border-[3px] border-dashed border-[var(--purple-neon)] m-4 rounded-xl transition-all">
           <div className="flex flex-col items-center justify-center p-12 bg-black/40 rounded-2xl animate-pulse">
             <div className="w-20 h-20 bg-[var(--purple-neon)]/20 text-[var(--purple-neon)] rounded-full flex items-center justify-center mb-4 border border-[var(--purple-neon)]">
               <Paperclip size={40} />
             </div>
             <h2 className="text-3xl font-extrabold text-white mb-2 tracking-widest uppercase">Soltar Imagem Aqui</h2>
             <p className="text-[var(--cyan-neon)] font-mono">A visão da Lira irá processar o arquivo</p>
           </div>
        </div>
      )}
      
      {/* HEADER / TOOLBAR */}
      <div className="bg-[rgba(10,10,15,0.85)] border-b border-[var(--border-strong)] p-4 z-10 shadow-lg backdrop-blur-md">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-[var(--purple-dark)] flex items-center justify-center border border-[var(--purple-neon)] shadow-[0_0_15px_var(--purple-dark)]">
              <MessageSquareText size={20} className="text-[var(--purple-neon)]" />
            </div>
            <div>
              <h2 className="text-xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-[var(--purple-neon)] to-[var(--cyan-neon)]">
                Lira Nexus Chat
              </h2>
              <p className="text-[10px] text-[var(--text-muted)] uppercase tracking-widest font-bold">Protocol v2.0 • Online</p>
            </div>
          </div>
          
          <div className="flex items-center gap-3 bg-[rgba(0,0,0,0.4)] p-1.5 rounded-2xl border border-[rgba(255,255,255,0.05)] shadow-inner">
            <div className="flex items-center gap-2 px-3 py-1 bg-[rgba(255,255,255,0.03)] rounded-xl border border-[rgba(255,255,255,0.05)]">
              <Terminal size={14} className="text-[var(--purple-neon)]" />
              <select 
                className="bg-transparent text-[var(--text-primary)] outline-none font-mono text-[11px] font-bold cursor-pointer uppercase"
                value={provider}
                onChange={(e) => setProvider(e.target.value)}
              >
                {LLM_PROVIDERS.map(p => <option key={p} value={p} className="bg-[#0f0f13]">{p}</option>)}
              </select>
            </div>

            <div className="flex items-center gap-2 px-3 py-1 bg-[rgba(255,255,255,0.03)] rounded-xl border border-[rgba(255,255,255,0.05)]">
              <BrainCircuit size={14} className="text-[var(--cyan-neon)]" />
              <select 
                className="bg-transparent text-[var(--text-primary)] outline-none font-mono text-[11px] font-bold cursor-pointer w-32 truncate"
                value={model}
                onChange={(e) => setModel(e.target.value)}
              >
                {availableModels.map(m => <option key={m.id} value={m.id} className="bg-[#0f0f13]">{m.label}</option>)}
              </select>
            </div>

            {isTyping && (
              <button 
                onClick={stopCurrentResponse}
                className="ml-1 bg-red-500/20 hover:bg-red-500/40 text-red-400 border border-red-500/30 transition-all p-2 rounded-xl animate-pulse"
                title="Parar Resposta"
              >
                <StopCircle size={18} />
              </button>
            )}
          </div>
        </div>
      </div>

      {/* CHAT AREA */}
      <div 
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-6 space-y-8 custom-scrollbar relative"
      >
        {/* Marca d'água */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 opacity-[0.03] pointer-events-none select-none">
          <img src="/lira_foto_01.png" alt="" className="w-[500px] grayscale" />
        </div>

        {messages.map((msg) => (
          <div key={msg.id} className={`flex w-full animate-fade-in ${msg.role === 'user' ? 'justify-end' : (msg.role === 'system' ? 'justify-center' : 'justify-start')}`}>
            
            {msg.role === 'system' && (
              <div className="bg-[rgba(255,255,255,0.03)] border border-[var(--border-strong)] text-[var(--text-muted)] text-[10px] px-6 py-2 rounded-full font-mono tracking-tighter uppercase backdrop-blur-sm shadow-sm">
                {msg.content}
              </div>
            )}

            {msg.role === 'user' && (
              <div className="flex flex-col items-end gap-2 max-w-[80%]">
                <div className="flex items-center gap-2 mb-1 px-1">
                  <span className="text-[10px] font-mono text-[var(--text-muted)]">{msg.timestamp}</span>
                  <span className="text-xs font-black text-blue-400 uppercase tracking-widest">Você</span>
                  <div className="w-6 h-6 rounded-full bg-blue-500/20 border border-blue-500/40 flex items-center justify-center">
                    <User size={12} className="text-blue-400" />
                  </div>
                </div>
                
                <div className="bg-[rgba(59,130,246,0.1)] border border-blue-500/30 rounded-3xl rounded-tr-none p-5 shadow-[0_10px_30px_rgba(0,0,0,0.3)] backdrop-blur-xl group relative">
                  {/* Miniaturas de anexos enviados */}
                  {msg.attachments && msg.attachments.length > 0 && (
                    <div className="flex flex-wrap gap-2 mb-4">
                      {msg.attachments.map((att, i) => (
                        <div key={i} className="w-24 h-24 rounded-xl overflow-hidden border border-white/10 shadow-lg group/img">
                          <img src={att} className="w-full h-full object-cover transition-transform group-hover/img:scale-110" alt="Anexo" />
                        </div>
                      ))}
                    </div>
                  )}
                  <p className="text-[15px] text-[var(--text-primary)] leading-relaxed whitespace-pre-wrap font-medium">{msg.content}</p>
                </div>
              </div>
            )}

            {msg.role === 'lira' && (
              <div className="flex flex-col items-start gap-2 max-w-[85%]">
                <div className="flex items-center gap-2 mb-1 px-1">
                  <div className="w-8 h-8 rounded-full bg-[var(--purple-dark)] border border-[var(--purple-neon)] flex items-center justify-center shadow-[0_0_10px_var(--purple-dark)] overflow-hidden">
                    <img src="/lira_perfil.png" className="w-full h-full object-cover" alt="H" />
                  </div>
                  <span className="text-xs font-black text-[var(--purple-neon)] uppercase tracking-[0.2em] drop-shadow-[0_0_5px_var(--purple-dark)]">Lira Amarinth</span>
                  <span className="text-[10px] font-mono text-[var(--text-muted)]">{msg.timestamp}</span>
                </div>
                
                <div className="bg-[rgba(168,85,247,0.08)] border border-[var(--purple-neon)]/20 rounded-3xl rounded-tl-none p-6 shadow-[0_15px_40px_rgba(0,0,0,0.4)] backdrop-blur-2xl relative group/lira overflow-hidden">
                  {/* Brilho interno animado */}
                  <div className="absolute -top-20 -left-20 w-40 h-40 bg-[var(--purple-neon)] rounded-full blur-[100px] opacity-10 pointer-events-none"></div>

                  {msg.meta && (
                    <div className="mb-4 text-[9px] font-bold font-mono text-[var(--text-muted)] flex items-center gap-3">
                      <span className="bg-black/40 px-3 py-1 rounded-full border border-white/5 uppercase tracking-widest">{msg.meta.provider} • {msg.meta.model}</span>
                      {msg.meta.tokens && <span className="bg-[var(--purple-dark)] text-[var(--purple-neon)] px-3 py-1 rounded-full border border-[var(--purple-neon)]/20">{msg.meta.tokens} TOKENS</span>}
                    </div>
                  )}
                  
                  <div className="prose prose-invert prose-sm max-w-none prose-p:leading-relaxed prose-pre:bg-black/50 prose-pre:border prose-pre:border-white/10 prose-code:text-[var(--cyan-neon)] prose-a:text-[var(--cyan-neon)] prose-a:no-underline hover:prose-a:underline">
                    <ReactMarkdown 
                      remarkPlugins={[remarkGfm, remarkBreaks]}
                      components={{
                        a: ({node, ...props}) => <a {...props} target="_blank" rel="noreferrer" className="flex items-center gap-1 inline-flex" />
                      }}
                    >
                      {msg.content.replace(/\[EMOTION:.*?\]/gi, '').replace(/\[PARAM:.*?\]/gi, '').trim()}
                    </ReactMarkdown>
                  </div>

                  {/* Renderização de Mídias */}
                  {msg.media && msg.media.map((m, i) => (
                    <MediaRenderer key={i} media={m} />
                  ))}

                  {/* Action Buttons Footer */}
                  <div className="mt-5 pt-4 border-t border-white/5 opacity-0 group-hover/lira:opacity-100 transition-all duration-300 flex items-center gap-3">
                    <button
                      onClick={() => ApiController.speakText(msg.content)}
                      className="text-[10px] font-bold uppercase tracking-widest bg-white/5 hover:bg-[var(--purple-dark)] text-[var(--text-secondary)] hover:text-white px-4 py-2 rounded-full border border-white/5 transition-all flex items-center gap-2"
                    >
                      <Volume2 size={12} /> Ouvir Voz
                    </button>
                    <button className="text-[10px] font-bold uppercase tracking-widest bg-white/5 hover:bg-[var(--purple-dark)] text-[var(--text-secondary)] hover:text-white px-4 py-2 rounded-full border border-white/5 transition-all flex items-center gap-2">
                      <Copy size={12} /> Copiar
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        ))}

        {isTyping && !currentResponseRef.current && (
          <div className="flex w-full justify-start animate-fade-in">
             <div className="flex flex-col items-start gap-2">
                <div className="flex items-center gap-2 mb-1 px-1">
                   <div className="w-8 h-8 rounded-full bg-[var(--purple-dark)] border border-[var(--purple-neon)] flex items-center justify-center animate-pulse">
                      <Bot size={14} className="text-[var(--purple-neon)]" />
                   </div>
                   <span className="text-[10px] font-black text-[var(--purple-neon)] uppercase tracking-widest animate-pulse">Lira está digitando...</span>
                </div>
                <div className="bg-white/5 border border-white/10 rounded-2xl p-4 flex items-center gap-1.5 shadow-xl">
                  <div className="w-1.5 h-1.5 rounded-full bg-[var(--purple-neon)] animate-bounce" style={{ animationDelay: '0ms' }}></div>
                  <div className="w-1.5 h-1.5 rounded-full bg-[var(--purple-neon)] animate-bounce" style={{ animationDelay: '150ms' }}></div>
                  <div className="w-1.5 h-1.5 rounded-full bg-[var(--purple-neon)] animate-bounce" style={{ animationDelay: '300ms' }}></div>
                </div>
             </div>
          </div>
        )}
      </div>

      {/* INPUT AREA */}
      <div className="bg-[rgba(10,10,15,0.9)] border-t border-[var(--border-strong)] p-6 z-10 backdrop-blur-xl relative">
        
        <div className="flex items-end gap-4 max-w-6xl mx-auto">
          <div className="flex gap-2 mb-1 shrink-0">
            <button className="w-12 h-12 flex items-center justify-center rounded-2xl bg-white/5 hover:bg-[var(--purple-dark)] border border-white/5 hover:border-[var(--purple-neon)]/30 text-[var(--text-secondary)] hover:text-[var(--purple-neon)] transition-all shadow-lg group">
              <Mic size={20} className="group-hover:scale-110 transition-transform" />
            </button>
            
            <label className="w-12 h-12 flex items-center justify-center rounded-2xl bg-white/5 hover:bg-blue-500/10 border border-white/5 hover:border-blue-500/30 text-[var(--text-secondary)] hover:text-blue-400 transition-all shadow-lg cursor-pointer group">
              <Paperclip size={20} className="group-hover:rotate-45 transition-transform" />
              <input type="file" className="hidden" multiple accept="image/*" onChange={handleFileUpload} />
            </label>
          </div>

          <div className="flex-1 bg-[rgba(0,0,0,0.5)] border border-[var(--border-strong)] rounded-[1.5rem] p-1.5 relative group focus-within:border-[var(--purple-neon)] focus-within:shadow-[0_0_40px_rgba(168,85,247,0.2)] transition-all duration-500 shadow-2xl flex flex-col">
            
            {/* Preview de Anexos dentro da caixa de texto */}
            {attachments.length > 0 && (
              <div className="flex flex-wrap gap-2 p-3 pb-0 animate-fade-in">
                {attachments.map((att, i) => (
                  <div key={i} className="group/att relative w-12 h-12 rounded-lg border border-[var(--purple-neon)]/30 overflow-hidden shadow-lg">
                    <img src={att.data} className="w-full h-full object-cover" alt="preview" />
                    <button 
                      onClick={() => removeAttachment(i)}
                      className="absolute top-0.5 right-0.5 bg-red-500 rounded-full w-4 h-4 flex items-center justify-center text-white text-[10px] font-bold opacity-0 group-hover/att:opacity-100 transition-opacity"
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
            )}

            <textarea 
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              onPaste={handlePaste}
              className="w-full bg-transparent text-[var(--text-primary)] text-[15px] resize-none outline-none custom-scrollbar p-3 pl-5 max-h-60 min-h-[54px] font-medium placeholder:text-[var(--text-muted)] leading-relaxed"
              placeholder={attachments.length > 0 ? "Adicione uma descrição para a imagem..." : "Fale com a Lira Amarinth... (Ou arraste imagens para aqui)"}
              rows={1}
            />
          </div>

          <button 
            onClick={handleSend}
            disabled={(!input.trim() && attachments.length === 0) || isTyping}
            className="w-[60px] h-[60px] bg-gradient-to-br from-[var(--purple-neon)] to-[#7e22ce] hover:brightness-110 disabled:from-gray-800 disabled:to-gray-900 text-white disabled:text-gray-600 rounded-[1.2rem] flex items-center justify-center transition-all shadow-[0_10px_25px_rgba(168,85,247,0.4)] hover:shadow-[0_15px_35px_rgba(168,85,247,0.6)] active:scale-90 shrink-0 mb-0.5 border border-white/10"
          >
            <Send size={24} className={isTyping ? "animate-spin-slow" : ""} />
          </button>
        </div>
        
        <div className="text-[9px] text-center text-[var(--text-muted)] mt-4 font-bold uppercase tracking-[0.3em] opacity-30">
          Neural Interface Active • Secure Connection
        </div>
      </div>

    </div>
  );
}
