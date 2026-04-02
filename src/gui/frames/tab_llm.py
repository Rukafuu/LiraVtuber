"""
Tab Cérebro — Controle de APIs do Terminal.
Hot-swap de LLM Provider/Modelo/Temperatura + TTS config.
Mudanças são salvas no config.json e aplicadas em tempo real.
"""

import customtkinter as ctk
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from src.gui.design import COLORS, FONT_TITLE, FONT_BODY, FONT_SMALL, FONT_MONO
from src.config.config_loader import CONFIG


class TabLLM(ctk.CTkFrame):
    """Cérebro — configuração do terminal em tempo real."""

    def __init__(self, master, **kwargs):
        super().__init__(master, corner_radius=12, fg_color=COLORS["bg_dark"], border_width=1, border_color=COLORS["border"])
        self.grid_columnconfigure(0, weight=1)

        # ─── HEADER ───
        header = ctk.CTkLabel(self, text="🧠  Cérebro — Configuração do Terminal", font=FONT_TITLE, text_color=COLORS["text_primary"])
        header.grid(row=0, column=0, padx=25, pady=(20, 2), sticky="w")
        sub = ctk.CTkLabel(self, text="Altere o provedor e modelo que o terminal usa. Mudanças são aplicadas em tempo real.", font=FONT_SMALL, text_color=COLORS["text_muted"])
        sub.grid(row=1, column=0, padx=25, pady=(0, 12), sticky="w")

        # Scrollable
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
        self.scroll.grid(row=2, column=0, padx=8, pady=(0, 8), sticky="nsew")
        self.scroll.grid_columnconfigure(0, weight=1)
        self.scroll.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=1)

        provedores_llm = ["groq", "google_cloud", "cerebras", "openrouter"]

        # ═══════════════════════════════════════════════════
        # CARD 1: LLM PRINCIPAL
        # ═══════════════════════════════════════════════════
        card_llm = self._card(self.scroll, "🧠  LLM Principal (Chat Terminal)", row=0, col=0, colspan=2)
        card_llm.grid_columnconfigure(1, weight=1)
        card_llm.grid_columnconfigure(3, weight=1)

        self._label(card_llm, "Provedor:", 1, 0)
        self.combo_llm_provedor = self._combo(card_llm, provedores_llm, 1, 1, command=self._on_provedor_change)

        self._label(card_llm, "Modelo:", 1, 2)
        self.combo_llm_modelo = self._combo(card_llm, [""], 1, 3)

        self._label(card_llm, "Temperatura:", 2, 0)
        temp_frame = ctk.CTkFrame(card_llm, fg_color="transparent")
        temp_frame.grid(row=2, column=1, columnspan=3, padx=10, pady=3, sticky="ew")
        self.slider_temp = ctk.CTkSlider(
            temp_frame, from_=0, to=2, number_of_steps=200,
            progress_color=COLORS["purple_neon"], button_color=COLORS["purple_dim"],
            fg_color=COLORS["bg_darkest"], width=280,
            command=self._on_temp_change
        )
        self.slider_temp.pack(side="left", padx=(0, 8))
        self.lbl_temp = ctk.CTkLabel(temp_frame, text="0.00", font=FONT_MONO, text_color=COLORS["purple_neon"])
        self.lbl_temp.pack(side="left")

        # ═══════════════════════════════════════════════════
        # CARD 2: MODELO DE VISÃO
        # ═══════════════════════════════════════════════════
        card_vision = self._card(self.scroll, "👁  Modelo de Visão", row=1, col=0, colspan=2)
        card_vision.grid_columnconfigure(1, weight=1)

        self._label(card_vision, "Modelo Visão:", 1, 0)
        self.combo_visao = self._combo(card_vision, [""], 1, 1)

        # ═══════════════════════════════════════════════════
        # CARD 3: VOZ (TTS)
        # ═══════════════════════════════════════════════════
        card_tts = self._card(self.scroll, "🗣  Voz (TTS)", row=2, col=0, colspan=2)
        card_tts.grid_columnconfigure(1, weight=1)
        card_tts.grid_columnconfigure(3, weight=1)

        self._label(card_tts, "Provedor TTS:", 1, 0)
        self.combo_tts = self._combo(card_tts, ["google", "edge", "azure"], 1, 1)

        self._label(card_tts, "Voz:", 1, 2)
        self.entry_tts_voz = self._entry(card_tts, "ex: pt-BR-Neural2-C", 1, 3)

        self._label(card_tts, "Velocidade:", 2, 0)
        speed_frame = ctk.CTkFrame(card_tts, fg_color="transparent")
        speed_frame.grid(row=2, column=1, columnspan=3, padx=10, pady=3, sticky="ew")
        self.slider_speed = ctk.CTkSlider(
            speed_frame, from_=0.5, to=2.0, number_of_steps=30,
            progress_color=COLORS["blue_neon"], button_color=COLORS["blue_dim"],
            fg_color=COLORS["bg_darkest"], width=280,
            command=self._on_speed_change
        )
        self.slider_speed.pack(side="left", padx=(0, 8))
        self.lbl_speed = ctk.CTkLabel(speed_frame, text="1.00x", font=FONT_MONO, text_color=COLORS["blue_neon"])
        self.lbl_speed.pack(side="left")

        self._label(card_tts, "Pitch:", 3, 0)
        pitch_frame = ctk.CTkFrame(card_tts, fg_color="transparent")
        pitch_frame.grid(row=3, column=1, columnspan=3, padx=10, pady=3, sticky="ew")
        self.slider_pitch = ctk.CTkSlider(
            pitch_frame, from_=-20, to=20, number_of_steps=400,
            progress_color=COLORS["green"], button_color="#166534",
            fg_color=COLORS["bg_darkest"], width=280,
            command=self._on_pitch_change
        )
        self.slider_pitch.pack(side="left", padx=(0, 8))
        self.lbl_pitch = ctk.CTkLabel(pitch_frame, text="0.0", font=FONT_MONO, text_color=COLORS["green"])
        self.lbl_pitch.pack(side="left")

        # ═══════════════════════════════════════════════════
        # BOTÃO APLICAR + STATUS
        # ═══════════════════════════════════════════════════
        btn_frame = ctk.CTkFrame(self.scroll, fg_color="transparent")
        btn_frame.grid(row=3, column=0, columnspan=2, padx=10, pady=(10, 4), sticky="ew")

        self.btn_aplicar = ctk.CTkButton(
            btn_frame, text="⚡ Salvar & Aplicar", width=200, height=36,
            fg_color=COLORS["purple_dim"], hover_color=COLORS["purple_neon"],
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            command=self._aplicar
        )
        self.btn_aplicar.pack(pady=4)

        self.lbl_status = ctk.CTkLabel(btn_frame, text="", font=FONT_SMALL, text_color=COLORS["green"])
        self.lbl_status.pack(pady=(0, 4))

        # Status bar
        status_bar = ctk.CTkFrame(self.scroll, fg_color=COLORS["bg_card"], corner_radius=8, border_width=1, border_color=COLORS["border"])
        status_bar.grid(row=4, column=0, columnspan=2, padx=8, pady=(4, 10), sticky="ew")
        self.lbl_atual = ctk.CTkLabel(status_bar, text="Motor Atual: carregando...", font=FONT_MONO, text_color=COLORS["text_secondary"])
        self.lbl_atual.pack(padx=15, pady=10)

        # Inicializa valores
        self._carregar_settings()
        self._atualizar_status()

    # ═══════════════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════════════

    def _card(self, parent, titulo, row, col, colspan=1):
        card = ctk.CTkFrame(parent, fg_color=COLORS["bg_card"], corner_radius=10, border_width=1, border_color=COLORS["border"])
        card.grid(row=row, column=col, columnspan=colspan, padx=8, pady=6, sticky="nsew")
        lbl = ctk.CTkLabel(card, text=titulo, font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), text_color=COLORS["text_primary"])
        lbl.grid(row=0, column=0, columnspan=4, padx=12, pady=(10, 6), sticky="w")
        return card

    def _label(self, parent, text, row, col):
        ctk.CTkLabel(parent, text=text, font=FONT_BODY, text_color=COLORS["text_secondary"]).grid(row=row, column=col, padx=(12, 4), pady=4, sticky="w")

    def _combo(self, parent, values, row, col, command=None):
        combo = ctk.CTkComboBox(
            parent, values=values, width=200, command=command,
            fg_color=COLORS["bg_darkest"], border_color=COLORS["border"],
            button_color=COLORS["purple_dim"], button_hover_color=COLORS["purple_neon"],
            dropdown_fg_color=COLORS["bg_card"], dropdown_hover_color=COLORS["purple_dark"],
            text_color=COLORS["text_primary"], font=FONT_MONO,
        )
        combo.grid(row=row, column=col, padx=(4, 12), pady=4, sticky="ew")
        return combo

    def _entry(self, parent, placeholder, row, col):
        entry = ctk.CTkEntry(
            parent, placeholder_text=placeholder,
            fg_color=COLORS["bg_darkest"], border_color=COLORS["border"],
            text_color=COLORS["text_primary"], font=FONT_MONO
        )
        entry.grid(row=row, column=col, padx=(4, 12), pady=4, sticky="ew")
        return entry

    # ═══════════════════════════════════════════════════
    # CALLBACKS
    # ═══════════════════════════════════════════════════

    def _on_temp_change(self, v):
        self.lbl_temp.configure(text=f"{v:.2f}")

    def _on_speed_change(self, v):
        self.lbl_speed.configure(text=f"{v:.2f}x")

    def _on_pitch_change(self, v):
        self.lbl_pitch.configure(text=f"{v:.1f}")

    def _carregar_settings(self):
        """Preenche a UI com os dados do config.json."""
        prov_atual = CONFIG.get("LLM_PROVIDER", "groq")
        self.combo_llm_provedor.set(prov_atual)

        temp = CONFIG.get("LLM_TEMPERATURE", 0.7)
        self.slider_temp.set(temp)
        self._on_temp_change(temp)

        # TTS
        tts_prov = CONFIG.get("TTS_PROVIDER", "google")
        self.combo_tts.set(tts_prov)
        self.entry_tts_voz.delete(0, "end")
        self.entry_tts_voz.insert(0, CONFIG.get("GOOGLE_TTS_VOICE", "pt-BR-Neural2-C"))
        speed = CONFIG.get("GOOGLE_TTS_RATE", 1.25)
        self.slider_speed.set(speed)
        self._on_speed_change(speed)
        pitch = CONFIG.get("GOOGLE_TTS_PITCH", 1.4)
        self.slider_pitch.set(pitch)
        self._on_pitch_change(pitch)

        # Popula modelos
        self._on_provedor_change(prov_atual)

    def _on_provedor_change(self, provedor):
        """Atualiza modelos baseado no provedor."""
        sugestoes = {
            "groq": {
                "chat": ["llama-3.1-8b-instant", "meta-llama/llama-4-scout-17b-16e-instruct", "moonshotai/kimi-k2-instruct-0905", "Outro..."],
                "visao": ["meta-llama/llama-4-scout-17b-16e-instruct", "Outro..."]
            },
            "google_cloud": {
                "chat": ["gemini-3.1-pro-preview", "gemini-3-pro-preview", "gemini-3.1-flash-preview", "gemini-3-flash-preview", "gemini-3.1-flash-lite-preview", "gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite", "Outro..."],
                "visao": ["gemini-3.1-pro-preview", "gemini-3-pro-preview", "gemini-3.1-flash-preview", "gemini-3-flash-preview", "gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.5-flash-lite", "Outro..."]
            },
            "openrouter": {
                "chat": ["openai/gpt-5.4", "openai/gpt-5.4-mini", "google/gemini-3.1-flash-lite-preview", "google/gemini-3.1-pro-preview", "google/gemini-2.5-pro", "google/gemini-2.5-flash", "google/gemini-2.5-flash-lite", "x-ai/grok-4.20-beta", "x-ai/grok-4.1-fast", "x-ai/grok-4", "anthropic/claude-opus-4.6", "anthropic/claude-sonnet-4.6", "anthropic/claude-haiku-4.5", "Outro..."],
                "visao": ["google/gemini-3.1-pro-preview", "google/gemini-2.5-flash", "google/gemini-2.5-pro", "x-ai/grok-4.1-fast", "Outro..."]
            },
            "cerebras": {
                "chat": ["qwen-3-235b-a22b-instruct-2507", "llama3.1-8b", "gpt-oss-120b", "zai-glm-4.7", "Outro..."],
                "visao": []
            }
        }

        cats = sugestoes.get(provedor, {})
        dados_prov = CONFIG.get("LLM_PROVIDERS", {})
        dados_prov = dados_prov.get(provedor, {}) if isinstance(dados_prov, dict) else {}

        # Modelo Principal
        self.combo_llm_modelo.configure(values=cats.get("chat", ["Outro..."]))
        self.combo_llm_modelo.set(dados_prov.get("modelo", ""))

        # Modelo Visão
        visao_list = cats.get("visao", [])
        if visao_list:
            self.combo_visao.configure(state="normal", text_color=COLORS["text_primary"], values=visao_list)
            self.combo_visao.set(dados_prov.get("modelo_vision", ""))
        else:
            self.combo_visao.configure(state="normal", values=[""])
            self.combo_visao.set("(Provedor não suporta Visão)")
            self.combo_visao.configure(state="disabled", text_color=COLORS["text_muted"])

    # ═══════════════════════════════════════════════════
    # SALVAR & APLICAR
    # ═══════════════════════════════════════════════════

    def _aplicar(self):
        """Salva as alterações no config.json."""
        provedor = self.combo_llm_provedor.get()
        modelo_chat = self.combo_llm_modelo.get().strip()
        temp = self.slider_temp.get()
        modelo_visao = self.combo_visao.get().strip()

        # Atualiza CONFIG
        CONFIG["LLM_PROVIDER"] = provedor
        CONFIG["LLM_TEMPERATURE"] = float(f"{temp:.2f}")

        providers = CONFIG.get("LLM_PROVIDERS", {})
        if not isinstance(providers, dict):
            providers = {}
        if provedor not in providers:
            providers[provedor] = {}
        if modelo_chat:
            providers[provedor]["modelo"] = modelo_chat
        if modelo_visao and not modelo_visao.startswith("("):
            providers[provedor]["modelo_vision"] = modelo_visao
        CONFIG["LLM_PROVIDERS"] = providers

        # TTS
        tts_prov = self.combo_tts.get()
        tts_voz = self.entry_tts_voz.get().strip()
        tts_speed = self.slider_speed.get()
        tts_pitch = self.slider_pitch.get()

        CONFIG["TTS_PROVIDER"] = tts_prov
        if tts_voz:
            CONFIG["GOOGLE_TTS_VOICE"] = tts_voz
        CONFIG["GOOGLE_TTS_RATE"] = float(f"{tts_speed:.2f}")
        CONFIG["GOOGLE_TTS_PITCH"] = float(f"{tts_pitch:.1f}")

        # Salva no disco
        try:
            CONFIG.save()
            self.lbl_status.configure(text=f"✓ Salvo! ({provedor} / TTS: {tts_prov})", text_color=COLORS["green"])
        except Exception as e:
            self.lbl_status.configure(text=f"Erro ao salvar: {e}", text_color=COLORS["red"])

        self._atualizar_status()

    def _atualizar_status(self):
        prov = CONFIG.get("LLM_PROVIDER", "?").upper()
        providers = CONFIG.get("LLM_PROVIDERS", {})
        prov_data = providers.get(CONFIG.get("LLM_PROVIDER", ""), {}) if isinstance(providers, dict) else {}
        modelo = prov_data.get("modelo", "?") if isinstance(prov_data, dict) else "?"
        tts = CONFIG.get("TTS_PROVIDER", "?").upper()
        self.lbl_atual.configure(text=f"Motor Atual: {prov} / {modelo}  |  TTS: {tts}")
