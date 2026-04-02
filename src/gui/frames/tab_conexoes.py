"""
Tab Conexões — Switches de módulos e integrações da Hana.
Cada toggle salva imediatamente no config.json.
"""

import customtkinter as ctk
import logging
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from src.gui.design import COLORS, FONT_TITLE, FONT_BODY, FONT_SMALL
from src.config.config_loader import CONFIG
from src.core.runtime_capabilities import get_ptt_settings, sync_legacy_ptt_config


class TabConexoes(ctk.CTkFrame):
    """Conexões — switches de módulos com PTT key picker."""

    def __init__(self, master, **kwargs):
        super().__init__(master, corner_radius=12, fg_color=COLORS["bg_dark"], border_width=1, border_color=COLORS["border"])
        self.grid_columnconfigure(0, weight=1)

        # ─── HEADER ───
        header = ctk.CTkLabel(self, text="🔌  Conexões & Arsenal", font=FONT_TITLE, text_color=COLORS["text_primary"])
        header.grid(row=0, column=0, padx=25, pady=(20, 5), sticky="w")
        sub = ctk.CTkLabel(self, text="Controle de módulos — alterações são aplicadas em tempo real", font=FONT_SMALL, text_color=COLORS["text_muted"])
        sub.grid(row=1, column=0, padx=25, pady=(0, 20), sticky="w")

        # Scrollable para caber todos os módulos
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
        self.scroll.grid(row=2, column=0, padx=8, pady=(0, 8), sticky="nsew")
        self.scroll.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # ─── MÓDULOS ───
        self._switches = {}
        modulos = [
            ("tts",     "🗣  Voz (TTS)",                    "TTS_ATIVO",         "Síntese de voz — falar as respostas"),
            ("stt",     "🎙  Voz (STT — Whisper)",           "STT_ATIVO",         "Reconhecimento de voz — transcrição via Whisper"),
            ("ptt",     "🎤  Pressione para Falar (PTT)",    "GUI.ptt_enabled",   "Hotkey global para ativar escuta por tecla"),
            ("vts",     "🎭  VTube Studio",                  "VTUBESTUDIO_ATIVO", "Controle de avatar VTube Studio (em breve)"),
            ("discord", "🤖  Bot Discord",                   "Modo_discord",      "Bot de interação via Discord (em breve)"),
            ("visao",   "👁  Visão (Sob Demanda)",           "VISAO_ATIVA",       "Captura de tela sob demanda antes de cada resposta"),
        ]

        self._ptt_key_combo = None  # Referência para o seletor de tecla PTT

        for i, (key, nome, config_key, desc) in enumerate(modulos):
            card = ctk.CTkFrame(self.scroll, fg_color=COLORS["bg_card"], corner_radius=10, border_width=1, border_color=COLORS["border"])
            card.grid(row=i, column=0, padx=8, pady=4, sticky="ew")
            card.grid_columnconfigure(1, weight=1)

            lbl = ctk.CTkLabel(card, text=nome, font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"), text_color=COLORS["text_primary"])
            lbl.grid(row=0, column=0, padx=15, pady=(12, 2), sticky="w")

            lbl_desc = ctk.CTkLabel(card, text=desc, font=FONT_SMALL, text_color=COLORS["text_muted"])
            lbl_desc.grid(row=1, column=0, padx=15, pady=(0, 12), sticky="w")

            switch = ctk.CTkSwitch(
                card, text="", width=50,
                progress_color=COLORS["purple_neon"],
                button_color=COLORS["text_secondary"],
                button_hover_color=COLORS["purple_dim"],
                fg_color=COLORS["bg_darkest"],
                command=lambda k=key, ck=config_key: self._toggle(k, ck)
            )
            switch.grid(row=0, column=1, rowspan=2, padx=15, pady=10, sticky="e")
            self._switches[key] = switch

            # PTT: Adicionar seletor de tecla ao lado
            if key == "ptt":
                current_key = get_ptt_settings()["key"]

                key_frame = ctk.CTkFrame(card, fg_color="transparent")
                key_frame.grid(row=2, column=0, columnspan=2, padx=15, pady=(0, 12), sticky="ew")

                ctk.CTkLabel(key_frame, text="Tecla:", font=FONT_SMALL, text_color=COLORS["text_muted"]).pack(side="left", padx=(0, 8))

                teclas = ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12",
                          "CapsLock", "ScrollLock", "Insert", "Home", "End", "PageUp", "PageDown"]

                self._ptt_key_combo = ctk.CTkComboBox(
                    key_frame, values=teclas, width=140,
                    fg_color=COLORS["bg_darkest"], border_color=COLORS["border"],
                    button_color=COLORS["purple_dim"], button_hover_color=COLORS["purple_neon"],
                    dropdown_fg_color=COLORS["bg_card"], dropdown_hover_color=COLORS["purple_dark"],
                    text_color=COLORS["text_primary"], font=FONT_SMALL,
                    command=self._on_ptt_key_change
                )
                self._ptt_key_combo.set(current_key)
                self._ptt_key_combo.pack(side="left")

        self._atualizar_switches()

    def _atualizar_switches(self):
        """Atualiza switches para refletir o estado SALVO no CONFIG."""
        mapa_config = {
            "tts": "TTS_ATIVO",
            "stt": "STT_ATIVO",
            "ptt": "GUI.ptt_enabled",
            "vts": "VTUBESTUDIO_ATIVO",
            "discord": "Modo_discord",
            "visao": "VISAO_ATIVA",
        }
        for key, config_key in mapa_config.items():
            if key in self._switches:
                valor = False
                if "." in config_key:
                    parts = config_key.split(".")
                    section = CONFIG.get(parts[0], {})
                    valor = section.get(parts[1], False) if isinstance(section, dict) else False
                else:
                    valor = CONFIG.get(config_key, False)

                if valor:
                    self._switches[key].select()
                else:
                    self._switches[key].deselect()

    def _toggle(self, key, config_key):
        """Toggle de um módulo — persiste no config.json."""
        ativo = bool(self._switches[key].get())

        # Salvar no CONFIG
        if "." in config_key:
            parts = config_key.split(".")
            section = CONFIG.get(parts[0], {})
            if not isinstance(section, dict):
                section = {}
            section[parts[1]] = ativo
            CONFIG[parts[0]] = section
        else:
            CONFIG[config_key] = ativo

        if key == "ptt":
            sync_legacy_ptt_config()

        try:
            CONFIG.save()
            logging.info(f"[CONEXÕES] {config_key} = {ativo}")
        except Exception:
            pass

    def _on_ptt_key_change(self, new_key):
        """Atualiza a tecla PTT no config.json."""
        gui_cfg = CONFIG.get("GUI", {})
        if not isinstance(gui_cfg, dict):
            gui_cfg = {}
        gui_cfg["ptt_key"] = new_key
        CONFIG["GUI"] = gui_cfg
        sync_legacy_ptt_config()
        try:
            CONFIG.save()
            logging.info(f"[CONEXÕES] PTT tecla: {new_key}")
        except Exception:
            pass
