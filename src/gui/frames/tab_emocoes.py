"""
Tab Emoções — Aba "Mente da Hana".
Mostra humor atual, último pensamento, histórico de emoções.
Lê o estado via IPC (arquivo JSON) para funcionar em processo separado.
"""

import customtkinter as ctk
import json
import time
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from src.gui.design import COLORS, FONT_TITLE, FONT_BODY, FONT_SMALL, FONT_MONO

STATE_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "emotion_state.json")


class TabEmocoes(ctk.CTkFrame):
    """Aba Mente da Hana — visualização do estado emocional e pensamentos."""

    def __init__(self, master, **kwargs):
        super().__init__(master, corner_radius=12, fg_color=COLORS["bg_dark"], border_width=2, border_color=COLORS["border_strong"])
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self._last_update_ts = 0.0  # Timestamp da ultima leitura do JSON

        # ─── HEADER ───
        header = ctk.CTkLabel(self, text="💭  Mente da Hana", font=FONT_TITLE, text_color=COLORS["text_primary"])
        header.grid(row=0, column=0, columnspan=2, padx=25, pady=(20, 5), sticky="w")
        sub = ctk.CTkLabel(self, text="Visualização em tempo real do estado emocional e pensamentos internos", font=FONT_SMALL, text_color=COLORS["text_muted"])
        sub.grid(row=1, column=0, columnspan=2, padx=25, pady=(0, 15), sticky="w")

        # ─── CARD: HUMOR ATUAL ───
        card_mood = self._criar_card("Humor Atual", row=2, col=0)

        # Emoji grande do humor
        self._mood_emoji = ctk.CTkLabel(card_mood, text="😐", font=("Segoe UI", 64))
        self._mood_emoji.pack(pady=(15, 5))

        # Label do humor
        self._mood_label = ctk.CTkLabel(card_mood, text="Neutra", font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"), text_color=COLORS["purple_neon"])
        self._mood_label.pack(pady=(0, 5))

        # Barra de humor
        self._mood_bar_frame = ctk.CTkFrame(card_mood, fg_color="transparent")
        self._mood_bar_frame.pack(fill="x", padx=20, pady=(5, 5))

        ctk.CTkLabel(self._mood_bar_frame, text="😡", font=("Segoe UI", 14)).pack(side="left", padx=5)
        self._mood_bar = ctk.CTkProgressBar(self._mood_bar_frame, progress_color=COLORS["purple_neon"], fg_color=COLORS["bg_darkest"], height=12, corner_radius=6)
        self._mood_bar.pack(side="left", fill="x", expand=True, padx=5)
        self._mood_bar.set(0.5)
        ctk.CTkLabel(self._mood_bar_frame, text="😄", font=("Segoe UI", 14)).pack(side="left", padx=5)

        # Valor numérico
        self._mood_value = ctk.CTkLabel(card_mood, text="Mood: 0.00", font=FONT_MONO, text_color=COLORS["text_muted"])
        self._mood_value.pack(pady=(0, 15))

        # ─── CARD: EMOÇÃO ATIVA ───
        card_emotion = self._criar_card("Emoção Ativa", row=2, col=1)

        self._emotion_emoji = ctk.CTkLabel(card_emotion, text="❓", font=("Segoe UI", 48))
        self._emotion_emoji.pack(pady=(15, 5))

        self._emotion_label = ctk.CTkLabel(card_emotion, text="NEUTRAL", font=ctk.CTkFont(family="Consolas", size=20, weight="bold"), text_color=COLORS["text_primary"])
        self._emotion_label.pack(pady=(0, 5))

        self._emotion_turno = ctk.CTkLabel(card_emotion, text="Turno: —", font=FONT_MONO, text_color=COLORS["text_muted"])
        self._emotion_turno.pack(pady=(0, 15))

        # ─── CARD: ÚLTIMO PENSAMENTO ───
        card_thought = self._criar_card("Último Pensamento Interno", row=3, col=0, colspan=2)

        self._thought_box = ctk.CTkTextbox(
            card_thought, height=80, font=FONT_MONO,
            fg_color=COLORS["bg_darkest"], border_color=COLORS["border"],
            text_color=COLORS["text_secondary"], border_width=2,
            corner_radius=8, wrap="word"
        )
        self._thought_box.pack(fill="both", expand=True, padx=15, pady=10)
        self._thought_box.insert("1.0", "💭 A Hana ainda não pensou nada...")
        self._thought_box.configure(state="disabled")

        # ─── CARD: HISTÓRICO DE EMOÇÕES ───
        card_history = self._criar_card("Histórico de Emoções", row=4, col=0, colspan=2)

        self._history_scroll = ctk.CTkScrollableFrame(card_history, fg_color="transparent", height=140)
        self._history_scroll.pack(fill="both", expand=True, padx=10, pady=10)
        self._history_scroll.grid_columnconfigure(0, weight=1)

        self._history_labels = []

        # Atualização periódica
        self._atualizar()

    def _criar_card(self, titulo, row, col, colspan=1):
        card = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=12, border_width=2, border_color=COLORS["border"])
        card.grid(row=row, column=col, columnspan=colspan, padx=15, pady=8, sticky="nsew")
        self.grid_rowconfigure(row, weight=1)
        lbl = ctk.CTkLabel(card, text=titulo, font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), text_color=COLORS["text_primary"])
        lbl.pack(anchor="w", padx=15, pady=(12, 0))
        return card

    def _ler_estado_json(self) -> dict | None:
        """Lê o estado emocional do arquivo JSON (IPC com main.py)."""
        try:
            abspath = os.path.abspath(STATE_FILE)
            if not os.path.exists(abspath):
                return None
            with open(abspath, "r", encoding="utf-8") as f:
                state = json.load(f)
            # Só atualiza se o timestamp mudou
            updated_at = state.get("updated_at", 0)
            if updated_at <= self._last_update_ts:
                return None  # Nada novo
            self._last_update_ts = updated_at
            return state
        except Exception:
            return None

    def _atualizar(self):
        """Refresh automático a cada 1.5 segundo via IPC JSON."""
        emoji_map = {
            "HAPPY": "😄", "SAD": "😔", "ANGRY": "😡", "SHY": "😳",
            "SURPRISED": "😲", "SMUG": "😏", "NEUTRAL": "😐",
            "LOVE": "😍", "SCARED": "😨", "CONFUSED": "🤔"
        }

        state = self._ler_estado_json()
        if state is not None:
            mood = state.get("mood", 0.0)
            emo = state.get("current_emotion", "NEUTRAL")
            turno = state.get("turno", 0)
            thought = state.get("last_thought", "")
            history = state.get("history", [])

            # Humor
            if mood > 0.6:
                mood_emoji, mood_label = "😄", "Muito Feliz"
            elif mood > 0.2:
                mood_emoji, mood_label = "😊", "Feliz"
            elif mood > -0.2:
                mood_emoji, mood_label = "😐", "Neutra"
            elif mood > -0.6:
                mood_emoji, mood_label = "😔", "Triste"
            else:
                mood_emoji, mood_label = "😡", "Irritada"

            self._mood_emoji.configure(text=mood_emoji)
            self._mood_label.configure(text=mood_label)
            self._mood_bar.set((mood + 1.0) / 2.0)
            self._mood_value.configure(text=f"Mood: {mood:.2f}")

            # Cor da barra
            if mood > 0.3:
                self._mood_bar.configure(progress_color=COLORS["green"])
            elif mood > -0.3:
                self._mood_bar.configure(progress_color=COLORS["purple_neon"])
            else:
                self._mood_bar.configure(progress_color=COLORS["red"])

            # Emoção ativa
            self._emotion_emoji.configure(text=emoji_map.get(emo, "❓"))
            self._emotion_label.configure(text=emo)
            self._emotion_turno.configure(text=f"Turno: {turno}")

            # Pensamento
            if thought:
                self._thought_box.configure(state="normal")
                self._thought_box.delete("1.0", "end")
                self._thought_box.insert("1.0", f"💭 {thought}")
                self._thought_box.configure(state="disabled")

            # Histórico (limpa e recria)
            for lbl in self._history_labels:
                lbl.destroy()
            self._history_labels.clear()

            for i, event in enumerate(reversed(history[-20:])):
                ts = time.strftime("%H:%M:%S", time.localtime(event.get("timestamp", 0)))
                e_name = event.get("emotion", "NEUTRAL")
                emoji = emoji_map.get(e_name, "❓")
                text = f"{ts}  {emoji} {e_name}  (Turno {event.get('turno', 0)})"

                lbl = ctk.CTkLabel(
                    self._history_scroll, text=text,
                    font=FONT_MONO, text_color=COLORS["text_secondary"],
                    anchor="w"
                )
                lbl.grid(row=i, column=0, padx=5, pady=1, sticky="w")
                self._history_labels.append(lbl)

        self.after(1500, self._atualizar)
