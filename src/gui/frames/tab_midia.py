"""
Tab Mídia — Galeria e Fila de Produção da Lira.
Mostra imagens e músicas geradas, além de jobs em andamento.
"""

import os
import sys
import logging
import threading
import customtkinter as ctk
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from src.gui.design import COLORS, FONT_TITLE, FONT_BODY, FONT_SMALL, FONT_MONO
from src.config.config_loader import CONFIG
from src.modules.media.media_jobs import MediaJobManager

logger = logging.getLogger(__name__)

class TabMidia(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, corner_radius=12, fg_color=COLORS["bg_dark"], border_width=2, border_color=COLORS["border_strong"])
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1) # Fila
        self.grid_rowconfigure(4, weight=2) # Histórico

        self.job_manager = MediaJobManager()

        # ─── HEADER ───
        header = ctk.CTkLabel(self, text="🎨  Estúdio de Mídia", font=FONT_TITLE, text_color=COLORS["text_primary"])
        header.grid(row=0, column=0, padx=25, pady=(20, 5), sticky="w")
        sub = ctk.CTkLabel(self, text="Gerencie imagens e músicas criadas pela Lira", font=FONT_SMALL, text_color=COLORS["text_muted"])
        sub.grid(row=1, column=0, padx=25, pady=(0, 15), sticky="w")

        # ─── SEÇÃO: FILA DE GERAÇÃO ───
        self.label_queue = ctk.CTkLabel(self, text="⏳ FILA DE PRODUÇÃO", font=ctk.CTkFont(size=12, weight="bold"), text_color=COLORS["purple_neon"])
        self.label_queue.grid(row=2, column=0, padx=25, pady=(10, 5), sticky="w")

        self.queue_container = ctk.CTkScrollableFrame(self, height=150, fg_color=COLORS["bg_darkest"], border_width=1, border_color=COLORS["border"])
        self.queue_container.grid(row=3, column=0, padx=20, pady=(0, 15), sticky="nsew")

        # ─── SEÇÃO: HISTÓRICO DE MÍDIA ───
        self.label_history = ctk.CTkLabel(self, text="📚 HISTÓRICO RECENTE", font=ctk.CTkFont(size=12, weight="bold"), text_color=COLORS["blue_neon"])
        self.label_history.grid(row=4, column=0, padx=25, pady=(10, 5), sticky="w")

        self.history_tabview = ctk.CTkTabview(self, fg_color=COLORS["bg_darkest"], segmented_button_selected_color=COLORS["purple_dark"])
        self.history_tabview.grid(row=5, column=0, padx=20, pady=(0, 20), sticky="nsew")
        
        self.tab_imgs = self.history_tabview.add("🖼 Imagens")
        self.tab_audio = self.history_tabview.add("🎵 Músicas")

        self._setup_img_tab()
        self._setup_audio_tab()

        # Iniciar loop de atualização
        self._refresh_jobs()

    def _setup_img_tab(self):
        self.img_scroll = ctk.CTkScrollableFrame(self.tab_imgs, fg_color="transparent")
        self.img_scroll.pack(fill="both", expand=True)
        # TODO: Implementar grid de thumbnails

    def _setup_audio_tab(self):
        self.audio_scroll = ctk.CTkScrollableFrame(self.tab_audio, fg_color="transparent")
        self.audio_scroll.pack(fill="both", expand=True)

    def _refresh_jobs(self):
        """Atualiza a lista de jobs na fila."""
        # Limpar fila visual
        for child in self.queue_container.winfo_children():
            child.destroy()

        jobs = self.job_manager.list_jobs()
        active_jobs = [j for j in jobs if j["state"] in ["queued", "running"]]

        if not active_jobs:
            lbl = ctk.CTkLabel(self.queue_container, text="Nenhum processo criativo em andamento no momento.", font=FONT_SMALL, text_color=COLORS["text_muted"])
            lbl.pack(pady=20)
        else:
            for job in active_jobs:
                self._criar_item_fila(job)

        self.after(3000, self._refresh_jobs)

    def _criar_item_fila(self, job):
        frame = ctk.CTkFrame(self.queue_container, fg_color=COLORS["bg_card"], height=60)
        frame.pack(fill="x", padx=5, pady=3)
        
        icone = "🎵" if job["kind"] == "music" else "🎨"
        status_text = "⚡ Processando..." if job["state"] == "running" else "🕒 Na fila"
        
        lbl_info = ctk.CTkLabel(frame, text=f"{icone} {job['prompt'][:50]}...", font=FONT_SMALL, text_color=COLORS["text_primary"], anchor="w")
        lbl_info.pack(side="left", padx=15, pady=10)
        
        lbl_status = ctk.CTkLabel(frame, text=status_text, font=FONT_SMALL, text_color=COLORS["purple_neon"])
        lbl_status.pack(side="right", padx=15, pady=10)

    def _carregar_historico(self):
        # TODO: Ler arquivos da pasta lira_inbox e popular as abas
        pass
