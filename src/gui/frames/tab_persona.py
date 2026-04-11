"""
Tab Persona — Editor da personalidade da Hana (persona.txt).
Mudanças são captadas pelo terminal no próximo turno automaticamente.
"""

import customtkinter as ctk
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from src.gui.design import COLORS, FONT_TITLE, FONT_BODY, FONT_SMALL, FONT_MONO

PERSONA_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "config", "persona.txt")


class TabPersona(ctk.CTkFrame):
    """Editor da personalidade da Hana — persona.txt."""

    def __init__(self, master, **kwargs):
        super().__init__(master, corner_radius=12, fg_color=COLORS["bg_dark"], border_width=2, border_color=COLORS["border_strong"])
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # ─── HEADER ───
        header = ctk.CTkLabel(self, text="📝  Persona — Personalidade da Hana", font=FONT_TITLE, text_color=COLORS["text_primary"])
        header.grid(row=0, column=0, padx=25, pady=(20, 2), sticky="w")
        sub = ctk.CTkLabel(
            self,
            text="Edite a personalidade da Hana. O terminal usa a versão salva no próximo turno automaticamente.",
            font=FONT_SMALL, text_color=COLORS["text_muted"]
        )
        sub.grid(row=1, column=0, padx=25, pady=(0, 12), sticky="w")

        # ─── EDITOR ───
        editor_card = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=12, border_width=2, border_color=COLORS["border"])
        editor_card.grid(row=2, column=0, padx=15, pady=(0, 8), sticky="nsew")
        editor_card.grid_columnconfigure(0, weight=1)
        editor_card.grid_rowconfigure(1, weight=1)

        # Info do arquivo
        path_abs = os.path.abspath(PERSONA_PATH)
        path_lbl = ctk.CTkLabel(
            editor_card,
            text=f"📄 {os.path.basename(path_abs)}  —  {path_abs}",
            font=FONT_SMALL, text_color=COLORS["text_muted"]
        )
        path_lbl.grid(row=0, column=0, padx=15, pady=(12, 5), sticky="w")

        # Textbox
        self.editor = ctk.CTkTextbox(
            editor_card, font=FONT_MONO,
            fg_color=COLORS["bg_darkest"],
            text_color=COLORS["text_primary"],
            border_width=2, border_color=COLORS["border"],
            corner_radius=8, wrap="word"
        )
        self.editor.grid(row=1, column=0, padx=12, pady=(0, 8), sticky="nsew")

        # ─── BARRA DE AÇÕES ───
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=3, column=0, padx=15, pady=(0, 15), sticky="ew")

        self.btn_recarregar = ctk.CTkButton(
            btn_frame, text="↻  Recarregar", width=130,
            fg_color=COLORS["bg_card"], hover_color=COLORS["blue_dim"],
            text_color=COLORS["text_secondary"], border_width=2, border_color=COLORS["border"],
            command=self._carregar
        )
        self.btn_recarregar.pack(side="left", padx=(0, 8))

        self.btn_salvar = ctk.CTkButton(
            btn_frame, text="💾  Salvar", width=130,
            fg_color=COLORS["purple_dim"], hover_color=COLORS["purple_neon"],
            text_color="white",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            command=self._salvar
        )
        self.btn_salvar.pack(side="left")

        self.lbl_status = ctk.CTkLabel(btn_frame, text="", font=FONT_SMALL, text_color=COLORS["green"])
        self.lbl_status.pack(side="right", padx=10)

        # Carrega conteúdo inicial
        self._carregar()

    def _carregar(self):
        """Lê persona.txt do disco e carrega no editor."""
        path = os.path.abspath(PERSONA_PATH)
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    conteudo = f.read()
                self.editor.delete("1.0", "end")
                self.editor.insert("1.0", conteudo)
                self.lbl_status.configure(text=f"✓ Carregado ({len(conteudo)} chars)", text_color=COLORS["green"])
            else:
                self.editor.delete("1.0", "end")
                self.editor.insert("1.0", "Eu sou a Hana AM Nakamura...")
                self.lbl_status.configure(text="Arquivo não encontrado — template criado", text_color=COLORS["yellow"])
        except Exception as e:
            self.lbl_status.configure(text=f"Erro: {e}", text_color=COLORS["red"])

    def _salvar(self):
        """Salva o conteúdo do editor em persona.txt."""
        path = os.path.abspath(PERSONA_PATH)
        texto = self.editor.get("1.0", "end").strip()

        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(texto)
            self.lbl_status.configure(
                text="✓ Salvo! O terminal usará a nova persona no próximo turno.",
                text_color=COLORS["green"]
            )
        except Exception as e:
            self.lbl_status.configure(text=f"Erro ao salvar: {e}", text_color=COLORS["red"])
