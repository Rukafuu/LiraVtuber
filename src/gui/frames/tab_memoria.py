"""
Tab Memória & Prompts — Editor multi-arquivos (core_memory, prompts) + Fatos Exatos.
"""

import json
import os
import customtkinter as ctk

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from src.gui.design import COLORS, FONT_TITLE, FONT_BODY, FONT_SMALL, FONT_MONO

BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "..")

# Dicionário de arquivos gerenciáveis pelo editor
ARQUIVOS_PROMPT = {
    "Core Memory (O Johnson) [JSON]": os.path.join(BASE_DIR, "memory", "core_memory.json"),
    "Prompt Principal (nyra_prompt.txt)": os.path.join(BASE_DIR, "..", "data", "persona", "nyra_prompt.txt"),
    "Prompt Terminal Chat (prompt_terminal.txt)": os.path.join(BASE_DIR, "..", "data", "persona", "prompt_terminal.txt"),
}

class TabMemoria(ctk.CTkFrame):
    """Cofre GraphRAG V2 + Gestor de Prompts."""

    def __init__(self, master, runtime=None):
        super().__init__(master, corner_radius=12, fg_color=COLORS["bg_dark"], border_width=1, border_color=COLORS["border"])
        self.runtime = runtime
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # ─── HEADER ───
        header = ctk.CTkLabel(self, text="Memória & Prompts", font=FONT_TITLE, text_color=COLORS["text_primary"])
        header.grid(row=0, column=0, columnspan=2, padx=25, pady=(20, 5), sticky="w")
        sub = ctk.CTkLabel(self, text="Core Memory (Johnson) + Editor de Prompts + Fatos Exatos (Triplas)", font=FONT_SMALL, text_color=COLORS["text_muted"])
        sub.grid(row=1, column=0, columnspan=2, padx=25, pady=(0, 15), sticky="w")

        # ═══ COLUNA ESQUERDA: Editor de Arquivos ═══
        card_editor = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=10, border_width=1, border_color=COLORS["border"])
        card_editor.grid(row=2, column=0, padx=(15, 8), pady=8, sticky="nsew")
        self.grid_rowconfigure(2, weight=1)

        # Topo do Editor (Combo Box)
        top_frame = ctk.CTkFrame(card_editor, fg_color="transparent")
        top_frame.pack(fill="x", padx=15, pady=(12, 5))
        
        ctk.CTkLabel(top_frame, text="📋 Arquivo:", font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), text_color=COLORS["text_primary"]).pack(side="left", padx=(0, 10))
        
        self.combo_arquivo = ctk.CTkComboBox(
            top_frame, values=list(ARQUIVOS_PROMPT.keys()), width=300,
            fg_color=COLORS["bg_darkest"], border_color=COLORS["border"],
            button_color=COLORS["purple_dim"], button_hover_color=COLORS["purple_neon"],
            dropdown_fg_color=COLORS["bg_card"], dropdown_hover_color=COLORS["purple_dark"],
            text_color=COLORS["text_primary"], font=FONT_SMALL,
            command=self._on_arquivo_selecionado
        )
        self.combo_arquivo.pack(side="left")

        # Area de Texto do Editor
        self.editor = ctk.CTkTextbox(
            card_editor, font=FONT_MONO,
            fg_color=COLORS["bg_darkest"],
            text_color=COLORS["text_primary"],
            border_width=1, border_color=COLORS["border"],
            corner_radius=8
        )
        self.editor.pack(fill="both", expand=True, padx=12, pady=(5, 8))

        # Botões do Editor
        btn_frame = ctk.CTkFrame(card_editor, fg_color="transparent")
        btn_frame.pack(fill="x", padx=12, pady=(0, 12))

        self.btn_recarregar = ctk.CTkButton(
            btn_frame, text="↻  Recarregar", width=120,
            fg_color=COLORS["bg_darkest"], hover_color=COLORS["blue_dim"],
            text_color=COLORS["text_secondary"], border_width=1, border_color=COLORS["border"],
            command=self._carregar_arquivo
        )
        self.btn_recarregar.pack(side="left", padx=(0, 8))

        self.btn_salvar = ctk.CTkButton(
            btn_frame, text="💾  Salvar", width=120,
            fg_color=COLORS["purple_dim"], hover_color=COLORS["purple_neon"],
            text_color="white",
            command=self._salvar_arquivo
        )
        self.btn_salvar.pack(side="left")

        self.lbl_status_editor = ctk.CTkLabel(btn_frame, text="", font=FONT_SMALL, text_color=COLORS["green"])
        self.lbl_status_editor.pack(side="right", padx=10)

        # ═══ COLUNA DIREITA: Fatos Exatos ═══
        card_fatos = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=10, border_width=1, border_color=COLORS["border"])
        card_fatos.grid(row=2, column=1, padx=(8, 15), pady=8, sticky="nsew")

        lbl_fatos = ctk.CTkLabel(card_fatos, text="🧠  Fatos Exatos  (Triplas)", font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), text_color=COLORS["text_primary"])
        lbl_fatos.pack(anchor="w", padx=15, pady=(12, 5))

        # Barra de busca
        search_frame = ctk.CTkFrame(card_fatos, fg_color="transparent")
        search_frame.pack(fill="x", padx=12, pady=(5, 5))

        self.entry_busca = ctk.CTkEntry(
            search_frame, placeholder_text="🔍  Buscar fatos...",
            fg_color=COLORS["bg_darkest"], border_color=COLORS["border"],
            text_color=COLORS["text_primary"], font=FONT_BODY
        )
        self.entry_busca.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.entry_busca.bind("<Return>", lambda e: self._buscar_fatos())

        btn_buscar = ctk.CTkButton(
            search_frame, text="Buscar", width=80,
            fg_color=COLORS["blue_dim"], hover_color=COLORS["blue_neon"],
            command=self._buscar_fatos
        )
        btn_buscar.pack(side="right")

        # Lista de fatos (scrollable)
        self.fatos_scroll = ctk.CTkScrollableFrame(
            card_fatos, fg_color=COLORS["bg_darkest"],
            corner_radius=8, border_width=1, border_color=COLORS["border"]
        )
        self.fatos_scroll.pack(fill="both", expand=True, padx=12, pady=(5, 8))
        self.fatos_scroll.grid_columnconfigure(0, weight=1)

        # Botão para listar todos
        btn_todos = ctk.CTkButton(
            card_fatos, text="📋  Listar Todos os Fatos", width=200,
            fg_color=COLORS["bg_darkest"], hover_color=COLORS["bg_card_hover"],
            text_color=COLORS["text_secondary"], border_width=1, border_color=COLORS["border"],
            command=self._listar_todos_fatos
        )
        btn_todos.pack(pady=(0, 12))

        # Inicializa Editor e BD
        self._carregar_arquivo()

    # ─── GESTOR DE PROMPTS E JSON ───

    def _on_arquivo_selecionado(self, choice):
        """Ao trocar o dropdown, carrega o arquivo."""
        self._carregar_arquivo()

    def _carregar_arquivo(self):
        """Lê o arquivo selecionado no dropdown e injeta no editor."""
        nome_selecionado = self.combo_arquivo.get()
        path = os.path.abspath(ARQUIVOS_PROMPT[nome_selecionado])
        
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    conteudo = f.read()
                self.editor.delete("1.0", "end")
                self.editor.insert("1.0", conteudo)
                self.lbl_status_editor.configure(text=f"✓ Carregado: {os.path.basename(path)}", text_color=COLORS["green"])
            else:
                self.editor.delete("1.0", "end")
                # Templates default dependendo se é JSON ou TXT
                if path.endswith(".json"):
                    self.editor.insert("1.0", '{\n  "identidade": {},\n  "fatos_absolutos": [],\n  "preferencias_mestre": {},\n  "regras_extras": []\n}')
                else:
                    self.editor.insert("1.0", "Você é a Nyra.")
                self.lbl_status_editor.configure(text="Arquivo não encontrado — template gerado", text_color=COLORS["yellow"])
        except Exception as e:
            self.lbl_status_editor.configure(text=f"Erro de leitura: {e}", text_color=COLORS["red"])

    def _salvar_arquivo(self):
        """Salva o buffer do editor no arquivo real no disco."""
        nome_selecionado = self.combo_arquivo.get()
        path = os.path.abspath(ARQUIVOS_PROMPT[nome_selecionado])
        texto = self.editor.get("1.0", "end").strip()
        
        try:
            # Se for JSON, tenta validar a integridade antes de salvar
            if path.endswith(".json"):
                dados = json.loads(texto)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(dados, f, ensure_ascii=False, indent=2)
            else:
                # Se for TXT (Prompt)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(texto)
                    
            self.lbl_status_editor.configure(text="✓ Salvo com sucesso!", text_color=COLORS["green"])
            
            # Avisa o runtime para recarregar as memórias/prompts na hora, se possível
            if self.runtime and self.runtime.contexto:
                self.runtime.contexto.system_prompt = self.runtime.contexto._carregar_system_prompt()
                
        except json.JSONDecodeError as e:
            self.lbl_status_editor.configure(text=f"Erro de formatação JSON: {e}", text_color=COLORS["red"])
        except Exception as e:
            self.lbl_status_editor.configure(text=f"Erro ao salvar: {e}", text_color=COLORS["red"])

    # ─── FATOS EXATOS ───

    def _limpar_lista_fatos(self):
        for widget in self.fatos_scroll.winfo_children():
            widget.destroy()

    def _renderizar_fatos(self, fatos: list):
        self._limpar_lista_fatos()
        if not fatos:
            lbl = ctk.CTkLabel(self.fatos_scroll, text="Nenhum fato encontrado.", font=FONT_SMALL, text_color=COLORS["text_muted"])
            lbl.pack(pady=20)
            return

        for i, fato in enumerate(fatos):
            row = ctk.CTkFrame(self.fatos_scroll, fg_color=COLORS["bg_card"], corner_radius=6, height=40)
            row.pack(fill="x", padx=4, pady=3)

            tripla = f"({fato.get('sujeito', '?')})  →  [{fato.get('relacao', '?')}]  →  ({fato.get('objeto', '?')})"
            lbl = ctk.CTkLabel(row, text=tripla, font=FONT_MONO, text_color=COLORS["purple_neon"], anchor="w")
            lbl.pack(side="left", padx=10, pady=6, fill="x", expand=True)

            conf = fato.get("confianca", 1.0)
            lbl_conf = ctk.CTkLabel(row, text=f"{conf:.0%}", font=FONT_SMALL, text_color=COLORS["green"] if conf >= 0.8 else COLORS["yellow"])
            lbl_conf.pack(side="right", padx=(5, 5))

            fato_id = fato.get("id")
            btn_del = ctk.CTkButton(
                row, text="🗑", width=30, height=28,
                fg_color=COLORS["bg_darkest"], hover_color=COLORS["red"],
                text_color=COLORS["text_muted"],
                command=lambda fid=fato_id: self._deletar_fato(fid)
            )
            btn_del.pack(side="right", padx=(0, 8))

    def _listar_todos_fatos(self):
        if not self.runtime or not hasattr(self.runtime, 'memory') or not self.runtime.memory:
            self._limpar_lista_fatos()
            lbl = ctk.CTkLabel(self.fatos_scroll, text="Runtime não conectado.", font=FONT_SMALL, text_color=COLORS["text_muted"])
            lbl.pack(pady=20)
            return
        try:
            fatos = self.runtime.memory.sqlite_manager.listar_fatos(limite=50)
            self._renderizar_fatos(fatos)
        except Exception as e:
            self._limpar_lista_fatos()
            lbl = ctk.CTkLabel(self.fatos_scroll, text=f"Erro: {e}", font=FONT_SMALL, text_color=COLORS["red"])
            lbl.pack(pady=20)

    def _buscar_fatos(self):
        query = self.entry_busca.get().strip()
        if not query:
            self._listar_todos_fatos()
            return
        if not self.runtime or not hasattr(self.runtime, 'memory') or not self.runtime.memory:
            return
        try:
            fatos = self.runtime.memory.sqlite_manager.buscar_fatos(keyword=query, limit=20)
            self._renderizar_fatos(fatos)
        except Exception as e:
            self._limpar_lista_fatos()
            lbl = ctk.CTkLabel(self.fatos_scroll, text=f"Erro: {e}", font=FONT_SMALL, text_color=COLORS["red"])
            lbl.pack(pady=20)

    def _deletar_fato(self, fato_id):
        if not fato_id or not self.runtime:
            return
        try:
            self.runtime.memory.sqlite_manager.deletar_fato(fato_id)
            self._listar_todos_fatos()
        except:
            pass
