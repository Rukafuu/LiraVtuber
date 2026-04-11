"""
Tab Conexoes - switches de modulos e integracoes da Hana.
Cada toggle salva imediatamente no config.json.
"""

import customtkinter as ctk
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from src.config.config_loader import CONFIG
from src.core.runtime_capabilities import (
    get_ptt_settings,
    get_stop_hotkey_settings,
    sync_legacy_ptt_config,
)
from src.gui.design import COLORS, FONT_SMALL, FONT_TITLE


class TabConexoes(ctk.CTkFrame):
    """Conexoes - switches de modulos com seletores de hotkey."""

    def __init__(self, master, **kwargs):
        super().__init__(master, corner_radius=12, fg_color=COLORS["bg_dark"], border_width=2, border_color=COLORS["border_strong"])
        self.grid_columnconfigure(0, weight=1)

        header = ctk.CTkLabel(self, text="Conexoes & Arsenal", font=FONT_TITLE, text_color=COLORS["text_primary"])
        header.grid(row=0, column=0, padx=25, pady=(20, 5), sticky="w")
        sub = ctk.CTkLabel(self, text="Controle de modulos - alteracoes sao aplicadas em tempo real", font=FONT_SMALL, text_color=COLORS["text_muted"])
        sub.grid(row=1, column=0, padx=25, pady=(0, 20), sticky="w")

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
        self.scroll.grid(row=2, column=0, padx=8, pady=(0, 8), sticky="nsew")
        self.scroll.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._switches = {}
        self._ptt_key_combo = None
        self._stop_key_combo = None

        modulos = [
            ("tts", "Voz (TTS)", "TTS_ATIVO", "Sintese de voz - falar as respostas"),
            ("stt", "Voz (STT - Whisper)", "STT_ATIVO", "Reconhecimento de voz - transcricao via Whisper"),
            ("ptt", "Pressione para Falar (PTT)", "GUI.ptt_enabled", "Hotkey global para ativar escuta por tecla"),
            ("stop_hotkey", "Parar Resposta (Hotkey)", "GUI.stop_hotkey_enabled", "Hotkey global para parar stream, TTS, preview e midia do chat"),
            ("vts", "VTube Studio", "VTUBESTUDIO_ATIVO", "Controle de avatar VTube Studio (em breve)"),
            ("discord", "Bot Discord", "Modo_discord", "Bot de interacao via Discord (em breve)"),
            ("visao", "Visao (Sob Demanda)", "VISAO_ATIVA", "Captura de tela sob demanda antes de cada resposta"),
        ]

        for row_index, (key, nome, config_key, desc) in enumerate(modulos):
            card = ctk.CTkFrame(self.scroll, fg_color=COLORS["bg_card"], corner_radius=12, border_width=2, border_color=COLORS["border"])
            card.grid(row=row_index, column=0, padx=8, pady=4, sticky="ew")
            card.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(
                card,
                text=nome,
                font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
                text_color=COLORS["text_primary"],
            ).grid(row=0, column=0, padx=15, pady=(12, 2), sticky="w")

            ctk.CTkLabel(
                card,
                text=desc,
                font=FONT_SMALL,
                text_color=COLORS["text_muted"],
            ).grid(row=1, column=0, padx=15, pady=(0, 12), sticky="w")

            switch = ctk.CTkSwitch(
                card,
                text="",
                width=50,
                progress_color=COLORS["purple_neon"],
                button_color=COLORS["text_secondary"],
                button_hover_color=COLORS["purple_dim"],
                fg_color=COLORS["bg_darkest"],
                command=lambda k=key, ck=config_key: self._toggle(k, ck),
            )
            switch.grid(row=0, column=1, rowspan=2, padx=15, pady=10, sticky="e")
            self._switches[key] = switch

            if key == "ptt":
                self._build_key_picker(
                    card,
                    current_key=get_ptt_settings()["key"],
                    on_change=self._on_ptt_key_change,
                    attr_name="_ptt_key_combo",
                )
            elif key == "stop_hotkey":
                self._build_key_picker(
                    card,
                    current_key=get_stop_hotkey_settings()["key"],
                    on_change=self._on_stop_key_change,
                    attr_name="_stop_key_combo",
                )

        self._atualizar_switches()

    def _build_key_picker(self, parent, *, current_key, on_change, attr_name):
        key_frame = ctk.CTkFrame(parent, fg_color="transparent")
        key_frame.grid(row=2, column=0, columnspan=2, padx=15, pady=(0, 12), sticky="ew")
        ctk.CTkLabel(key_frame, text="Tecla:", font=FONT_SMALL, text_color=COLORS["text_muted"]).pack(side="left", padx=(0, 8))

        teclas = [
            "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12",
            "CapsLock", "ScrollLock", "Insert", "Home", "End", "PageUp", "PageDown",
        ]
        combo = ctk.CTkComboBox(
            key_frame,
            values=teclas,
            width=140,
            fg_color=COLORS["bg_darkest"],
            border_color=COLORS["border"],
            button_color=COLORS["purple_dim"],
            button_hover_color=COLORS["purple_neon"],
            dropdown_fg_color=COLORS["bg_card"],
            dropdown_hover_color=COLORS["purple_dark"],
            text_color=COLORS["text_primary"],
            font=FONT_SMALL,
            command=on_change,
        )
        combo.set(current_key)
        combo.pack(side="left")
        setattr(self, attr_name, combo)

    def _atualizar_switches(self):
        mapa_config = {
            "tts": "TTS_ATIVO",
            "stt": "STT_ATIVO",
            "ptt": "GUI.ptt_enabled",
            "stop_hotkey": "GUI.stop_hotkey_enabled",
            "vts": "VTUBESTUDIO_ATIVO",
            "discord": "Modo_discord",
            "visao": "VISAO_ATIVA",
        }
        for key, config_key in mapa_config.items():
            if key not in self._switches:
                continue
            if "." in config_key:
                section_name, item_name = config_key.split(".", 1)
                section = CONFIG.get(section_name, {})
                valor = section.get(item_name, False) if isinstance(section, dict) else False
            else:
                valor = CONFIG.get(config_key, False)
            if valor:
                self._switches[key].select()
            else:
                self._switches[key].deselect()

    def _toggle(self, key, config_key):
        ativo = bool(self._switches[key].get())
        if "." in config_key:
            section_name, item_name = config_key.split(".", 1)
            section = CONFIG.get(section_name, {})
            if not isinstance(section, dict):
                section = {}
            section[item_name] = ativo
            CONFIG[section_name] = section
        else:
            CONFIG[config_key] = ativo

        if key == "ptt":
            sync_legacy_ptt_config()

        try:
            CONFIG.save()
            logging.info("[CONEXOES] %s = %s", config_key, ativo)
        except Exception:
            pass
        self._refresh_chat_runtime()

    def _on_ptt_key_change(self, new_key):
        gui_cfg = CONFIG.get("GUI", {})
        if not isinstance(gui_cfg, dict):
            gui_cfg = {}
        gui_cfg["ptt_key"] = new_key
        CONFIG["GUI"] = gui_cfg
        sync_legacy_ptt_config()
        try:
            CONFIG.save()
            logging.info("[CONEXOES] PTT tecla: %s", new_key)
        except Exception:
            pass
        self._refresh_chat_runtime()

    def _on_stop_key_change(self, new_key):
        gui_cfg = CONFIG.get("GUI", {})
        if not isinstance(gui_cfg, dict):
            gui_cfg = {}
        gui_cfg["stop_hotkey"] = new_key
        CONFIG["GUI"] = gui_cfg
        try:
            CONFIG.save()
            logging.info("[CONEXOES] Stop hotkey: %s", new_key)
        except Exception:
            pass
        self._refresh_chat_runtime()

    def _refresh_chat_runtime(self):
        frames = getattr(self.master, "frames", {})
        chat_frame = frames.get("chat") if isinstance(frames, dict) else None
        if chat_frame and hasattr(chat_frame, "on_config_reload"):
            try:
                chat_frame.on_config_reload()
            except Exception:
                logging.exception("[CONEXOES] Falha ao recarregar hotkeys do chat")
