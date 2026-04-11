"""
Tab Geral — Dashboard de Status do Sistema Hana.
Mostra CPU, RAM, módulos ativos e motor LLM em tempo real.
"""

import customtkinter as ctk

try:
    import psutil
    PSUTIL_OK = True
except ImportError:
    PSUTIL_OK = False

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from src.gui.design import COLORS, FONT_TITLE, FONT_BODY, FONT_SMALL, FONT_MONO
from src.config.config_loader import CONFIG


class TabGeral(ctk.CTkFrame):
    """Dashboard — visão geral do sistema Hana."""

    def __init__(self, master, **kwargs):
        super().__init__(master, corner_radius=12, fg_color=COLORS["bg_dark"], border_width=2, border_color=COLORS["border_strong"])
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # ─── HEADER ───
        header = ctk.CTkLabel(self, text="🖥  Monitor Geral", font=FONT_TITLE, text_color=COLORS["text_primary"])
        header.grid(row=0, column=0, columnspan=2, padx=25, pady=(20, 5), sticky="w")
        sub = ctk.CTkLabel(self, text="Status em tempo real de todos os subsistemas da Hana", font=FONT_SMALL, text_color=COLORS["text_muted"])
        sub.grid(row=1, column=0, columnspan=2, padx=25, pady=(0, 15), sticky="w")

        # ─── CARD: RECURSOS DO SISTEMA ───
        card_sys = self._criar_card("Recursos do Sistema", row=2, col=0)

        self.lbl_cpu = ctk.CTkLabel(card_sys, text="CPU:  —", font=FONT_MONO, text_color=COLORS["text_secondary"], anchor="w")
        self.lbl_cpu.pack(fill="x", padx=15, pady=(10, 2))
        self.bar_cpu = ctk.CTkProgressBar(card_sys, progress_color=COLORS["purple_neon"], fg_color=COLORS["bg_darkest"], height=10, corner_radius=5)
        self.bar_cpu.pack(fill="x", padx=15, pady=(0, 8))
        self.bar_cpu.set(0)

        self.lbl_ram = ctk.CTkLabel(card_sys, text="RAM:  —", font=FONT_MONO, text_color=COLORS["text_secondary"], anchor="w")
        self.lbl_ram.pack(fill="x", padx=15, pady=(5, 2))
        self.bar_ram = ctk.CTkProgressBar(card_sys, progress_color=COLORS["blue_neon"], fg_color=COLORS["bg_darkest"], height=10, corner_radius=5)
        self.bar_ram.pack(fill="x", padx=15, pady=(0, 10))
        self.bar_ram.set(0)

        # ─── CARD: MOTOR LLM ───
        card_llm = self._criar_card("Motor LLM Ativo", row=2, col=1)

        self.lbl_provedor = ctk.CTkLabel(card_llm, text="Provedor:  —", font=FONT_MONO, text_color=COLORS["text_secondary"], anchor="w")
        self.lbl_provedor.pack(fill="x", padx=15, pady=(10, 4))
        self.lbl_modelo = ctk.CTkLabel(card_llm, text="Modelo:  —", font=FONT_MONO, text_color=COLORS["purple_neon"], anchor="w")
        self.lbl_modelo.pack(fill="x", padx=15, pady=(0, 4))
        self.lbl_tts = ctk.CTkLabel(card_llm, text="TTS:  —", font=FONT_MONO, text_color=COLORS["text_secondary"], anchor="w")
        self.lbl_tts.pack(fill="x", padx=15, pady=(0, 10))

        # ─── CARD: MÓDULOS ATIVOS ───
        card_mods = self._criar_card("Módulos Ativos", row=3, col=0, colspan=2)

        self.modulos_frame = ctk.CTkFrame(card_mods, fg_color="transparent")
        self.modulos_frame.pack(fill="x", padx=15, pady=10)

        self._modulos_labels = {}
        modulos = ["LLM", "TTS", "STT", "Visão", "VTube Studio", "Discord"]
        for i, nome in enumerate(modulos):
            col = i % 3
            row = i // 3
            frame = ctk.CTkFrame(self.modulos_frame, fg_color=COLORS["bg_darkest"], corner_radius=8, height=50)
            frame.grid(row=row, column=col, padx=6, pady=4, sticky="ew")
            self.modulos_frame.grid_columnconfigure(col, weight=1)

            dot = ctk.CTkLabel(frame, text="●", font=("Segoe UI", 12), text_color=COLORS["text_muted"])
            dot.pack(side="left", padx=(10, 5), pady=8)
            lbl = ctk.CTkLabel(frame, text=nome, font=FONT_SMALL, text_color=COLORS["text_secondary"])
            lbl.pack(side="left", pady=8)
            self._modulos_labels[nome.lower()] = dot

        # Iniciar refresh
        self._atualizar()

    def _criar_card(self, titulo, row, col, colspan=1):
        """Cria um card estilizado."""
        card = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=12, border_width=2, border_color=COLORS["border"])
        card.grid(row=row, column=col, columnspan=colspan, padx=15, pady=8, sticky="nsew")
        self.grid_rowconfigure(row, weight=1)

        lbl = ctk.CTkLabel(card, text=titulo, font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), text_color=COLORS["text_primary"])
        lbl.pack(anchor="w", padx=15, pady=(12, 0))
        return card

    def _atualizar(self):
        """Refresh automático a cada 2 segundos."""
        try:
            # CPU e RAM via psutil
            if PSUTIL_OK:
                cpu = psutil.cpu_percent(interval=0)
                ram = psutil.virtual_memory()
                self.lbl_cpu.configure(text=f"CPU:  {cpu:.0f}%")
                self.bar_cpu.set(cpu / 100)
                self.lbl_ram.configure(text=f"RAM:  {ram.percent:.0f}%  ({ram.used // (1024**3):.1f} / {ram.total // (1024**3):.1f} GB)")
                self.bar_ram.set(ram.percent / 100)

                if cpu > 80:
                    self.bar_cpu.configure(progress_color=COLORS["red"])
                elif cpu > 50:
                    self.bar_cpu.configure(progress_color=COLORS["yellow"])
                else:
                    self.bar_cpu.configure(progress_color=COLORS["purple_neon"])

            # Status lido do CONFIG
            prov = CONFIG.get("LLM_PROVIDER", "?").upper()
            providers = CONFIG.get("LLM_PROVIDERS", {})
            prov_data = providers.get(CONFIG.get("LLM_PROVIDER", ""), {}) if isinstance(providers, dict) else {}
            modelo = prov_data.get("modelo", "?") if isinstance(prov_data, dict) else "?"
            tts = CONFIG.get("TTS_PROVIDER", "?").upper()

            self.lbl_provedor.configure(text=f"Provedor:  {prov}")
            self.lbl_modelo.configure(text=f"Modelo:    {modelo}")
            self.lbl_tts.configure(text=f"TTS:       {tts}")

            # Módulos
            mapa = {
                "llm": True,
                "tts": CONFIG.get("TTS_ATIVO", True),
                "stt": CONFIG.get("STT_ATIVO", True),
                "visão": CONFIG.get("VISAO_ATIVA", False),
                "vtube studio": CONFIG.get("VTUBESTUDIO_ATIVO", False),
                "discord": CONFIG.get("Modo_discord", False),
            }
            for key, ativo in mapa.items():
                if key in self._modulos_labels:
                    self._modulos_labels[key].configure(
                        text_color=COLORS["green"] if ativo else COLORS["red"]
                    )

        except Exception:
            pass

        self.after(2000, self._atualizar)
