"""
Tab Cerebro: controle de LLM e TTS do terminal em tempo real.
"""

from __future__ import annotations

import os
import sys
import threading

import customtkinter as ctk

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from src.config.config_loader import CONFIG
from src.core.provider_catalog import (
    find_voice,
    get_default_model,
    get_default_voice,
    get_llm_providers,
    get_model_ids_for_provider,
    get_tts_providers,
    get_voice_ids_for_provider,
)
from src.gui.design import COLORS, FONT_BODY, FONT_MONO, FONT_SMALL, FONT_TITLE
from src.modules.voice.tts_selector import get_tts, get_tts_settings

ELEVENLABS_TTS_MODELS = [
    "eleven_flash_v2_5",
    "eleven_multilingual_v2",
    "eleven_turbo_v2_5",
    "eleven_v3",
]

OPENAI_TTS_MODELS = [
    "gpt-4o-mini-tts",
]


class TabLLM(ctk.CTkFrame):
    """Cerebro: configuracao do terminal em tempo real."""

    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            corner_radius=12,
            fg_color=COLORS["bg_dark"],
            border_width=2,
            border_color=COLORS["border_strong"],
        )
        self.grid_columnconfigure(0, weight=1)

        self._build_layout()
        self._load_settings()
        self._refresh_status()

    def _build_layout(self):
        header = ctk.CTkLabel(
            self,
            text="Cerebro - Configuracao do Terminal",
            font=FONT_TITLE,
            text_color=COLORS["text_primary"],
        )
        header.grid(row=0, column=0, padx=25, pady=(20, 2), sticky="w")

        sub = ctk.CTkLabel(
            self,
            text="Altere provider, modelo, visao e TTS do terminal. As mudancas sao aplicadas em tempo real.",
            font=FONT_SMALL,
            text_color=COLORS["text_muted"],
        )
        sub.grid(row=1, column=0, padx=25, pady=(0, 12), sticky="w")

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
        self.scroll.grid(row=2, column=0, padx=8, pady=(0, 8), sticky="nsew")
        self.scroll.grid_columnconfigure(0, weight=1)
        self.scroll.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._build_llm_card()
        self._build_vision_card()
        self._build_tts_card()
        self._build_actions()
        self._build_status_bar()

    def _build_llm_card(self):
        card = self._card(self.scroll, "LLM principal (chat terminal)", row=0, col=0, colspan=2)
        card.grid_columnconfigure(1, weight=1)
        card.grid_columnconfigure(3, weight=1)

        self._label(card, "Provider:", 1, 0)
        self.combo_llm_provider = self._combo(card, get_llm_providers(), 1, 1, command=self._on_llm_provider_change)

        self._label(card, "Modelo:", 1, 2)
        self.combo_llm_model = self._combo(card, [""], 1, 3)

        self._label(card, "Filtro:", 2, 0)
        self.entry_model_filter = self._entry(card, "Filtrar modelos por nome ou familia", 2, 1, colspan=3)
        self.entry_model_filter.bind("<KeyRelease>", lambda _e: self._refresh_model_lists())

        self._label(card, "Temperatura:", 3, 0)
        temp_frame = ctk.CTkFrame(card, fg_color="transparent")
        temp_frame.grid(row=3, column=1, columnspan=3, padx=10, pady=3, sticky="ew")
        self.slider_temp = ctk.CTkSlider(
            temp_frame,
            from_=0,
            to=2,
            number_of_steps=200,
            progress_color=COLORS["purple_neon"],
            button_color=COLORS["purple_dim"],
            fg_color=COLORS["bg_darkest"],
            width=280,
            command=self._on_temp_change,
        )
        self.slider_temp.pack(side="left", padx=(0, 8))
        self.lbl_temp = ctk.CTkLabel(temp_frame, text="0.00", font=FONT_MONO, text_color=COLORS["purple_neon"])
        self.lbl_temp.pack(side="left")

    def _build_vision_card(self):
        card = self._card(self.scroll, "Modelo de visao", row=1, col=0, colspan=2)
        card.grid_columnconfigure(1, weight=1)
        self._label(card, "Modelo de visao:", 1, 0)
        self.combo_vision_model = self._combo(card, [""], 1, 1)

    def _build_tts_card(self):
        card = self._card(self.scroll, "Voz (TTS)", row=2, col=0, colspan=2)
        card.grid_columnconfigure(1, weight=1)
        card.grid_columnconfigure(3, weight=1)

        self._label(card, "Provider TTS:", 1, 0)
        self.combo_tts_provider = self._combo(card, get_tts_providers(), 1, 1, command=self._on_tts_provider_change)

        self._label(card, "Voz:", 1, 2)
        self.combo_tts_voice = self._combo(card, [""], 1, 3)

        self._label(card, "Modelo TTS:", 2, 0)
        self.combo_tts_model = self._combo(card, [""], 2, 1)
        self.combo_tts_model.grid_configure(columnspan=3)

        self._label(card, "Filtro de voz:", 3, 0)
        self.entry_voice_filter = self._entry(card, "Filtrar vozes por nome ou locale", 3, 1, colspan=3)
        self.entry_voice_filter.bind("<KeyRelease>", lambda _e: self._refresh_voice_list())

        self._label(card, "Velocidade:", 4, 0)
        speed_frame = ctk.CTkFrame(card, fg_color="transparent")
        speed_frame.grid(row=4, column=1, columnspan=3, padx=10, pady=3, sticky="ew")
        self.slider_speed = ctk.CTkSlider(
            speed_frame,
            from_=0.5,
            to=2.0,
            number_of_steps=30,
            progress_color=COLORS["blue_neon"],
            button_color=COLORS["blue_dim"],
            fg_color=COLORS["bg_darkest"],
            width=280,
            command=self._on_speed_change,
        )
        self.slider_speed.pack(side="left", padx=(0, 8))
        self.lbl_speed = ctk.CTkLabel(speed_frame, text="1.00x", font=FONT_MONO, text_color=COLORS["blue_neon"])
        self.lbl_speed.pack(side="left")

        self._label(card, "Pitch:", 5, 0)
        pitch_frame = ctk.CTkFrame(card, fg_color="transparent")
        pitch_frame.grid(row=5, column=1, columnspan=3, padx=10, pady=3, sticky="ew")
        self.slider_pitch = ctk.CTkSlider(
            pitch_frame,
            from_=-20,
            to=20,
            number_of_steps=400,
            progress_color=COLORS["green"],
            button_color="#166534",
            fg_color=COLORS["bg_darkest"],
            width=280,
            command=self._on_pitch_change,
        )
        self.slider_pitch.pack(side="left", padx=(0, 8))
        self.lbl_pitch = ctk.CTkLabel(pitch_frame, text="0.0", font=FONT_MONO, text_color=COLORS["green"])
        self.lbl_pitch.pack(side="left")

        self._label(card, "Stability:", 6, 0)
        stability_frame = ctk.CTkFrame(card, fg_color="transparent")
        stability_frame.grid(row=6, column=1, columnspan=3, padx=10, pady=3, sticky="ew")
        self.slider_tts_stability = ctk.CTkSlider(
            stability_frame,
            from_=0.0,
            to=1.0,
            number_of_steps=100,
            progress_color=COLORS["purple_neon"],
            button_color=COLORS["purple_dim"],
            fg_color=COLORS["bg_darkest"],
            width=280,
            command=self._on_tts_stability_change,
        )
        self.slider_tts_stability.pack(side="left", padx=(0, 8))
        self.lbl_tts_stability = ctk.CTkLabel(stability_frame, text="0.50", font=FONT_MONO, text_color=COLORS["purple_neon"])
        self.lbl_tts_stability.pack(side="left")

        self._label(card, "Similarity:", 7, 0)
        similarity_frame = ctk.CTkFrame(card, fg_color="transparent")
        similarity_frame.grid(row=7, column=1, columnspan=3, padx=10, pady=3, sticky="ew")
        self.slider_tts_similarity = ctk.CTkSlider(
            similarity_frame,
            from_=0.0,
            to=1.0,
            number_of_steps=100,
            progress_color=COLORS["blue_neon"],
            button_color=COLORS["blue_dim"],
            fg_color=COLORS["bg_darkest"],
            width=280,
            command=self._on_tts_similarity_change,
        )
        self.slider_tts_similarity.pack(side="left", padx=(0, 8))
        self.lbl_tts_similarity = ctk.CTkLabel(similarity_frame, text="0.75", font=FONT_MONO, text_color=COLORS["blue_neon"])
        self.lbl_tts_similarity.pack(side="left")

        self._label(card, "Style:", 8, 0)
        style_frame = ctk.CTkFrame(card, fg_color="transparent")
        style_frame.grid(row=8, column=1, columnspan=3, padx=10, pady=3, sticky="ew")
        self.slider_tts_style = ctk.CTkSlider(
            style_frame,
            from_=0.0,
            to=1.0,
            number_of_steps=100,
            progress_color=COLORS["green"],
            button_color="#166534",
            fg_color=COLORS["bg_darkest"],
            width=280,
            command=self._on_tts_style_change,
        )
        self.slider_tts_style.pack(side="left", padx=(0, 8))
        self.lbl_tts_style = ctk.CTkLabel(style_frame, text="0.00", font=FONT_MONO, text_color=COLORS["green"])
        self.lbl_tts_style.pack(side="left")

        self.chk_tts_speaker_boost = ctk.CTkCheckBox(
            card,
            text="Speaker boost (ElevenLabs)",
            checkbox_width=18,
            checkbox_height=18,
            border_width=2,
            corner_radius=5,
            fg_color=COLORS["purple_dim"],
            hover_color=COLORS["purple_neon"],
            border_color=COLORS["border"],
            text_color=COLORS["text_secondary"],
            font=FONT_BODY,
        )
        self.chk_tts_speaker_boost.grid(row=9, column=0, columnspan=4, padx=12, pady=(4, 2), sticky="w")

        self.btn_test_tts = ctk.CTkButton(
            card,
            text="Testar Voz",
            width=140,
            height=34,
            fg_color=COLORS["blue_dim"],
            hover_color=COLORS["blue_neon"],
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self._test_tts_voice,
        )
        self.btn_test_tts.grid(row=10, column=0, padx=12, pady=(4, 4), sticky="w")

        self.lbl_tts_note = ctk.CTkLabel(
            card,
            text="Pitch: nativo",
            font=FONT_SMALL,
            text_color=COLORS["text_muted"],
        )
        self.lbl_tts_note.grid(row=10, column=1, columnspan=3, padx=12, pady=(0, 8), sticky="w")

    def _build_actions(self):
        btn_frame = ctk.CTkFrame(self.scroll, fg_color="transparent")
        btn_frame.grid(row=3, column=0, columnspan=2, padx=10, pady=(10, 4), sticky="ew")

        self.btn_apply = ctk.CTkButton(
            btn_frame,
            text="Salvar e aplicar",
            width=200,
            height=36,
            fg_color=COLORS["purple_dim"],
            hover_color=COLORS["purple_neon"],
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            command=self._save,
        )
        self.btn_apply.pack(pady=4)

        self.lbl_status = ctk.CTkLabel(btn_frame, text="", font=FONT_SMALL, text_color=COLORS["green"])
        self.lbl_status.pack(pady=(0, 4))

    def _build_status_bar(self):
        status_bar = ctk.CTkFrame(
            self.scroll,
            fg_color=COLORS["bg_card"],
            corner_radius=10,
            border_width=2,
            border_color=COLORS["border"],
        )
        status_bar.grid(row=4, column=0, columnspan=2, padx=8, pady=(4, 10), sticky="ew")
        self.lbl_current = ctk.CTkLabel(
            status_bar,
            text="Motor atual: carregando...",
            font=FONT_MONO,
            text_color=COLORS["text_secondary"],
        )
        self.lbl_current.pack(padx=15, pady=10)

    def _card(self, parent, title, row, col, colspan=1):
        card = ctk.CTkFrame(parent, fg_color=COLORS["bg_card"], corner_radius=12, border_width=2, border_color=COLORS["border"])
        card.grid(row=row, column=col, columnspan=colspan, padx=8, pady=6, sticky="nsew")
        label = ctk.CTkLabel(
            card,
            text=title,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=COLORS["text_primary"],
        )
        label.grid(row=0, column=0, columnspan=4, padx=12, pady=(10, 6), sticky="w")
        return card

    def _label(self, parent, text, row, col):
        ctk.CTkLabel(parent, text=text, font=FONT_BODY, text_color=COLORS["text_secondary"]).grid(
            row=row,
            column=col,
            padx=(12, 4),
            pady=4,
            sticky="w",
        )

    def _combo(self, parent, values, row, col, command=None):
        combo = ctk.CTkComboBox(
            parent,
            values=values,
            width=220,
            command=command,
            fg_color=COLORS["bg_darkest"],
            border_color=COLORS["border"],
            button_color=COLORS["purple_dim"],
            button_hover_color=COLORS["purple_neon"],
            dropdown_fg_color=COLORS["bg_card"],
            dropdown_hover_color=COLORS["purple_dark"],
            text_color=COLORS["text_primary"],
            font=FONT_MONO,
        )
        combo.grid(row=row, column=col, padx=(4, 12), pady=4, sticky="ew")
        return combo

    def _entry(self, parent, placeholder, row, col, colspan=1):
        entry = ctk.CTkEntry(
            parent,
            placeholder_text=placeholder,
            fg_color=COLORS["bg_darkest"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            font=FONT_MONO,
        )
        entry.grid(row=row, column=col, columnspan=colspan, padx=(4, 12), pady=4, sticky="ew")
        return entry

    def _provider_block(self, provider: str) -> dict:
        providers = CONFIG.get("LLM_PROVIDERS", {})
        if not isinstance(providers, dict):
            providers = {}
        block = providers.get(provider, {})
        if not isinstance(block, dict):
            block = {}
        providers[provider] = block
        CONFIG["LLM_PROVIDERS"] = providers
        return block

    def _parse_rate(self, value, provider: str) -> float:
        if provider in {"google", "openai", "elevenlabs"}:
            try:
                return float(value)
            except (TypeError, ValueError):
                return 1.0
        if isinstance(value, str) and value.endswith("%"):
            try:
                return 1.0 + (int(value[:-1]) / 100.0)
            except ValueError:
                return 1.0
        try:
            return float(value)
        except (TypeError, ValueError):
            return 1.0

    def _parse_pitch(self, value, provider: str) -> float:
        if provider in {"google", "openai"}:
            try:
                return float(value)
            except (TypeError, ValueError):
                return 0.0
        if isinstance(value, str) and value.lower().endswith("hz"):
            try:
                return float(value[:-2])
            except ValueError:
                return 0.0
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _format_provider_rate(self, provider: str, value: float):
        if provider in {"google", "openai", "elevenlabs"}:
            return float(f"{value:.2f}")
        percent = int(round((value - 1.0) * 100))
        signal = "+" if percent >= 0 else ""
        return f"{signal}{percent}%"

    def _format_provider_pitch(self, provider: str, value: float):
        if provider in {"google", "openai"}:
            return float(f"{value:.1f}")
        rounded = int(round(value))
        signal = "+" if rounded >= 0 else ""
        return f"{signal}{rounded}Hz"

    def _current_tts_settings(self, provider: str) -> dict:
        tts_settings = get_tts_settings()
        block = tts_settings.get(provider, {})
        return block if isinstance(block, dict) else {}

    def _on_temp_change(self, value):
        self.lbl_temp.configure(text=f"{value:.2f}")

    def _on_speed_change(self, value):
        self.lbl_speed.configure(text=f"{value:.2f}x")

    def _on_pitch_change(self, value):
        self.lbl_pitch.configure(text=f"{value:.1f}")

    def _on_tts_stability_change(self, value):
        self.lbl_tts_stability.configure(text=f"{value:.2f}")

    def _on_tts_similarity_change(self, value):
        self.lbl_tts_similarity.configure(text=f"{value:.2f}")

    def _on_tts_style_change(self, value):
        self.lbl_tts_style.configure(text=f"{value:.2f}")

    def _load_settings(self):
        provider = CONFIG.get("LLM_PROVIDER", "google_cloud")
        self.combo_llm_provider.set(provider)

        temp = CONFIG.get("LLM_TEMPERATURE", 0.85)
        self.slider_temp.set(temp)
        self._on_temp_change(temp)

        self._on_llm_provider_change(provider)

        tts_provider = CONFIG.get("TTS_PROVIDER", "google")
        self.combo_tts_provider.set(tts_provider)
        self._on_tts_provider_change(tts_provider)

    def _ensure_selected_value(self, values: list[str], selected: str) -> list[str]:
        items = list(values)
        if selected and selected not in items and selected != "Outro...":
            items.insert(0, selected)
        return items

    def _refresh_model_lists(self):
        provider = self.combo_llm_provider.get().strip()
        query = self.entry_model_filter.get().strip()
        provider_data = self._provider_block(provider)
        selected_model = self.combo_llm_model.get().strip() or provider_data.get("modelo") or provider_data.get("modelo_chat", "")
        selected_vision = self.combo_vision_model.get().strip() or provider_data.get("modelo_vision", "")

        model_values = self._ensure_selected_value(get_model_ids_for_provider(provider, query=query), selected_model)
        self.combo_llm_model.configure(values=model_values)
        self.combo_llm_model.set(selected_model or get_default_model(provider))

        vision_values = self._ensure_selected_value(get_model_ids_for_provider(provider, vision_only=True, query=query), selected_vision)
        if len(vision_values) > 1:
            self.combo_vision_model.configure(state="normal", text_color=COLORS["text_primary"], values=vision_values)
            self.combo_vision_model.set(selected_vision or get_default_model(provider, vision_only=True))
        else:
            self.combo_vision_model.configure(state="normal", values=[""])
            self.combo_vision_model.set("(provider sem visao)")
            self.combo_vision_model.configure(state="disabled", text_color=COLORS["text_muted"])

    def _on_llm_provider_change(self, provider):
        self._refresh_model_lists()

    def _refresh_voice_list(self):
        provider = self.combo_tts_provider.get().strip()
        query = self.entry_voice_filter.get().strip()
        settings = self._current_tts_settings(provider)
        selected_voice = self.combo_tts_voice.get().strip() or settings.get("voice_id") or settings.get("voice", get_default_voice(provider))
        if provider == "elevenlabs":
            voices = [selected_voice] if selected_voice else [""]
        else:
            voices = self._ensure_selected_value(get_voice_ids_for_provider(provider, query=query), selected_voice)
        self.combo_tts_voice.configure(values=voices or [selected_voice or ""])
        if selected_voice:
            self.combo_tts_voice.set(selected_voice)

        voice_spec = find_voice(provider, selected_voice)
        pitch_mode = "native"
        supports_pitch = True
        if provider == "elevenlabs":
            pitch_mode = "unsupported"
            supports_pitch = False
        elif voice_spec:
            pitch_mode = voice_spec.pitch_mode
            supports_pitch = voice_spec.supports_pitch
        elif provider == "openai":
            pitch_mode = "style"
            supports_pitch = False

        self.slider_pitch.configure(state="normal" if supports_pitch else "disabled")
        if provider == "elevenlabs":
            self.lbl_tts_note.configure(
                text="Pitch: indisponivel. Flash v2.5 e o modelo rapido recomendado. Speed nativa: 0.70 a 1.20.",
                text_color=COLORS["text_muted"],
            )
        else:
            self.lbl_tts_note.configure(
                text=(
                    "Pitch: indisponivel neste provider"
                    if pitch_mode == "unsupported"
                    else "Pitch: por estilo/instrucao"
                    if pitch_mode == "style"
                    else "Pitch: nativo"
                ),
                text_color=COLORS["text_muted"],
            )

    def _refresh_tts_controls_visibility(self, provider: str):
        is_elevenlabs = provider == "elevenlabs"
        is_openai = provider == "openai"
        tts_settings = self._current_tts_settings(provider)
        selected_model = str(tts_settings.get("model_id") or tts_settings.get("model") or "").strip()

        model_values = [selected_model] if selected_model else [""]
        model_state = "disabled"
        if is_elevenlabs:
            model_values = self._ensure_selected_value(ELEVENLABS_TTS_MODELS, selected_model or "eleven_flash_v2_5")
            model_state = "normal"
        elif is_openai:
            model_values = self._ensure_selected_value(OPENAI_TTS_MODELS, selected_model or "gpt-4o-mini-tts")
            model_state = "normal"

        self.combo_tts_model.configure(values=model_values or [selected_model or ""], state=model_state)
        self.combo_tts_model.set(selected_model or (model_values[0] if model_values else ""))

        self.slider_tts_stability.set(float(tts_settings.get("stability", 0.5)))
        self._on_tts_stability_change(float(tts_settings.get("stability", 0.5)))
        self.slider_tts_similarity.set(float(tts_settings.get("similarity_boost", 0.75)))
        self._on_tts_similarity_change(float(tts_settings.get("similarity_boost", 0.75)))
        self.slider_tts_style.set(float(tts_settings.get("style", 0.0)))
        self._on_tts_style_change(float(tts_settings.get("style", 0.0)))
        self.chk_tts_speaker_boost.select() if bool(tts_settings.get("speaker_boost", True)) else self.chk_tts_speaker_boost.deselect()

        advanced_state = "normal" if is_elevenlabs else "disabled"
        for widget in (self.slider_tts_stability, self.slider_tts_similarity, self.slider_tts_style, self.chk_tts_speaker_boost):
            widget.configure(state=advanced_state)

        if is_elevenlabs:
            self.entry_voice_filter.configure(placeholder_text="Voice ID manual da ElevenLabs")
            self.slider_speed.configure(from_=0.7, to=1.2, number_of_steps=50)
            speed_value = min(1.2, max(0.7, float(self.slider_speed.get())))
            self.slider_speed.set(speed_value)
            self._on_speed_change(speed_value)
            self.lbl_tts_note.configure(
                text="Pitch: indisponivel. Flash v2.5 e o modelo rapido recomendado. Speed nativa: 0.70 a 1.20.",
                text_color=COLORS["text_muted"],
            )
        elif is_openai:
            self.entry_voice_filter.configure(placeholder_text="Filtrar vozes por nome ou locale")
            self.slider_speed.configure(from_=0.5, to=2.0, number_of_steps=30)
            self.lbl_tts_note.configure(
                text="Pitch: por estilo/instrucao. Modelo TTS selecionavel neste provider.",
                text_color=COLORS["text_muted"],
            )
        else:
            self.entry_voice_filter.configure(placeholder_text="Filtrar vozes por nome ou locale")
            self.slider_speed.configure(from_=0.5, to=2.0, number_of_steps=30)

    def _on_tts_provider_change(self, provider):
        settings = self._current_tts_settings(provider)
        speed = self._parse_rate(settings.get("rate", 1.0), provider)
        pitch = self._parse_pitch(settings.get("pitch", 0.0), provider)
        self.slider_speed.set(speed)
        self._on_speed_change(speed)
        self.slider_pitch.set(pitch)
        self._on_pitch_change(pitch)
        self._refresh_voice_list()
        self._refresh_tts_controls_visibility(provider)

    def _save_tts_settings(self, provider: str):
        tts_settings = get_tts_settings()
        block = tts_settings.get(provider, {})
        if not isinstance(block, dict):
            block = {}

        selected_voice = self.combo_tts_voice.get().strip() or get_default_voice(provider)
        block["voice"] = selected_voice
        block["rate"] = self._format_provider_rate(provider, self.slider_speed.get())
        if self.slider_pitch.cget("state") != "disabled":
            block["pitch"] = self._format_provider_pitch(provider, self.slider_pitch.get())
        else:
            block["pitch"] = 0.0

        if provider == "elevenlabs":
            block["voice_id"] = selected_voice
            block["model_id"] = self.combo_tts_model.get().strip() or block.get("model_id") or "eleven_flash_v2_5"
            block["rate"] = float(f"{self.slider_speed.get():.2f}")
            block["pitch"] = 0.0
            block["stability"] = float(f"{self.slider_tts_stability.get():.2f}")
            block["similarity_boost"] = float(f"{self.slider_tts_similarity.get():.2f}")
            block["style"] = float(f"{self.slider_tts_style.get():.2f}")
            block["speaker_boost"] = bool(self.chk_tts_speaker_boost.get())
            CONFIG["ELEVENLABS_VOICE_ID"] = block["voice_id"]
        elif provider == "google":
            block["language_code"] = "pt-BR"
            CONFIG["GOOGLE_TTS_VOICE"] = block["voice"]
            CONFIG["GOOGLE_TTS_LANG"] = "pt-BR"
            CONFIG["GOOGLE_TTS_RATE"] = float(self.slider_speed.get())
            CONFIG["GOOGLE_TTS_PITCH"] = float(self.slider_pitch.get())
        elif provider == "edge":
            block.setdefault("volume", "+0%")
        elif provider == "openai":
            block["model"] = self.combo_tts_model.get().strip() or block.get("model") or "gpt-4o-mini-tts"
            block["style"] = "natural e clara"

        tts_settings[provider] = block
        CONFIG["TTS_SETTINGS"] = tts_settings
        CONFIG["TTS_PROVIDER"] = provider

    def _test_tts_voice(self):
        provider = self.combo_tts_provider.get().strip()
        try:
            self._save_tts_settings(provider)
            CONFIG.save()
            tts = get_tts(provider, force_reload=True)
        except Exception as exc:
            self.lbl_status.configure(text=f"Falha ao preparar teste de voz: {exc}", text_color=COLORS["red"])
            return

        frase = "Oi, eu sou a Hana. Hoje eu vou falar com voce de um jeitinho doce e natural."

        def _run():
            ok = False
            try:
                ok = tts.falar(frase)
            except Exception:
                ok = False
            self.after(
                0,
                lambda: self.lbl_status.configure(
                    text="Teste de voz concluido." if ok else "Falha ao testar a voz atual.",
                    text_color=COLORS["green"] if ok else COLORS["red"],
                ),
            )

        self.lbl_status.configure(text="Testando voz atual...", text_color=COLORS["blue_neon"])
        threading.Thread(target=_run, daemon=True, name="TabLLM-TestTTS").start()

    def _save(self):
        provider = self.combo_llm_provider.get().strip()
        model = self.combo_llm_model.get().strip()
        temperature = float(f"{self.slider_temp.get():.2f}")
        vision_model = self.combo_vision_model.get().strip()

        CONFIG["LLM_PROVIDER"] = provider
        CONFIG["LLM_TEMPERATURE"] = temperature

        providers = CONFIG.get("LLM_PROVIDERS", {})
        if not isinstance(providers, dict):
            providers = {}
        block = providers.get(provider, {})
        if not isinstance(block, dict):
            block = {}
        if model:
            block["modelo"] = model
            block["modelo_chat"] = model
        if vision_model and not vision_model.startswith("("):
            block["modelo_vision"] = vision_model
        providers[provider] = block
        CONFIG["LLM_PROVIDERS"] = providers

        tts_provider = self.combo_tts_provider.get().strip()
        self._save_tts_settings(tts_provider)

        try:
            CONFIG.save()
            get_tts(tts_provider, force_reload=True)
            self.lbl_status.configure(text=f"Salvo com sucesso ({provider} / TTS: {tts_provider})", text_color=COLORS["green"])
        except Exception as exc:
            self.lbl_status.configure(text=f"Erro ao salvar: {exc}", text_color=COLORS["red"])

        self._refresh_status()

    def _refresh_status(self):
        provider = str(CONFIG.get("LLM_PROVIDER", "?")).upper()
        providers = CONFIG.get("LLM_PROVIDERS", {})
        provider_data = providers.get(CONFIG.get("LLM_PROVIDER", ""), {}) if isinstance(providers, dict) else {}
        model = provider_data.get("modelo", "?") if isinstance(provider_data, dict) else "?"
        tts_provider = str(CONFIG.get("TTS_PROVIDER", "?")).upper()
        self.lbl_current.configure(text=f"Motor atual: {provider} / {model}  |  TTS: {tts_provider}")
