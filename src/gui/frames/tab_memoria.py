"""
Tab Memória — Visualizador do Knowledge Graph + Editor de Fatos.
Conecta diretamente aos arquivos persistentes em disco (NetworkX GML + ChromaDB).
"""

import customtkinter as ctk
import logging

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from src.gui.design import COLORS, FONT_TITLE, FONT_BODY, FONT_SMALL, FONT_MONO

logger = logging.getLogger(__name__)

# Caminhos dos dados persistentes
BASE_PROJECT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
GRAPH_PATH = os.path.join(BASE_PROJECT, "data", "memory", "knowledge_graph.gml")
CHROMA_PATH = os.path.join(BASE_PROJECT, "data", "memory", "chroma_db")


class TabMemoria(ctk.CTkFrame):
    """Painel de Memória: Visualizador do Grafo de Conhecimento + Memórias RAG."""

    def __init__(self, master, **kwargs):
        super().__init__(master, corner_radius=12, fg_color=COLORS["bg_dark"], border_width=1, border_color=COLORS["border"])
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # Conexões diretas aos arquivos persistentes
        self._knowledge_graph = None
        self._rag_engine = None
        self._sqlite_memory = None
        self._auto_connect()

        # ─── HEADER ───
        header = ctk.CTkLabel(self, text="🧠  Memória Neural-Graph", font=FONT_TITLE, text_color=COLORS["text_primary"])
        header.grid(row=0, column=0, columnspan=2, padx=25, pady=(20, 5), sticky="w")
        sub = ctk.CTkLabel(self, text="Grafo de Conhecimento (Fatos Permanentes) + Memórias Semânticas (ChromaDB)", font=FONT_SMALL, text_color=COLORS["text_muted"])
        sub.grid(row=1, column=0, columnspan=2, padx=25, pady=(0, 15), sticky="w")

        # ═══ COLUNA ESQUERDA: Fatos do Grafo ═══
        card_fatos = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=10, border_width=1, border_color=COLORS["border"])
        card_fatos.grid(row=2, column=0, padx=(15, 8), pady=8, sticky="nsew")
        self.grid_rowconfigure(2, weight=1)

        lbl_fatos = ctk.CTkLabel(card_fatos, text="📊  Grafo de Conhecimento", font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), text_color=COLORS["text_primary"])
        lbl_fatos.pack(anchor="w", padx=15, pady=(12, 5))

        lbl_sub = ctk.CTkLabel(card_fatos, text="Fatos salvos permanentemente pela Hana", font=FONT_SMALL, text_color=COLORS["text_muted"])
        lbl_sub.pack(anchor="w", padx=15, pady=(0, 8))

        # Status do grafo
        self.lbl_stats = ctk.CTkLabel(card_fatos, text="Nós: 0  |  Conexões: 0", font=FONT_SMALL, text_color=COLORS["purple_neon"])
        self.lbl_stats.pack(anchor="w", padx=15, pady=(0, 5))

        # Lista de fatos (scrollable)
        self.fatos_scroll = ctk.CTkScrollableFrame(
            card_fatos, fg_color=COLORS["bg_darkest"],
            corner_radius=8, border_width=1, border_color=COLORS["border"]
        )
        self.fatos_scroll.pack(fill="both", expand=True, padx=12, pady=(5, 8))

        # Botões de ação
        btn_frame = ctk.CTkFrame(card_fatos, fg_color="transparent")
        btn_frame.pack(fill="x", padx=12, pady=(0, 12))

        btn_refresh = ctk.CTkButton(
            btn_frame, text="↻  Recarregar", width=120,
            fg_color=COLORS["bg_darkest"], hover_color=COLORS["blue_dim"],
            text_color=COLORS["text_secondary"], border_width=1, border_color=COLORS["border"],
            command=self._listar_fatos
        )
        btn_refresh.pack(side="left", padx=(0, 8))

        # ═══ LINHA INFERIOR: Histórico de Conversas (SQLite) ═══
        card_hist = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=10, border_width=1, border_color=COLORS["border"])
        card_hist.grid(row=3, column=0, columnspan=2, padx=15, pady=(0, 8), sticky="nsew")
        self.grid_rowconfigure(3, weight=1)

        hist_header = ctk.CTkFrame(card_hist, fg_color="transparent")
        hist_header.pack(fill="x", padx=15, pady=(12, 5))

        ctk.CTkLabel(hist_header, text="💬  Histórico de Conversas", font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), text_color=COLORS["text_primary"]).pack(side="left")

        self.lbl_hist_count = ctk.CTkLabel(hist_header, text="0 mensagens", font=FONT_SMALL, text_color=COLORS["text_muted"])
        self.lbl_hist_count.pack(side="right", padx=10)

        btn_refresh_hist = ctk.CTkButton(
            hist_header, text="↻", width=30, height=28,
            fg_color=COLORS["bg_darkest"], hover_color=COLORS["blue_dim"],
            text_color=COLORS["text_secondary"], border_width=1, border_color=COLORS["border"],
            command=self._carregar_historico
        )
        btn_refresh_hist.pack(side="right")

        self.hist_scroll = ctk.CTkScrollableFrame(
            card_hist, fg_color=COLORS["bg_darkest"],
            corner_radius=8, border_width=1, border_color=COLORS["border"]
        )
        self.hist_scroll.pack(fill="both", expand=True, padx=12, pady=(5, 12))

        # ═══ COLUNA DIREITA: Adicionar Fato Manual ═══
        card_add = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=10, border_width=1, border_color=COLORS["border"])
        card_add.grid(row=2, column=1, padx=(8, 15), pady=8, sticky="nsew")

        lbl_add = ctk.CTkLabel(card_add, text="➕  Adicionar Fato Manual", font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), text_color=COLORS["text_primary"])
        lbl_add.pack(anchor="w", padx=15, pady=(12, 5))

        lbl_add_sub = ctk.CTkLabel(card_add, text="Ensine algo à Hana que ela nunca esquecerá", font=FONT_SMALL, text_color=COLORS["text_muted"])
        lbl_add_sub.pack(anchor="w", padx=15, pady=(0, 15))

        # Campo: Sujeito
        ctk.CTkLabel(card_add, text="Sujeito", font=FONT_SMALL, text_color=COLORS["text_secondary"]).pack(anchor="w", padx=15, pady=(5, 2))
        self.entry_sujeito = ctk.CTkEntry(
            card_add, placeholder_text="Ex: Nakamura, Hana, Gato...",
            fg_color=COLORS["bg_darkest"], border_color=COLORS["border"],
            text_color=COLORS["text_primary"], font=FONT_BODY
        )
        self.entry_sujeito.pack(fill="x", padx=15, pady=(0, 8))

        # Campo: Relação
        ctk.CTkLabel(card_add, text="Relação", font=FONT_SMALL, text_color=COLORS["text_secondary"]).pack(anchor="w", padx=15, pady=(5, 2))
        self.entry_relacao = ctk.CTkEntry(
            card_add, placeholder_text="Ex: gosta_de, mora_em, tem_nome...",
            fg_color=COLORS["bg_darkest"], border_color=COLORS["border"],
            text_color=COLORS["text_primary"], font=FONT_BODY
        )
        self.entry_relacao.pack(fill="x", padx=15, pady=(0, 8))

        # Campo: Objeto
        ctk.CTkLabel(card_add, text="Objeto", font=FONT_SMALL, text_color=COLORS["text_secondary"]).pack(anchor="w", padx=15, pady=(5, 2))
        self.entry_objeto = ctk.CTkEntry(
            card_add, placeholder_text="Ex: Morango, São Paulo, Mimi...",
            fg_color=COLORS["bg_darkest"], border_color=COLORS["border"],
            text_color=COLORS["text_primary"], font=FONT_BODY
        )
        self.entry_objeto.pack(fill="x", padx=15, pady=(0, 15))

        # Botão Salvar
        self.btn_salvar = ctk.CTkButton(
            card_add, text="💾  Salvar Fato Permanente", height=40,
            fg_color=COLORS["purple_dim"], hover_color=COLORS["purple_neon"],
            text_color="white", font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            command=self._salvar_fato
        )
        self.btn_salvar.pack(fill="x", padx=15, pady=(5, 8))

        # Status
        self.lbl_status = ctk.CTkLabel(card_add, text="", font=FONT_SMALL, text_color=COLORS["green"])
        self.lbl_status.pack(anchor="w", padx=15, pady=(0, 15))

        # ─── Seção: Busca Semântica (RAG) ───
        card_rag = ctk.CTkFrame(card_add, fg_color=COLORS["bg_darkest"], corner_radius=8, border_width=1, border_color=COLORS["border"])
        card_rag.pack(fill="both", expand=True, padx=12, pady=(10, 12))

        ctk.CTkLabel(card_rag, text="🔍  Busca Semântica (RAG)", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color=COLORS["text_primary"]).pack(anchor="w", padx=12, pady=(10, 5))

        search_frame = ctk.CTkFrame(card_rag, fg_color="transparent")
        search_frame.pack(fill="x", padx=12, pady=(0, 5))

        self.entry_busca_rag = ctk.CTkEntry(
            search_frame, placeholder_text="Buscar nas memórias antigas...",
            fg_color=COLORS["bg_card"], border_color=COLORS["border"],
            text_color=COLORS["text_primary"], font=FONT_BODY
        )
        self.entry_busca_rag.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.entry_busca_rag.bind("<Return>", lambda e: self._buscar_rag())

        btn_buscar = ctk.CTkButton(
            search_frame, text="Buscar", width=80,
            fg_color=COLORS["blue_dim"], hover_color=COLORS["blue_neon"],
            command=self._buscar_rag
        )
        btn_buscar.pack(side="right")

        self.rag_results = ctk.CTkTextbox(
            card_rag, font=FONT_MONO, height=120,
            fg_color=COLORS["bg_card"],
            text_color=COLORS["text_secondary"],
            border_width=0, corner_radius=6
        )
        self.rag_results.pack(fill="both", expand=True, padx=12, pady=(5, 12))

    # ─── AUTO-CONEXÃO AOS ARQUIVOS PERSISTENTES ───

    def _auto_connect(self):
        """Conecta diretamente ao grafo GML, ChromaDB e SQLite no disco."""
        try:
            from src.memory.knowledge_graph import HanaKnowledgeGraph
            self._knowledge_graph = HanaKnowledgeGraph(persist_path=GRAPH_PATH)
        except Exception as e:
            logger.warning(f"[TAB MEMORIA] Não foi possível conectar ao grafo: {e}")
            self._knowledge_graph = None

        try:
            from src.memory.rag_engine import HanaRAGEngine
            self._rag_engine = HanaRAGEngine(persist_directory=CHROMA_PATH)
        except Exception as e:
            logger.warning(f"[TAB MEMORIA] Não foi possível conectar ao RAG: {e}")
            self._rag_engine = None

        try:
            import sqlite3
            db_path = os.path.join(BASE_PROJECT, "data", "hana_memory.db")
            if os.path.exists(db_path):
                self._sqlite_path = db_path
            else:
                self._sqlite_path = None
        except Exception as e:
            logger.warning(f"[TAB MEMORIA] SQLite não encontrado: {e}")
            self._sqlite_path = None

    # ─── FATOS DO GRAFO ───

    def _listar_fatos(self):
        """Lista todos os fatos do Knowledge Graph."""
        # Reconecta para pegar dados frescos do disco
        self._auto_connect()
        
        # Limpa a lista anterior
        for widget in self.fatos_scroll.winfo_children():
            widget.destroy()

        if not self._knowledge_graph:
            lbl = ctk.CTkLabel(self.fatos_scroll, text="Sistema de memória não conectado.\nInicie a Hana (main.py) primeiro.", font=FONT_SMALL, text_color=COLORS["text_muted"])
            lbl.pack(pady=20)
            self.lbl_stats.configure(text="Nós: 0  |  Conexões: 0")
            return

        graph = self._knowledge_graph.graph
        num_nodes = graph.number_of_nodes()
        num_edges = graph.number_of_edges()
        self.lbl_stats.configure(text=f"Nós: {num_nodes}  |  Conexões: {num_edges}")

        if num_edges == 0:
            lbl = ctk.CTkLabel(self.fatos_scroll, text="Nenhum fato salvo ainda.\nPeça à Hana para decorar algo!", font=FONT_SMALL, text_color=COLORS["text_muted"])
            lbl.pack(pady=20)
            return

        for s, o, data in graph.edges(data=True):
            rel = data.get("relation", "?")
            row = ctk.CTkFrame(self.fatos_scroll, fg_color=COLORS["bg_card"], corner_radius=6, height=40)
            row.pack(fill="x", padx=4, pady=3)

            tripla = f"({s})  →  [{rel}]  →  ({o})"
            lbl = ctk.CTkLabel(row, text=tripla, font=FONT_MONO, text_color=COLORS["purple_neon"], anchor="w")
            lbl.pack(side="left", padx=10, pady=6, fill="x", expand=True)

            btn_del = ctk.CTkButton(
                row, text="🗑", width=30, height=28,
                fg_color=COLORS["bg_darkest"], hover_color=COLORS.get("red", "#ef4444"),
                text_color=COLORS["text_muted"],
                command=lambda subj=s, obj=o: self._deletar_fato(subj, obj)
            )
            btn_del.pack(side="right", padx=(0, 8))

    def _salvar_fato(self):
        """Salva um novo fato no Knowledge Graph."""
        s = self.entry_sujeito.get().strip()
        r = self.entry_relacao.get().strip()
        o = self.entry_objeto.get().strip()

        if not (s and r and o):
            self.lbl_status.configure(text="Preencha todos os campos!", text_color=COLORS.get("red", "#ef4444"))
            return

        if not self._knowledge_graph:
            self.lbl_status.configure(text="Sistema de memória não conectado.", text_color=COLORS.get("red", "#ef4444"))
            return

        try:
            self._knowledge_graph.add_fact(s, r, o)
            self.lbl_status.configure(text=f"✓ Fato salvo: {s} [{r}] {o}", text_color=COLORS["green"])
            # Limpa os campos
            self.entry_sujeito.delete(0, "end")
            self.entry_relacao.delete(0, "end")
            self.entry_objeto.delete(0, "end")
            # Atualiza a lista
            self._listar_fatos()
        except Exception as e:
            self.lbl_status.configure(text=f"Erro: {e}", text_color=COLORS.get("red", "#ef4444"))

    def _deletar_fato(self, subject, obj):
        """Remove um fato (aresta) do grafo."""
        if not self._knowledge_graph:
            return
        try:
            self._knowledge_graph.graph.remove_edge(subject, obj)
            self._knowledge_graph.save()
            self._listar_fatos()
        except Exception:
            pass

    # ─── HISTÓRICO SQLITE ───

    def _carregar_historico(self):
        """Carrega as últimas mensagens do SQLite e exibe no painel."""
        for widget in self.hist_scroll.winfo_children():
            widget.destroy()

        if not getattr(self, '_sqlite_path', None):
            lbl = ctk.CTkLabel(self.hist_scroll, text="Banco de dados não encontrado.", font=FONT_SMALL, text_color=COLORS["text_muted"])
            lbl.pack(pady=20)
            self.lbl_hist_count.configure(text="0 mensagens")
            return

        try:
            import sqlite3
            conn = sqlite3.connect(self._sqlite_path)
            cursor = conn.cursor()
            cursor.execute("SELECT role, content, timestamp FROM messages ORDER BY id DESC LIMIT 50")
            rows = cursor.fetchall()
            conn.close()

            self.lbl_hist_count.configure(text=f"{len(rows)} mensagens")

            if not rows:
                lbl = ctk.CTkLabel(self.hist_scroll, text="Nenhuma mensagem no histórico.", font=FONT_SMALL, text_color=COLORS["text_muted"])
                lbl.pack(pady=20)
                return

            for role, content, ts in rows:
                row = ctk.CTkFrame(self.hist_scroll, fg_color=COLORS["bg_card"], corner_radius=6)
                row.pack(fill="x", padx=4, pady=2)

                color = COLORS["purple_neon"] if role and role.lower() == "hana" else COLORS["blue_neon"]
                display_role = role or "?"
                preview = (content or "")[:120].replace("\n", " ")

                lbl_role = ctk.CTkLabel(row, text=f"[{display_role}]", font=FONT_MONO, text_color=color, width=90, anchor="w")
                lbl_role.pack(side="left", padx=(10, 5), pady=5)

                lbl_msg = ctk.CTkLabel(row, text=preview, font=FONT_SMALL, text_color=COLORS["text_secondary"], anchor="w")
                lbl_msg.pack(side="left", fill="x", expand=True, padx=(0, 10), pady=5)

        except Exception as e:
            lbl = ctk.CTkLabel(self.hist_scroll, text=f"Erro ao carregar: {e}", font=FONT_SMALL, text_color=COLORS["red"])
            lbl.pack(pady=20)

    # ─── BUSCA RAG ───

    def _buscar_rag(self):
        """Busca memórias semânticas via ChromaDB."""
        query = self.entry_busca_rag.get().strip()
        if not query:
            return

        self.rag_results.delete("1.0", "end")

        if not self._rag_engine:
            self.rag_results.insert("1.0", "Motor RAG não conectado.")
            return

        try:
            results = self._rag_engine.query_memories_with_scores(query, n_results=5)
            if not results:
                self.rag_results.insert("1.0", "Nenhuma memória encontrada para essa busca.")
                return

            threshold = self._rag_engine.MAX_DISTANCE
            for i, (mem, dist) in enumerate(results, 1):
                similarity = max(0, (1 - dist)) * 100
                tag = "✅" if dist <= threshold else "⚠️"
                self.rag_results.insert("end", f"[{i}] {tag} ({similarity:.0f}% similar)\n{mem}\n\n")
        except Exception as e:
            self.rag_results.insert("1.0", f"Erro na busca: {e}")
