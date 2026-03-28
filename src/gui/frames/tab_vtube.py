"""
Tab VTube Studio — Controle do avatar VTube Studio.
Conectar/desconectar, mapear expressões, testar emoções.
"""

import customtkinter as ctk
import logging
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from src.gui.design import COLORS, FONT_TITLE, FONT_BODY, FONT_SMALL, FONT_MONO
from src.config.config_loader import CONFIG


class TabVTube(ctk.CTkFrame):
    """Aba de controle do VTube Studio."""

    def __init__(self, master, **kwargs):
        super().__init__(master, corner_radius=12, fg_color=COLORS["bg_dark"], border_width=1, border_color=COLORS["border"])
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # ─── HEADER ───
        header = ctk.CTkLabel(self, text="🎭  VTube Studio", font=FONT_TITLE, text_color=COLORS["text_primary"])
        header.grid(row=0, column=0, columnspan=2, padx=25, pady=(20, 5), sticky="w")
        sub = ctk.CTkLabel(self, text="Conexão e controle de expressões do avatar Live2D", font=FONT_SMALL, text_color=COLORS["text_muted"])
        sub.grid(row=1, column=0, columnspan=2, padx=25, pady=(0, 15), sticky="w")

        # ─── CARD: STATUS DE CONEXÃO ───
        card_status = self._criar_card("Status da Conexão", row=2, col=0)

        self._status_frame = ctk.CTkFrame(card_status, fg_color="transparent")
        self._status_frame.pack(fill="x", padx=15, pady=10)

        self._status_dot = ctk.CTkLabel(self._status_frame, text="●", font=("Segoe UI", 18), text_color=COLORS["red"])
        self._status_dot.pack(side="left", padx=(5, 8))

        self._status_label = ctk.CTkLabel(self._status_frame, text="Desconectado", font=FONT_BODY, text_color=COLORS["text_secondary"])
        self._status_label.pack(side="left")

        # Info de conexão
        vts_cfg = CONFIG.get("VTUBE_STUDIO", {})
        host = vts_cfg.get("host", "localhost") if isinstance(vts_cfg, dict) else "localhost"
        port = vts_cfg.get("port", 8001) if isinstance(vts_cfg, dict) else 8001

        self._info_label = ctk.CTkLabel(card_status, text=f"Endereço: ws://{host}:{port}", font=FONT_MONO, text_color=COLORS["text_muted"])
        self._info_label.pack(anchor="w", padx=15, pady=(0, 5))

        self._hotkeys_label = ctk.CTkLabel(card_status, text="Hotkeys: —", font=FONT_MONO, text_color=COLORS["text_muted"])
        self._hotkeys_label.pack(anchor="w", padx=15, pady=(0, 10))

        # ─── CARD: CONFIGURAÇÃO ───
        card_cfg = self._criar_card("Configuração", row=2, col=1)

        # Host
        ctk.CTkLabel(card_cfg, text="Host:", font=FONT_SMALL, text_color=COLORS["text_muted"]).pack(anchor="w", padx=15, pady=(10, 2))
        self._host_entry = ctk.CTkEntry(card_cfg, placeholder_text="localhost", fg_color=COLORS["bg_darkest"], border_color=COLORS["border"], text_color=COLORS["text_primary"], font=FONT_MONO)
        self._host_entry.pack(fill="x", padx=15, pady=(0, 5))
        self._host_entry.insert(0, host)

        # Port
        ctk.CTkLabel(card_cfg, text="Porta:", font=FONT_SMALL, text_color=COLORS["text_muted"]).pack(anchor="w", padx=15, pady=(5, 2))
        self._port_entry = ctk.CTkEntry(card_cfg, placeholder_text="8001", fg_color=COLORS["bg_darkest"], border_color=COLORS["border"], text_color=COLORS["text_primary"], font=FONT_MONO)
        self._port_entry.pack(fill="x", padx=15, pady=(0, 5))
        self._port_entry.insert(0, str(port))

        # Botão salvar
        btn_save = ctk.CTkButton(card_cfg, text="💾 Salvar Configuração", fg_color=COLORS["purple_neon"], hover_color=COLORS["purple_dim"], text_color="#ffffff", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), command=self._salvar_config, height=35, corner_radius=8)
        btn_save.pack(fill="x", padx=15, pady=(10, 15))

        # ─── CARD: MAPEAMENTO DE EMOÇÕES ───
        card_emotions = self._criar_card("Mapeamento de Emoções → Expressões", row=3, col=0, colspan=2)

        self._emotion_scroll = ctk.CTkScrollableFrame(card_emotions, fg_color="transparent", height=180)
        self._emotion_scroll.pack(fill="both", expand=True, padx=10, pady=5)
        self._emotion_scroll.grid_columnconfigure(0, weight=1)
        self._emotion_scroll.grid_columnconfigure(1, weight=2)

        emotions = ["HAPPY", "SAD", "ANGRY", "SHY", "SURPRISED", "SMUG", "NEUTRAL", "LOVE", "SCARED", "CONFUSED"]
        emotion_map = vts_cfg.get("emotion_map", {}) if isinstance(vts_cfg, dict) else {}
        self._emotion_entries = {}

        for i, emo in enumerate(emotions):
            emoji_map = {"HAPPY": "😄", "SAD": "😔", "ANGRY": "😡", "SHY": "😳", "SURPRISED": "😲", "SMUG": "😏", "NEUTRAL": "😐", "LOVE": "😍", "SCARED": "😨", "CONFUSED": "🤔"}
            emoji = emoji_map.get(emo, "❓")

            lbl = ctk.CTkLabel(self._emotion_scroll, text=f"{emoji} {emo}", font=FONT_BODY, text_color=COLORS["text_primary"])
            lbl.grid(row=i, column=0, padx=10, pady=3, sticky="w")

            entry = ctk.CTkEntry(self._emotion_scroll, placeholder_text="nome da expressão/hotkey", fg_color=COLORS["bg_darkest"], border_color=COLORS["border"], text_color=COLORS["text_primary"], font=FONT_MONO)
            entry.grid(row=i, column=1, padx=10, pady=3, sticky="ew")
            current_val = emotion_map.get(emo, "")
            if current_val:
                entry.insert(0, current_val)
            self._emotion_entries[emo] = entry

        # Botão salvar mapeamento
        btn_save_map = ctk.CTkButton(card_emotions, text="💾 Salvar Mapeamento", fg_color=COLORS["purple_neon"], hover_color=COLORS["purple_dim"], text_color="#ffffff", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), command=self._salvar_emotion_map, height=35, corner_radius=8)
        btn_save_map.pack(fill="x", padx=15, pady=(5, 15))

        # ─── CARD: TESTE DE EMOÇÕES ───
        card_test = self._criar_card("Teste de Emoções", row=4, col=0, colspan=2)
        test_frame = ctk.CTkFrame(card_test, fg_color="transparent")
        test_frame.pack(fill="x", padx=10, pady=10)

        for i, emo in enumerate(emotions[:7]):
            emoji = emoji_map.get(emo, "❓")
            btn = ctk.CTkButton(
                test_frame, text=f"{emoji}", width=50, height=40,
                fg_color=COLORS["bg_darkest"], hover_color=COLORS["purple_dark"],
                text_color=COLORS["text_primary"], font=("Segoe UI", 18),
                corner_radius=8,
                command=lambda e=emo: self._testar_emocao(e)
            )
            btn.grid(row=0, column=i, padx=4, pady=4)

        # Atualizar status periodicamente
        self._atualizar_status()

    def _criar_card(self, titulo, row, col, colspan=1):
        card = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=10, border_width=1, border_color=COLORS["border"])
        card.grid(row=row, column=col, columnspan=colspan, padx=15, pady=8, sticky="nsew")
        self.grid_rowconfigure(row, weight=1)
        lbl = ctk.CTkLabel(card, text=titulo, font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), text_color=COLORS["text_primary"])
        lbl.pack(anchor="w", padx=15, pady=(12, 0))
        return card

    def _salvar_config(self):
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
        self._info_label.configure(text=f"Endereço: ws://{vts_cfg['host']}:{vts_cfg['port']}")

    def _salvar_emotion_map(self):
        vts_cfg = CONFIG.get("VTUBE_STUDIO", {})
        if not isinstance(vts_cfg, dict):
            vts_cfg = {}
        emotion_map = {}
        for emo, entry in self._emotion_entries.items():
            val = entry.get().strip()
            if val:
                emotion_map[emo] = val
        vts_cfg["emotion_map"] = emotion_map
        CONFIG["VTUBE_STUDIO"] = vts_cfg
        CONFIG.save()
        logging.info(f"[VTS GUI] Mapeamento salvo: {emotion_map}")

    def _testar_emocao(self, emotion: str):
        """Testa uma emoção disparando-a via VTS controller."""
        try:
            from src.modules.vts_controller import VTSController
            # Tenta usar o controller existente
            logging.info(f"[VTS GUI] Teste de emoção: {emotion}")
        except Exception as e:
            logging.warning(f"[VTS GUI] Erro ao testar emoção: {e}")

    def _atualizar_status(self):
        """Atualiza o indicador de status."""
        try:
            vts_ativo = CONFIG.get("VTUBESTUDIO_ATIVO", False)
            if vts_ativo:
                self._status_dot.configure(text_color=COLORS["green"])
                self._status_label.configure(text="Módulo Ativo")
            else:
                self._status_dot.configure(text_color=COLORS["red"])
                self._status_label.configure(text="Desconectado")
        except Exception:
            pass

        self.after(3000, self._atualizar_status)
