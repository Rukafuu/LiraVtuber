"""
Tab Logs — Exibição de logs do sistema em tempo real.
Captura logs via handler customizado do Python logging.
"""

import logging
import customtkinter as ctk
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from src.gui.design import COLORS, FONT_TITLE, FONT_SMALL, FONT_MONO, FONT_MONO_SM
from src.config.config_loader import CONFIG


class GUILogHandler(logging.Handler):
    """Handler customizado que redireciona logs para um callback."""

    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        self.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-7s  %(name)s  →  %(message)s", datefmt="%H:%M:%S"))

    def emit(self, record):
        try:
            msg = self.format(record)
            self.callback(msg, record.levelno)
        except Exception:
            pass


class TabLogs(ctk.CTkFrame):
    """Painel de logs do sistema em tempo real."""

    def __init__(self, master, **kwargs):
        super().__init__(master, corner_radius=12, fg_color=COLORS["bg_dark"], border_width=2, border_color=COLORS["border_strong"])
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # ─── HEADER ───
        header = ctk.CTkLabel(self, text="📋  Logs do Sistema", font=FONT_TITLE, text_color=COLORS["text_primary"])
        header.grid(row=0, column=0, padx=25, pady=(20, 2), sticky="w")
        sub = ctk.CTkLabel(self, text="Visualize chamadas de API, erros e status em tempo real", font=FONT_SMALL, text_color=COLORS["text_muted"])
        sub.grid(row=1, column=0, padx=25, pady=(0, 12), sticky="w")

        # ─── LOG AREA ───
        self.log_text = ctk.CTkTextbox(
            self, font=FONT_MONO_SM,
            fg_color=COLORS["bg_darkest"],
            text_color=COLORS["text_secondary"],
            border_width=2, border_color=COLORS["border"],
            corner_radius=8, wrap="word",
            state="disabled"
        )
        self.log_text.grid(row=2, column=0, padx=15, pady=(0, 8), sticky="nsew")

        # ─── BARRA DE AÇÕES ───
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=3, column=0, padx=15, pady=(0, 15), sticky="ew")

        self.btn_limpar = ctk.CTkButton(
            btn_frame, text="🗑  Limpar", width=100,
            fg_color=COLORS["bg_card"], hover_color=COLORS["red"],
            text_color=COLORS["text_secondary"], border_width=2, border_color=COLORS["border"],
            command=self._limpar
        )
        self.btn_limpar.pack(side="left", padx=(0, 8))

        self.btn_copiar = ctk.CTkButton(
            btn_frame, text="📋  Copiar", width=100,
            fg_color=COLORS["bg_card"], hover_color=COLORS["blue_dim"],
            text_color=COLORS["text_secondary"], border_width=2, border_color=COLORS["border"],
            command=self._copiar
        )
        self.btn_copiar.pack(side="left")

        self.lbl_count = ctk.CTkLabel(btn_frame, text="0 linhas", font=FONT_SMALL, text_color=COLORS["text_muted"])
        self.lbl_count.pack(side="right", padx=10)

        self._line_count = 0

        # Registra o handler no root logger
        self._handler = GUILogHandler(self._on_log)
        self._handler.setLevel(logging.DEBUG)
        root_logger = logging.getLogger()
        root_logger.addHandler(self._handler)
        # Garante que o root logger capture tudo
        if root_logger.level > logging.DEBUG:
            root_logger.setLevel(logging.DEBUG)

        # Log inicial
        self._append_log("📋 Hana Control Center — Sistema de Logs inicializado.\n", COLORS["green"])
        self._append_log("💡 Logs de ações da GUI (chat, config, módulos) aparecerão aqui.\n", COLORS["text_muted"])
        self._append_log(f"🔧 Config: {os.path.abspath(CONFIG.config_path)}\n", COLORS["text_muted"])

    def _on_log(self, msg: str, level: int):
        """Callback chamado pelo handler — agendado no loop principal do Tk."""
        if level >= logging.ERROR:
            color = COLORS["red"]
        elif level >= logging.WARNING:
            color = COLORS["yellow"]
        else:
            color = COLORS["text_secondary"]

        # Agenda no thread principal do Tk
        try:
            self.after(0, lambda m=msg, c=color: self._append_log(m + "\n", c))
        except Exception:
            pass

    def _append_log(self, text: str, color: str = None):
        """Adiciona texto ao log (thread-safe via after)."""
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text)
        self.log_text.configure(state="disabled")
        self.log_text.see("end")

        self._line_count += 1
        self.lbl_count.configure(text=f"{self._line_count} linhas")

        # Limit log size
        if self._line_count > 2000:
            self.log_text.configure(state="normal")
            self.log_text.delete("1.0", "500.0")
            self.log_text.configure(state="disabled")
            self._line_count -= 500

    def _limpar(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")
        self._line_count = 0
        self.lbl_count.configure(text="0 linhas")

    def _copiar(self):
        """Copia todo o conteúdo dos logs para a área de transferência."""
        self.log_text.configure(state="normal")
        conteudo = self.log_text.get("1.0", "end")
        self.log_text.configure(state="disabled")
        self.clipboard_clear()
        self.clipboard_append(conteudo)

    def destroy(self):
        """Remove o handler ao destruir o frame."""
        try:
            logging.getLogger().removeHandler(self._handler)
        except Exception:
            pass
        super().destroy()
