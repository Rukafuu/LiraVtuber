"""
Tab VTube Studio: controle do avatar Live2D.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time

import customtkinter as ctk

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from src.config.config_loader import CONFIG
from src.gui.design import COLORS, FONT_BODY, FONT_MONO, FONT_SMALL, FONT_TITLE
from src.utils.text import repair_mojibake_text


class TabVTube(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            corner_radius=12,
            fg_color=COLORS["bg_dark"],
            border_width=2,
            border_color=COLORS["border_strong"],
        )
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        header = ctk.CTkLabel(self, text="VTube Studio", font=FONT_TITLE, text_color=COLORS["text_primary"])
        header.grid(row=0, column=0, columnspan=2, padx=25, pady=(20, 5), sticky="w")
        sub = ctk.CTkLabel(
            self,
            text="Conexao, autenticacao e observabilidade do avatar Live2D.",
            font=FONT_SMALL,
            text_color=COLORS["text_muted"],
        )
        sub.grid(row=1, column=0, columnspan=2, padx=25, pady=(0, 15), sticky="w")

        card_status = self._create_card("Status da conexao", row=2, col=0)

        self._status_frame = ctk.CTkFrame(card_status, fg_color="transparent")
        self._status_frame.pack(fill="x", padx=15, pady=10)

        self._status_dot = ctk.CTkLabel(self._status_frame, text="●", font=("Segoe UI", 18), text_color=COLORS["red"])
        self._status_dot.pack(side="left", padx=(5, 8))
        self._status_label = ctk.CTkLabel(self._status_frame, text="Desconectado", font=FONT_BODY, text_color=COLORS["text_secondary"])
        self._status_label.pack(side="left")

        vts_cfg = CONFIG.get("VTUBE_STUDIO", {})
        host = vts_cfg.get("host", "localhost") if isinstance(vts_cfg, dict) else "localhost"
        port = vts_cfg.get("port", 8001) if isinstance(vts_cfg, dict) else 8001

        self._info_label = ctk.CTkLabel(card_status, text=f"Endereco: ws://{host}:{port}", font=FONT_MONO, text_color=COLORS["text_muted"])
        self._info_label.pack(anchor="w", padx=15, pady=(0, 5))
        self._auth_label = ctk.CTkLabel(card_status, text="Autenticacao: -", font=FONT_MONO, text_color=COLORS["text_muted"])
        self._auth_label.pack(anchor="w", padx=15, pady=(0, 5))
        self._hotkeys_label = ctk.CTkLabel(card_status, text="Hotkeys: -", font=FONT_MONO, text_color=COLORS["text_muted"])
        self._hotkeys_label.pack(anchor="w", padx=15, pady=(0, 5))
        self._heartbeat_label = ctk.CTkLabel(card_status, text="Heartbeat: -", font=FONT_MONO, text_color=COLORS["text_muted"])
        self._heartbeat_label.pack(anchor="w", padx=15, pady=(0, 5))
        self._reconnect_label = ctk.CTkLabel(card_status, text="Reconexoes: -", font=FONT_MONO, text_color=COLORS["text_muted"])
        self._reconnect_label.pack(anchor="w", padx=15, pady=(0, 5))
        self._mouth_label = ctk.CTkLabel(card_status, text="Boca: -", font=FONT_MONO, text_color=COLORS["text_muted"])
        self._mouth_label.pack(anchor="w", padx=15, pady=(0, 5))
        self._expression_label = ctk.CTkLabel(card_status, text="Expressao ativa: -", font=FONT_MONO, text_color=COLORS["text_muted"])
        self._expression_label.pack(anchor="w", padx=15, pady=(0, 5))
        self._error_label = ctk.CTkLabel(
            card_status,
            text="Ultimo erro: -",
            font=FONT_SMALL,
            text_color=COLORS["text_muted"],
            wraplength=420,
            justify="left",
        )
        self._error_label.pack(anchor="w", padx=15, pady=(0, 10))

        card_cfg = self._create_card("Configuracao", row=2, col=1)
        ctk.CTkLabel(card_cfg, text="Host:", font=FONT_SMALL, text_color=COLORS["text_muted"]).pack(anchor="w", padx=15, pady=(10, 2))
        self._host_entry = ctk.CTkEntry(
            card_cfg,
            placeholder_text="localhost",
            fg_color=COLORS["bg_darkest"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            font=FONT_MONO,
        )
        self._host_entry.pack(fill="x", padx=15, pady=(0, 5))
        self._host_entry.insert(0, host)

        ctk.CTkLabel(card_cfg, text="Porta:", font=FONT_SMALL, text_color=COLORS["text_muted"]).pack(anchor="w", padx=15, pady=(5, 2))
        self._port_entry = ctk.CTkEntry(
            card_cfg,
            placeholder_text="8001",
            fg_color=COLORS["bg_darkest"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            font=FONT_MONO,
        )
        self._port_entry.pack(fill="x", padx=15, pady=(0, 5))
        self._port_entry.insert(0, str(port))

        btn_save = ctk.CTkButton(
            card_cfg,
            text="Salvar configuracao",
            fg_color=COLORS["purple_neon"],
            hover_color=COLORS["purple_dim"],
            text_color="#ffffff",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self._save_config,
            height=35,
            corner_radius=8,
        )
        btn_save.pack(fill="x", padx=15, pady=(10, 15))

        card_emotions = self._create_card("Mapeamento de emocoes para expressoes", row=3, col=0, colspan=2)
        self._emotion_scroll = ctk.CTkScrollableFrame(card_emotions, fg_color="transparent", height=180)
        self._emotion_scroll.pack(fill="both", expand=True, padx=10, pady=5)
        self._emotion_scroll.grid_columnconfigure(0, weight=1)
        self._emotion_scroll.grid_columnconfigure(1, weight=2)

        emotions = ["HAPPY", "SAD", "ANGRY", "SHY", "SURPRISED", "SMUG", "NEUTRAL", "LOVE", "SCARED", "CONFUSED"]
        emotion_map = vts_cfg.get("emotion_map", {}) if isinstance(vts_cfg, dict) else {}
        self._emotion_entries = {}

        for i, emotion in enumerate(emotions):
            lbl = ctk.CTkLabel(self._emotion_scroll, text=emotion, font=FONT_BODY, text_color=COLORS["text_primary"])
            lbl.grid(row=i, column=0, padx=10, pady=3, sticky="w")
            entry = ctk.CTkEntry(
                self._emotion_scroll,
                placeholder_text="nome da expressao ou hotkey",
                fg_color=COLORS["bg_darkest"],
                border_color=COLORS["border"],
                text_color=COLORS["text_primary"],
                font=FONT_MONO,
            )
            entry.grid(row=i, column=1, padx=10, pady=3, sticky="ew")
            current_val = emotion_map.get(emotion, "")
            if current_val:
                entry.insert(0, current_val)
            self._emotion_entries[emotion] = entry

        btn_save_map = ctk.CTkButton(
            card_emotions,
            text="Salvar mapeamento",
            fg_color=COLORS["purple_neon"],
            hover_color=COLORS["purple_dim"],
            text_color="#ffffff",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self._save_emotion_map,
            height=35,
            corner_radius=8,
        )
        btn_save_map.pack(fill="x", padx=15, pady=(5, 15))

        card_test = self._create_card("Teste de emocoes", row=4, col=0, colspan=2)
        test_frame = ctk.CTkFrame(card_test, fg_color="transparent")
        test_frame.pack(fill="x", padx=10, pady=10)
        for i, emotion in enumerate(emotions[:7]):
            btn = ctk.CTkButton(
                test_frame,
                text=emotion[:3],
                width=60,
                height=40,
                fg_color=COLORS["bg_darkest"],
                hover_color=COLORS["purple_dark"],
                text_color=COLORS["text_primary"],
                font=("Segoe UI", 12, "bold"),
                corner_radius=8,
                command=lambda e=emotion: self._test_emotion(e),
            )
            btn.grid(row=0, column=i, padx=4, pady=4)

        self._refresh_status()

    def _create_card(self, title, row, col, colspan=1):
        card = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=12, border_width=2, border_color=COLORS["border"])
        card.grid(row=row, column=col, columnspan=colspan, padx=15, pady=8, sticky="nsew")
        self.grid_rowconfigure(row, weight=1)
        lbl = ctk.CTkLabel(
            card,
            text=title,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=COLORS["text_primary"],
        )
        lbl.pack(anchor="w", padx=15, pady=(12, 0))
        return card

    def _save_config(self):
        vts_cfg = CONFIG.get("VTUBE_STUDIO", {})
        if not isinstance(vts_cfg, dict):
            vts_cfg = {}
        vts_cfg["host"] = self._host_entry.get().strip() or "localhost"
        try:
            vts_cfg["port"] = int(self._port_entry.get().strip())
        except ValueError:
            vts_cfg["port"] = 8001
        CONFIG["VTUBE_STUDIO"] = vts_cfg
        CONFIG.save()
        self._info_label.configure(text=f"Endereco: ws://{vts_cfg['host']}:{vts_cfg['port']}")

    def _save_emotion_map(self):
        vts_cfg = CONFIG.get("VTUBE_STUDIO", {})
        if not isinstance(vts_cfg, dict):
            vts_cfg = {}
        emotion_map = {}
        for emotion, entry in self._emotion_entries.items():
            value = entry.get().strip()
            if value:
                emotion_map[emotion] = value
        vts_cfg["emotion_map"] = emotion_map
        CONFIG["VTUBE_STUDIO"] = vts_cfg
        CONFIG.save()
        logging.info("[VTS GUI] Mapeamento salvo: %s", emotion_map)

    def _test_emotion(self, emotion: str):
        logging.info("[VTS GUI] Teste de emocao: %s", emotion)

    def _refresh_status(self):
        try:
            state_path = os.path.abspath(os.path.join("data", "vts_state.json"))
            state = {}
            if os.path.exists(state_path):
                with open(state_path, "r", encoding="utf-8") as file:
                    state = json.load(file)

            host = state.get("host", self._host_entry.get().strip() or "localhost")
            port = state.get("port", self._port_entry.get().strip() or "8001")
            self._info_label.configure(text=f"Endereco: ws://{host}:{port}")
            self._hotkeys_label.configure(text=f"Hotkeys: {state.get('hotkeys', 0)} | Expressoes: {state.get('expressions', 0)}")
            heartbeat = state.get("last_heartbeat_at", 0)
            heartbeat_text = "-" if not heartbeat else time.strftime("%H:%M:%S", time.localtime(heartbeat))
            self._heartbeat_label.configure(text=f"Heartbeat: {heartbeat_text}")
            self._reconnect_label.configure(text=f"Reconexoes: {state.get('reconnect_attempts', 0)} | Modo: {state.get('tracking_mode', '-')}")
            self._mouth_label.configure(text=f"Boca: {state.get('mouth_parameter', '-')}")
            self._expression_label.configure(text=f"Expressao ativa: {state.get('last_expression', '-')}")
            self._auth_label.configure(text=f"Autenticacao: {'ok' if state.get('authenticated') else 'pendente'}")

            status = state.get("status")
            if state.get("authenticated"):
                self._status_dot.configure(text_color=COLORS["green"])
                self._status_label.configure(text=f"Conectado e autenticado ({status or 'ready'})")
            elif state.get("connected"):
                self._status_dot.configure(text_color=COLORS["yellow"])
                self._status_label.configure(text="Conectado, aguardando autenticacao")
            elif status in {"starting", "connecting", "reconnecting", "awaiting_auth"}:
                self._status_dot.configure(text_color=COLORS["yellow"])
                self._status_label.configure(text=str(status).replace("_", " ").title())
            else:
                self._status_dot.configure(text_color=COLORS["red"])
                error_msg = repair_mojibake_text(str(state.get("last_error", "")).strip())
                self._status_label.configure(text=(error_msg[:60] if error_msg else (status or "Desconectado")))

            last_error = repair_mojibake_text(str(state.get("last_error", "")).strip() or "-")
            self._error_label.configure(text=f"Ultimo erro: {last_error}")
        except Exception:
            pass

        self.after(3000, self._refresh_status)
