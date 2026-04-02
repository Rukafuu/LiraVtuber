"""
Tab Chat — Terminal de Chat visual com a Hana.
Provedor/modelo independente do terminal. Formatação rica, envio de arquivos/imagens, TTS por mensagem.
"""

import threading
import time
import re
import json
import base64
import customtkinter as ctk
from tkinter import filedialog
import logging

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from src.gui.design import COLORS, FONT_TITLE, FONT_BODY, FONT_SMALL, FONT_MONO
from src.config.config_loader import CONFIG

logger = logging.getLogger(__name__)

try:
    from PIL import Image as PILImage
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


# ═══════════════════════════════════════════════════
# BUBBLE COLORS
# ═══════════════════════════════════════════════════
BUBBLE_USER = "#1a2744"
BUBBLE_HANA = "#1f1833"
BUBBLE_BORDER_USER = "#2563eb"
BUBBLE_BORDER_HANA = "#7c3aed"


class TabChat(ctk.CTkFrame):
    """Terminal de Chat visual — conversa com a Hana pela GUI."""

    def __init__(self, master, **kwargs):
        super().__init__(master, corner_radius=12, fg_color=COLORS["bg_dark"], border_width=1, border_color=COLORS["border"])
        self._ultima_resposta = ""
        self._anexos = []
        self._tk_images = []
        self._llm_instance = None
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        # ─── HEADER ───
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, padx=25, pady=(15, 0), sticky="ew")
        header = ctk.CTkLabel(header_frame, text="💬  Terminal Chat", font=FONT_TITLE, text_color=COLORS["text_primary"])
        header.pack(side="left")

        # ─── TOOLBAR: Provedor do Chat + TTS ───
        toolbar = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=8, height=45)
        toolbar.grid(row=1, column=0, padx=15, pady=(8, 5), sticky="ew")

        # Provedor do Chat (independente do terminal)
        ctk.CTkLabel(toolbar, text="Provedor:", font=FONT_SMALL, text_color=COLORS["text_muted"]).pack(side="left", padx=(10, 3))
        self.combo_chat_prov = ctk.CTkComboBox(
            toolbar, values=["groq", "google_cloud", "cerebras", "openrouter"], width=130,
            fg_color=COLORS["bg_darkest"], border_color=COLORS["border"],
            button_color=COLORS["purple_dim"], button_hover_color=COLORS["purple_neon"],
            dropdown_fg_color=COLORS["bg_card"], dropdown_hover_color=COLORS["purple_dark"],
            text_color=COLORS["text_primary"], font=FONT_SMALL,
            command=self._on_chat_prov_change
        )
        self.combo_chat_prov.pack(side="left", padx=(0, 8))

        ctk.CTkLabel(toolbar, text="Modelo:", font=FONT_SMALL, text_color=COLORS["text_muted"]).pack(side="left", padx=(0, 3))
        self.combo_chat_modelo = ctk.CTkComboBox(
            toolbar, values=[""], width=200,
            fg_color=COLORS["bg_darkest"], border_color=COLORS["border"],
            button_color=COLORS["purple_dim"], button_hover_color=COLORS["purple_neon"],
            dropdown_fg_color=COLORS["bg_card"], dropdown_hover_color=COLORS["purple_dark"],
            text_color=COLORS["text_primary"], font=FONT_SMALL,
        )
        self.combo_chat_modelo.pack(side="left", padx=(0, 10))

        # Separador
        sep = ctk.CTkFrame(toolbar, width=1, height=24, fg_color=COLORS["border"])
        sep.pack(side="left", padx=5)

        # Botão parar fala
        self.btn_stop_tts = ctk.CTkButton(
            toolbar, text="⏹ Parar", width=80, height=28,
            fg_color=COLORS["bg_darkest"], hover_color=COLORS["red"],
            text_color=COLORS["text_secondary"], border_width=1, border_color=COLORS["border"],
            font=FONT_SMALL,
            command=self._parar_fala
        )
        self.btn_stop_tts.pack(side="right", padx=8)

        # ─── STATUS BAR ───
        self.status_bar = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=6, height=24)
        self.status_bar.grid(row=2, column=0, padx=15, pady=(2, 4), sticky="ew")
        self.lbl_chat_status = ctk.CTkLabel(
            self.status_bar, text="Chat pronto — provedor independente do terminal",
            font=FONT_SMALL, text_color=COLORS["text_muted"]
        )
        self.lbl_chat_status.pack(side="left", padx=10, pady=3)

        # ─── ÁREA DE MENSAGENS ───
        self.chat_scroll = ctk.CTkScrollableFrame(
            self,
            fg_color=COLORS["bg_darkest"],
            corner_radius=10,
            border_width=1,
            border_color=COLORS["border"],
            scrollbar_button_color=COLORS["purple_dim"],
            scrollbar_button_hover_color=COLORS["purple_neon"],
        )
        self.chat_scroll.grid(row=3, column=0, padx=15, pady=(0, 8), sticky="nsew")
        self.chat_scroll.grid_columnconfigure(0, weight=1)
        self._bubble_row = 0

        # ─── CONTAINER ANEXO ───
        self.frame_anexo = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=8, height=36)
        self.lbl_anexo = ctk.CTkLabel(self.frame_anexo, text="📎 Arquivo:", font=FONT_SMALL, text_color=COLORS["text_secondary"])
        self.lbl_anexo.pack(side="left", padx=(15, 10), pady=4)
        self.btn_cancelar_anexo = ctk.CTkButton(
            self.frame_anexo, text="✖", width=24, height=24,
            fg_color="transparent", hover_color="#552222", text_color="#ff5555",
            command=self._cancelar_anexo
        )
        self.btn_cancelar_anexo.pack(side="right", padx=10)

        # ─── BARRA DE INPUT ───
        input_frame = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=10, border_width=1, border_color=COLORS["border"], height=50)
        input_frame.grid(row=5, column=0, padx=15, pady=(0, 15), sticky="ew")
        input_frame.grid_columnconfigure(2, weight=1)

        # Botão microfone
        self.btn_mic = ctk.CTkButton(
            input_frame, text="🎙", width=40, height=36,
            fg_color="transparent", hover_color=COLORS["purple_dark"],
            text_color=COLORS["text_muted"], font=("Segoe UI", 18),
            command=self._gravar_audio
        )
        self.btn_mic.grid(row=0, column=0, padx=(8, 0), pady=8)

        # Botão de anexo
        self.btn_anexo = ctk.CTkButton(
            input_frame, text="📎", width=40, height=36,
            fg_color="transparent", hover_color=COLORS["bg_card_hover"],
            text_color=COLORS["text_muted"], font=("Segoe UI", 16),
            command=self._abrir_anexo
        )
        self.btn_anexo.grid(row=0, column=1, padx=(0, 0), pady=8)

        # Campo de texto
        self.entry_msg = ctk.CTkEntry(
            input_frame, placeholder_text="Digite uma mensagem para a Hana...",
            fg_color=COLORS["bg_darkest"], border_width=0,
            text_color=COLORS["text_primary"], font=FONT_BODY, height=36
        )
        self.entry_msg.grid(row=0, column=2, padx=8, pady=8, sticky="ew")
        self.entry_msg.bind("<Return>", lambda e: self._enviar())

        # Botão enviar
        self.btn_enviar = ctk.CTkButton(
            input_frame, text="Enviar  ➤", width=100, height=36,
            fg_color=COLORS["purple_dim"], hover_color=COLORS["purple_neon"],
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            command=self._enviar
        )
        self.btn_enviar.grid(row=0, column=3, padx=(0, 8), pady=8)

        # Mensagem inicial
        self._adicionar_msg("system", "Hana", "Hana Control Center — Chat ativo. Digite ou use o microfone 🎙")

        # Carrega config do chat
        self._carregar_config_chat()

    # ═══════════════════════════════════════════════════
    # CONFIG DO CHAT
    # ═══════════════════════════════════════════════════

    def _carregar_config_chat(self):
        """Carrega provedor/modelo do chat do config.json."""
        chat_cfg = CONFIG.get("CHAT", {})
        if not isinstance(chat_cfg, dict):
            chat_cfg = {}

        prov = chat_cfg.get("LLM_PROVIDER", CONFIG.get("LLM_PROVIDER", "openrouter"))
        modelo = chat_cfg.get("LLM_MODEL", "")

        self.combo_chat_prov.set(prov)
        self._on_chat_prov_change(prov)
        if modelo:
            self.combo_chat_modelo.set(modelo)

    def _on_chat_prov_change(self, provedor):
        """Atualiza modelos disponíveis para o chat."""
        sugestoes = {
            "groq": ["llama-3.1-8b-instant", "meta-llama/llama-4-scout-17b-16e-instruct", "moonshotai/kimi-k2-instruct-0905", "Outro..."],
            "google_cloud": ["gemini-3.1-pro-preview", "gemini-3-pro-preview", "gemini-3.1-flash-preview", "gemini-3-flash-preview", "gemini-3.1-flash-lite-preview", "gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash", "Outro..."],
            "openrouter": ["openai/gpt-5.4", "openai/gpt-5.4-mini", "google/gemini-3.1-flash-lite-preview", "google/gemini-3.1-pro-preview", "google/gemini-2.5-pro", "google/gemini-2.5-flash", "google/gemini-2.5-flash-lite", "x-ai/grok-4.20-beta", "x-ai/grok-4.1-fast", "x-ai/grok-4", "anthropic/claude-opus-4.6", "anthropic/claude-sonnet-4.6", "anthropic/claude-haiku-4.5", "Outro..."],
            "cerebras": ["qwen-3-235b-a22b-instruct-2507", "llama3.1-8b", "gpt-oss-120b", "zai-glm-4.7", "Outro..."],
        }
        self.combo_chat_modelo.configure(values=sugestoes.get(provedor, ["Outro..."]))
        # Reseta para primeiro modelo
        models = sugestoes.get(provedor, [])
        if models:
            self.combo_chat_modelo.set(models[0])
        self._llm_instance = None  # Force re-creation

    def _get_chat_llm(self):
        """Obtém uma instância de LLM para o chat (independente do terminal)."""
        if self._llm_instance:
            return self._llm_instance

        prov = self.combo_chat_prov.get().lower()
        modelo = self.combo_chat_modelo.get().strip()

        try:
            if prov == "groq":
                from src.providers.groq_provider import GroqProvider
                llm = GroqProvider()
            elif prov == "google_cloud":
                from src.providers.google_provider import GoogleProvider
                llm = GoogleProvider()
            elif prov == "cerebras":
                from src.providers.cerebras_provider import CerebrasProvider
                llm = CerebrasProvider()
            elif prov == "openrouter":
                from src.providers.openrouter_provider import OpenRouterProvider
                llm = OpenRouterProvider()
            else:
                return None

            # Override the model if user selected a different one
            if modelo and modelo != "Outro...":
                llm.modelo_chat = modelo

            self._llm_instance = llm

            # Salvar config do chat
            chat_cfg = CONFIG.get("CHAT", {})
            if not isinstance(chat_cfg, dict):
                chat_cfg = {}
            chat_cfg["LLM_PROVIDER"] = prov
            chat_cfg["LLM_MODEL"] = modelo
            CONFIG["CHAT"] = chat_cfg
            try:
                CONFIG.save()
            except Exception:
                pass

            return llm
        except Exception as e:
            logger.error(f"[CHAT] Erro ao criar LLM: {e}")
            return None

    # ═══════════════════════════════════════════════════
    # BUBBLE RENDERING (com formatação rica)
    # ═══════════════════════════════════════════════════

    def _adicionar_msg(self, tag: str, autor: str, texto: str, imagem_path: str = None):
        """Adiciona uma bolha de mensagem ao chat com formatação rich."""
        if tag not in ("user", "hana"):
            sys_label = ctk.CTkLabel(
                self.chat_scroll, text=f"  {texto}",
                font=FONT_SMALL, text_color=COLORS["text_muted"],
                wraplength=600, justify="center"
            )
            sys_label.grid(row=self._bubble_row, column=0, padx=40, pady=(4, 2), sticky="ew")
            self._bubble_row += 1
            self._scroll_to_bottom()
            return

        if tag == "user":
            anchor, bg, border = "e", BUBBLE_USER, BUBBLE_BORDER_USER
            nome_cor, padx_left, padx_right, inicial = COLORS["blue_neon"], 80, 8, "👤"
        else:
            anchor, bg, border = "w", BUBBLE_HANA, BUBBLE_BORDER_HANA
            nome_cor, padx_left, padx_right, inicial = COLORS["purple_neon"], 8, 80, "🌸"

        # ─── Bolha Container ───
        bubble = ctk.CTkFrame(
            self.chat_scroll, fg_color=bg, corner_radius=14,
            border_width=1, border_color=border,
        )
        bubble.grid(row=self._bubble_row, column=0, padx=(padx_left, padx_right), pady=(6, 2), sticky=anchor)
        self._bubble_row += 1

        # Header: Inicial + Nome + Hora
        header_frm = ctk.CTkFrame(bubble, fg_color="transparent")
        header_frm.pack(fill="x", padx=12, pady=(8, 0))

        ctk.CTkLabel(
            header_frm, text=f"{inicial} {autor}",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=nome_cor,
        ).pack(side="left")

        hora = time.strftime("%H:%M")
        ctk.CTkLabel(
            header_frm, text=hora, font=FONT_SMALL, text_color=COLORS["text_muted"],
        ).pack(side="right")

        # Corpo da bolha com formatação rica
        self._render_rich_text(bubble, texto)

        # Imagem inline (se fornecida)
        if imagem_path and HAS_PIL and os.path.exists(imagem_path):
            try:
                img = PILImage.open(imagem_path)
                # Calculate thumbnail size maintaining aspect ratio
                w, h = img.size
                max_w, max_h = 250, 200
                ratio = min(max_w / w, max_h / h)
                new_size = (int(w * ratio), int(h * ratio))
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=new_size)
                self._tk_images.append(ctk_img)
                img_label = ctk.CTkLabel(bubble, text="", image=ctk_img)
                img_label.pack(padx=12, pady=(2, 4))
            except Exception:
                pass

        # Botão 🔊 TTS por mensagem (apenas para respostas da Hana)
        if tag == "hana" and texto.strip():
            footer = ctk.CTkFrame(bubble, fg_color="transparent")
            footer.pack(fill="x", padx=12, pady=(0, 8))

            btn_tts = ctk.CTkButton(
                footer, text="🔊", width=30, height=24,
                fg_color="transparent", hover_color=COLORS["purple_dark"],
                text_color=COLORS["text_muted"], font=("Segoe UI", 12),
                command=lambda t=texto: self._falar_texto(t)
            )
            btn_tts.pack(side="left")

        self._scroll_to_bottom()

    def _render_rich_text(self, parent, texto: str):
        """Renderiza texto com formatação rica (negrito, quebras, emojis, código, oculta tags XML)."""
        if not texto:
            return

        # Oculta XML do subconsciente (pensamento, gerar_imagem, etc)
        texto_limpo = re.sub(
            r'<(pensamento|thought|think|gerar_imagem|editar_imagem|salvar_memoria|analisar_youtube|usar_inbox|analisar_inbox|bypass|resumo_imagem)>.*?</\1>',
            '', texto, flags=re.DOTALL | re.IGNORECASE
        )

        # Oculta marcador [EMOTION:XXX]
        texto_limpo = re.sub(r'\[EMOTION.*?\]\s*', '', texto_limpo, flags=re.IGNORECASE)

        # Oculta citações do Google Search Grounding [INDEX_X.Y]
        texto_limpo = re.sub(r'\[INDEX_\d+\.\d+(?:,\s*INDEX_\d+\.\d+)*\]', '', texto_limpo)

        texto_limpo = texto_limpo.strip()
        if not texto_limpo:
            # Se for SÓ tag (ex: ela não falou nada, só pensou), colocamos um mini indicador
            texto_limpo = "*(Processando internamente...)*"

        # Detecta blocos de código
        code_pattern = re.compile(r'```(\w*)\n?(.*?)```', re.DOTALL)
        bold_pattern = re.compile(r'\*\*(.*?)\*\*')

        parts = code_pattern.split(texto_limpo)

        i = 0
        while i < len(parts):
            if i + 2 < len(parts) and (i % 3 == 1):
                # Bloco de código
                lang = parts[i]
                code = parts[i + 1].strip()
                code_frame = ctk.CTkFrame(parent, fg_color="#1a1a2e", corner_radius=8)
                code_frame.pack(fill="x", padx=12, pady=(4, 4))

                if lang:
                    ctk.CTkLabel(
                        code_frame, text=lang.upper(), font=FONT_SMALL,
                        text_color=COLORS["text_muted"]
                    ).pack(anchor="w", padx=8, pady=(4, 0))

                code_label = ctk.CTkLabel(
                    code_frame, text=code,
                    font=("Consolas", 11), text_color="#e2e8f0",
                    wraplength=550, justify="left", anchor="nw",
                )
                code_label.pack(fill="x", padx=8, pady=(2, 6))
                i += 2
            else:
                # Texto normal — processa negrito e quebras
                segment = parts[i]
                if segment.strip():
                    # Aplica formatação rica
                    # Substitui **texto** por texto com fonte negrito
                    display_text = segment.strip()
                    
                    # Vamos manter simples por enquanto: apenas tira os asteriscos ou formata como negrito 
                    # usando font customizada nos segmentos divididos. Para simplificar e evitar crash, usa texto puro sem **
                    display_text = display_text.replace("**", "")

                    corpo = ctk.CTkLabel(
                        parent, text=display_text,
                        font=ctk.CTkFont(family=FONT_BODY[0], size=FONT_BODY[1], weight="bold" if "**" in segment else "normal"), text_color=COLORS["text_primary"],
                        wraplength=600, justify="left", anchor="w",
                    )
                    corpo.pack(fill="x", padx=12, pady=(4, 4))
                i += 1

    def _scroll_to_bottom(self):
        self.chat_scroll.update_idletasks()
        self.chat_scroll._parent_canvas.yview_moveto(1.0)

    # ═══════════════════════════════════════════════════
    # ENVIO DE MENSAGEM
    # ═══════════════════════════════════════════════════

    def _enviar(self):
        texto = self.entry_msg.get().strip()
        if not texto:
            return
        self.entry_msg.delete(0, "end")

        # Captura anexos
        anexos_envio = list(self._anexos)
        img_paths = [p for p in anexos_envio if p.lower().split('.')[-1] in ('png', 'jpg', 'jpeg', 'webp', 'gif', 'bmp')]

        self._adicionar_msg("user", "Nakamura", texto, imagem_path=img_paths[0] if img_paths else None)

        self.btn_enviar.configure(state="disabled", text="...")
        self.lbl_chat_status.configure(text="⏳ Processando...", text_color=COLORS["yellow"])

        def _processar():
            try:
                llm = self._get_chat_llm()
                if not llm:
                    self.after(0, lambda: self._adicionar_msg("system", "Hana", "❌ Erro: Não foi possível inicializar o provedor LLM."))
                    return

                # Carrega persona e prompt
                persona_path = os.path.join(os.path.dirname(__file__), "..", "..", "config", "persona.txt")
                prompt_path = os.path.join(os.path.dirname(__file__), "..", "..", "config", "prompt.json")

                personality = ""
                prompt_rules = ""
                try:
                    with open(os.path.abspath(persona_path), "r", encoding="utf-8") as f:
                        personality = f.read()
                except Exception:
                    pass
                try:
                    with open(os.path.abspath(prompt_path), "r", encoding="utf-8") as f:
                        prompt_data = json.load(f)
                        prompt_rules = "\n".join([f"- {k}: {v}" for k, v in prompt_data.items()])
                except Exception:
                    pass

                import datetime
                current_datetime = datetime.datetime.now().strftime("%A, %d de %B de %Y, %H:%M")
                sistema_prompt = (
                    f"=== [NÚCLEO DE PERSONALIDADE: HANA AM NAKAMURA] ===\n{personality}\n\n"
                    f"=== [PROTOCOLO OPERACIONAL E REGRAS] ===\n{prompt_rules}\n\n"
                    f"=== [CONTEXTO AMBIENTAL] ===\n"
                    f"Data/Hora: {current_datetime}\n\n"
                    "⚠️ LEMBRETE CRÍTICO: Você é a HANA. Fale como ela, sinta como ela. "
                    "Nunca aja como uma IA, nunca se descreva como modelo de linguagem. "
                    "Seja imersiva, sarcástica, fofa e use suas gírias naturalmente."
                )

                # Carrega histórico do SQLite
                try:
                    from src.memory import memory
                    db = memory("data/hana_memory.db")
                    raw_history = db.get_messages(limit=50)
                except Exception:
                    raw_history = []

                # Processa anexos de arquivo (texto)
                mensagem_final = texto
                image_b64 = None
                arquivos_multimidia = []

                if anexos_envio:
                    textos_extras = []
                    for path in anexos_envio:
                        if not os.path.exists(path):
                            continue
                        ext = path.lower().split('.')[-1]
                        if ext in ('png', 'jpg', 'jpeg', 'webp', 'gif', 'bmp'):
                            try:
                                with open(path, "rb") as bf:
                                    image_b64 = base64.b64encode(bf.read()).decode("utf-8")
                            except Exception:
                                pass
                        elif ext in ('pdf', 'mp4', 'mp3', 'wav', 'ogg', 'avi', 'mov', 'webm', 'mkv', 'm4a', 'flac', 'aac'):
                            prov_sel = self.combo_chat_prov.get()
                            if prov_sel != "google_cloud":
                                self.after(0, lambda p=path: self._adicionar_msg("system", "Hana", f"❌ Apenas modelos do Google suportam leitura nativa de PDFs ou Vídeos/Áudio pesados. Envio bloqueado: {os.path.basename(p)}"))
                                self.after(0, lambda: self.btn_enviar.configure(state="normal", text="Enviar  ➤"))
                                self.after(0, lambda: self.lbl_chat_status.configure(text="❌ Erro Multimodal", text_color=COLORS["red"]))
                                return
                            else:
                                arquivos_multimidia.append(path)
                                textos_extras.append(f"📎 [Arquivo Anexado: {os.path.basename(path)}]")
                        else:
                            try:
                                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                                    conteudo = f.read()
                                textos_extras.append(f"[ARQUIVO: {os.path.basename(path)}]\n{conteudo}")
                            except Exception as e:
                                textos_extras.append(f"[ERRO: {os.path.basename(path)}: {e}]")

                    if textos_extras:
                        mensagem_final += "\n\n" + "\n\n".join(textos_extras)

                    self._anexos = []
                    self.after(0, self.frame_anexo.grid_forget)

                # Chama a LLM passando os objetos corretamente
                resposta = llm.gerar_resposta(
                    chat_history=raw_history,
                    sistema_prompt=sistema_prompt,
                    user_message=mensagem_final,
                    image_b64=image_b64,
                    arquivos_multimidia=arquivos_multimidia if arquivos_multimidia else None
                )

                if not resposta:
                    resposta = "(sem resposta)"

                # Limpa marcadores fantasma e tool calls
                resp_display = re.sub(r'【.*?】', '', resposta, flags=re.DOTALL).strip()
                resp_display = resp_display.replace('`', '') if '```' not in resp_display else resp_display

                self._ultima_resposta = resposta

                self.after(0, lambda r=resp_display: self._adicionar_msg("hana", "Hana", r))
                self.after(0, lambda: self.lbl_chat_status.configure(
                    text=f"✓ Resposta recebida — {self.combo_chat_prov.get()}/{self.combo_chat_modelo.get()}",
                    text_color=COLORS["green"]
                ))

                # Salva no SQLite (memória compartilhada) — NÃO salva respostas vazias
                try:
                    from src.memory import memory
                    db = memory("data/hana_memory.db")
                    db.add_message("Nakamura", texto)
                    if resposta and resposta != "(sem resposta)":
                        db.add_message("Hana", resposta)
                except Exception:
                    pass

            except Exception as e:
                self.after(0, lambda err=e: self._adicionar_msg("system", "ERRO", str(err)))
                self.after(0, lambda: self.lbl_chat_status.configure(text=f"❌ Erro: {e}", text_color=COLORS["red"]))
            finally:
                self.after(0, lambda: self.btn_enviar.configure(state="normal", text="Enviar  ➤"))

        threading.Thread(target=_processar, daemon=True).start()

    # ═══════════════════════════════════════════════════
    # ANEXOS
    # ═══════════════════════════════════════════════════

    def _abrir_anexo(self):
        filepaths = filedialog.askopenfilenames(
            title="Anexar arquivo(s)",
            filetypes=[
                ("Imagens", "*.png *.jpg *.jpeg *.webp *.gif *.bmp"),
                ("Áudio", "*.mp3 *.wav *.ogg *.m4a *.flac *.aac"),
                ("Vídeo", "*.mp4 *.avi *.mov *.webm *.mkv"),
                ("Documentos", "*.pdf *.doc *.docx"),
                ("Código", "*.py *.js *.ts *.html *.css *.java *.c *.cpp"),
                ("Textos", "*.txt *.md *.json *.csv *.xml *.yaml *.yml *.log"),
                ("Todos", "*.*")
            ]
        )
        if filepaths:
            for fp in filepaths:
                if fp not in self._anexos:
                    self._anexos.append(fp)
            self._atualizar_container_anexos()

    def _atualizar_container_anexos(self):
        for widget in self.frame_anexo.winfo_children():
            if widget not in (self.lbl_anexo, self.btn_cancelar_anexo):
                widget.destroy()
        if not self._anexos:
            self.frame_anexo.grid_forget()
            return
        self.lbl_anexo.configure(text=f"📎 {len(self._anexos)} arquivo(s)")
        for fp in self._anexos:
            nome = os.path.basename(fp)
            ext = nome.lower().split('.')[-1]
            icone = {
                "py": "🐍", "js": "⚡", "ts": "⚡", "pdf": "📕", "json": "📋",
                "txt": "📝", "md": "📝",
                "mp3": "🎵", "wav": "🎵", "ogg": "🎵", "m4a": "🎵", "flac": "🎵", "aac": "🎵",
                "mp4": "🎬", "avi": "🎬", "mov": "🎬", "webm": "🎬", "mkv": "🎬",
            }.get(ext, "📄")
            if ext in ('png', 'jpg', 'jpeg', 'webp', 'gif', 'bmp') and HAS_PIL:
                try:
                    img = PILImage.open(fp)
                    ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(40, 40))
                    self._tk_images.append(ctk_img)
                    thumb = ctk.CTkLabel(self.frame_anexo, text="", image=ctk_img, width=40, height=40)
                    thumb.pack(side="left", padx=3, pady=4)
                except Exception:
                    lbl = ctk.CTkLabel(self.frame_anexo, text=f"🖼 {nome[:12]}", font=FONT_SMALL, text_color=COLORS["text_secondary"])
                    lbl.pack(side="left", padx=3, pady=4)
            else:
                lbl = ctk.CTkLabel(self.frame_anexo, text=f"{icone} {nome[:15]}", font=FONT_SMALL, text_color=COLORS["text_secondary"])
                lbl.pack(side="left", padx=3, pady=4)
        self.frame_anexo.grid(row=4, column=0, padx=15, pady=(0, 5), sticky="ew")

    def _cancelar_anexo(self):
        self._anexos = []
        self._tk_images = []
        self.frame_anexo.grid_forget()

    # ═══════════════════════════════════════════════════
    # STT (Microfone)
    # ═══════════════════════════════════════════════════

    def _gravar_audio(self):
        self.btn_mic.configure(text="🔴", text_color=COLORS["red"])
        self._adicionar_msg("system", "Hana", "🎙 Gravando... (aguarde)")

        def _capturar():
            texto_transcrito = ""
            try:
                from src.modules.voice.stt_whisper import MotorSTTWhisper
                stt = MotorSTTWhisper()
                texto_transcrito = stt.transcrever()
            except Exception as e:
                texto_transcrito = f"(Erro STT: {e})"
            finally:
                self.after(0, lambda: self.btn_mic.configure(text="🎙", text_color=COLORS["text_muted"]))
                if texto_transcrito:
                    self.after(0, lambda t=texto_transcrito: self.entry_msg.insert(0, t))

        threading.Thread(target=_capturar, daemon=True).start()

    # ═══════════════════════════════════════════════════
    # TTS
    # ═══════════════════════════════════════════════════

    def _falar_texto(self, texto):
        def _run():
            try:
                from src.modules.voice.tts_selector import get_tts
                from src.utils.text import limpar_texto_tts
                tts = get_tts()
                texto_limpo = limpar_texto_tts(texto)
                if texto_limpo.strip():
                    tts.falar(texto_limpo)
            except Exception as e:
                logger.error(f"[CHAT TTS] Erro: {e}")

        threading.Thread(target=_run, daemon=True).start()

    def _parar_fala(self):
        """Tenta parar a reprodução de áudio."""
        try:
            import pygame
            if pygame.mixer.get_init():
                pygame.mixer.stop()
        except Exception:
            pass
