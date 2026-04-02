import base64
import json
import logging
import os
import re
import threading
import time
import webbrowser
from tkinter import filedialog

import customtkinter as ctk

from src.config.config_loader import CONFIG
from src.core.request_profiles import build_request_context, get_chat_settings
from src.core.runtime_capabilities import get_provider_capabilities
from src.gui.design import COLORS, FONT_BODY, FONT_SMALL, FONT_TITLE
from src.modules.tools.inbox_manager import InboxManager

logger = logging.getLogger(__name__)

try:
    from PIL import Image as PILImage

    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    from tkinterdnd2 import COPY, DND_FILES, TkinterDnD

    HAS_DND = True
except Exception:
    COPY = None
    DND_FILES = None
    TkinterDnD = None
    HAS_DND = False


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
AUDIO_EXTS = {".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac"}
VIDEO_EXTS = {".mp4", ".avi", ".mov", ".webm", ".mkv", ".m4v"}
TEXT_EXTS = {".txt", ".md", ".json", ".csv", ".xml", ".yaml", ".yml", ".log", ".docx"}
XML_TAGS = (
    "pensamento",
    "thought",
    "think",
    "gerar_imagem",
    "editar_imagem",
    "salvar_memoria",
    "analisar_youtube",
    "usar_inbox",
    "analisar_inbox",
    "bypass",
    "resumo_imagem",
    "ferramenta_web",
)
HEAVY_MEDIA_TASKS = {"analise_midia", "media_summary", "resumo_detalhado"}

BUBBLE_USER = "#1A2744"
BUBBLE_HANA = "#201933"
BUBBLE_BORDER_USER = "#2563EB"
BUBBLE_BORDER_HANA = "#8B5CF6"


class TabChat(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            corner_radius=12,
            fg_color=COLORS["bg_dark"],
            border_width=1,
            border_color=COLORS["border"],
        )
        self._ultima_resposta = ""
        self._anexos = []
        self._tk_images = []
        self._llm_instance = None
        self._memory_manager = None
        self._image_gen = None
        self._session_history = []
        self._audio_preview_path = None
        self._inbox_manager = InboxManager()
        self._request_seq = 0
        self._active_request_id = None
        self._active_cancel_event = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        self._build_layout()
        self._carregar_config_chat()
        self.after(200, self._ativar_dragdrop)

    def _build_layout(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, padx=24, pady=(16, 0), sticky="ew")
        ctk.CTkLabel(header, text="Control Center Chat", font=FONT_TITLE, text_color=COLORS["text_primary"]).pack(side="left")
        ctk.CTkLabel(header, text="GUI da Hana", font=FONT_SMALL, text_color=COLORS["text_muted"]).pack(side="left", padx=(10, 0))

        self.toolbar = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=10, height=48)
        self.toolbar.grid(row=1, column=0, padx=15, pady=(8, 6), sticky="ew")
        ctk.CTkLabel(self.toolbar, text="Provedor:", font=FONT_SMALL, text_color=COLORS["text_muted"]).pack(side="left", padx=(10, 4))
        self.combo_chat_prov = ctk.CTkComboBox(
            self.toolbar,
            values=["groq", "google_cloud", "cerebras", "openrouter"],
            width=135,
            fg_color=COLORS["bg_darkest"],
            border_color=COLORS["border"],
            button_color=COLORS["purple_dim"],
            button_hover_color=COLORS["purple_neon"],
            dropdown_fg_color=COLORS["bg_card"],
            dropdown_hover_color=COLORS["purple_dark"],
            text_color=COLORS["text_primary"],
            font=FONT_SMALL,
            command=self._on_chat_prov_change,
        )
        self.combo_chat_prov.pack(side="left", padx=(0, 8))
        ctk.CTkLabel(self.toolbar, text="Modelo:", font=FONT_SMALL, text_color=COLORS["text_muted"]).pack(side="left", padx=(0, 4))
        self.combo_chat_modelo = ctk.CTkComboBox(
            self.toolbar,
            values=[""],
            width=225,
            fg_color=COLORS["bg_darkest"],
            border_color=COLORS["border"],
            button_color=COLORS["purple_dim"],
            button_hover_color=COLORS["purple_neon"],
            dropdown_fg_color=COLORS["bg_card"],
            dropdown_hover_color=COLORS["purple_dark"],
            text_color=COLORS["text_primary"],
            font=FONT_SMALL,
        )
        self.combo_chat_modelo.pack(side="left", padx=(0, 10))
        self.lbl_input_hint = ctk.CTkLabel(
            self.toolbar,
            text="Enter envia • Shift+Enter quebra linha • Arraste arquivos aqui",
            font=FONT_SMALL,
            text_color=COLORS["text_muted"],
        )
        self.lbl_input_hint.pack(side="left", padx=(8, 0))
        self.btn_stop = ctk.CTkButton(
            self.toolbar,
            text="Parar",
            width=84,
            height=28,
            fg_color=COLORS["bg_darkest"],
            hover_color=COLORS["red"],
            text_color=COLORS["text_secondary"],
            border_width=1,
            border_color=COLORS["border"],
            font=FONT_SMALL,
            command=self._parar_fala,
        )
        self.btn_stop.pack(side="right", padx=8)

        self.status_bar = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=8, height=26)
        self.status_bar.grid(row=2, column=0, padx=15, pady=(0, 6), sticky="ew")
        self.lbl_chat_status = ctk.CTkLabel(self.status_bar, text="Chat da GUI pronto.", font=FONT_SMALL, text_color=COLORS["text_muted"])
        self.lbl_chat_status.pack(side="left", padx=10, pady=3)

        self.chat_scroll = ctk.CTkScrollableFrame(
            self,
            fg_color=COLORS["bg_darkest"],
            corner_radius=12,
            border_width=1,
            border_color=COLORS["border"],
            scrollbar_button_color=COLORS["purple_dim"],
            scrollbar_button_hover_color=COLORS["purple_neon"],
        )
        self.chat_scroll.grid(row=3, column=0, padx=15, pady=(0, 8), sticky="nsew")
        self.chat_scroll.grid_columnconfigure(0, weight=1)
        self._bubble_row = 0

        self.frame_anexo = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=10, border_width=1, border_color=COLORS["border"])
        self.lbl_anexo = ctk.CTkLabel(self.frame_anexo, text="Arquivos prontos para envio", font=FONT_SMALL, text_color=COLORS["text_secondary"])
        self.lbl_anexo.pack(anchor="w", padx=12, pady=(8, 4))
        self.frame_anexo_list = ctk.CTkFrame(self.frame_anexo, fg_color="transparent")
        self.frame_anexo_list.pack(fill="x", padx=10, pady=(0, 8))

        self.input_frame = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=12, border_width=1, border_color=COLORS["border"])
        self.input_frame.grid(row=5, column=0, padx=15, pady=(0, 15), sticky="ew")
        self.input_frame.grid_columnconfigure(2, weight=1)

        self.btn_mic = ctk.CTkButton(self.input_frame, text="Mic", width=44, height=44, fg_color="transparent", hover_color=COLORS["purple_dark"], text_color=COLORS["text_muted"], font=("Segoe UI", 12, "bold"), command=self._gravar_audio)
        self.btn_mic.grid(row=0, column=0, padx=(8, 4), pady=8)
        self.btn_anexo = ctk.CTkButton(self.input_frame, text="+", width=44, height=44, fg_color="transparent", hover_color=COLORS["bg_card_hover"], text_color=COLORS["text_muted"], font=("Segoe UI", 20, "bold"), command=self._abrir_anexo)
        self.btn_anexo.grid(row=0, column=1, padx=(0, 0), pady=8)

        textbox_frame = ctk.CTkFrame(self.input_frame, fg_color=COLORS["bg_darkest"], corner_radius=10)
        textbox_frame.grid(row=0, column=2, padx=8, pady=8, sticky="ew")
        textbox_frame.grid_columnconfigure(0, weight=1)
        self.entry_msg = ctk.CTkTextbox(textbox_frame, height=84, fg_color=COLORS["bg_darkest"], border_width=0, text_color=COLORS["text_primary"], font=FONT_BODY, wrap="word")
        self.entry_msg.grid(row=0, column=0, sticky="ew")
        self.entry_msg.bind("<Return>", self._on_input_return)
        self.entry_msg.bind("<KP_Enter>", self._on_input_return)
        self.entry_msg.bind("<KeyRelease>", self._update_input_placeholder)
        self.entry_placeholder = ctk.CTkLabel(textbox_frame, text="Digite uma mensagem para a Hana... (Shift+Enter quebra linha)", font=FONT_BODY, text_color=COLORS["text_muted"])
        self.entry_placeholder.place(x=12, y=12)

        self.btn_enviar = ctk.CTkButton(self.input_frame, text="Enviar", width=110, height=44, fg_color=COLORS["purple_dim"], hover_color=COLORS["purple_neon"], font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), command=self._enviar)
        self.btn_enviar.grid(row=0, column=3, padx=(0, 8), pady=8)

        self._adicionar_msg("system", "Hana", "Control Center online. Este chat não é o terminal.")

    def _carregar_config_chat(self):
        chat_cfg = CONFIG.get("CHAT", {})
        if not isinstance(chat_cfg, dict):
            chat_cfg = {}

        defaults = get_chat_settings()
        changed = False
        for key, value in (
            ("response_mode", defaults["response_mode"]),
            ("auto_route_media", defaults["auto_route_media"]),
            ("media_model", defaults["media_model"]),
            ("max_output_tokens_normal", defaults["max_output_tokens_normal"]),
            ("max_output_tokens_media", defaults["max_output_tokens_media"]),
            ("markdown_enabled", defaults["markdown_enabled"]),
        ):
            if chat_cfg.get(key) is None:
                chat_cfg[key] = value
                changed = True

        if chat_cfg.get("usa_mesmo_prompt_terminal") is not False:
            chat_cfg["usa_mesmo_prompt_terminal"] = False
            changed = True

        prov = chat_cfg.get("LLM_PROVIDER", CONFIG.get("LLM_PROVIDER", "openrouter"))
        modelo = chat_cfg.get("LLM_MODEL", "")
        self.combo_chat_prov.set(prov)
        self._on_chat_prov_change(prov)
        if modelo:
            self.combo_chat_modelo.set(modelo)

        if changed:
            CONFIG["CHAT"] = chat_cfg
            try:
                CONFIG.save()
            except Exception:
                pass

    def _provider_models(self, provedor):
        return {
            "groq": ["llama-3.1-8b-instant", "meta-llama/llama-4-scout-17b-16e-instruct", "moonshotai/kimi-k2-instruct-0905", "Outro..."],
            "google_cloud": ["gemini-3.1-pro-preview", "gemini-3-pro-preview", "gemini-3.1-flash-preview", "gemini-3-flash-preview", "gemini-3.1-flash-lite-preview", "gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash", "Outro..."],
            "openrouter": ["openai/gpt-5.4", "openai/gpt-5.4-mini", "google/gemini-3.1-flash-lite-preview", "google/gemini-3.1-pro-preview", "google/gemini-2.5-pro", "google/gemini-2.5-flash", "google/gemini-2.5-flash-lite", "x-ai/grok-4.20-beta", "x-ai/grok-4.1-fast", "x-ai/grok-4", "anthropic/claude-opus-4.6", "anthropic/claude-sonnet-4.6", "anthropic/claude-haiku-4.5", "Outro..."],
            "cerebras": ["qwen-3-235b-a22b-instruct-2507", "llama3.1-8b", "gpt-oss-120b", "zai-glm-4.7", "Outro..."],
        }.get(provedor, ["Outro..."])

    def _provider_class(self, provedor):
        prov = (provedor or "").strip().lower()
        if prov == "groq":
            from src.providers.groq_provider import GroqProvider

            return GroqProvider
        if prov == "google_cloud":
            from src.providers.google_provider import GoogleProvider

            return GoogleProvider
        if prov == "cerebras":
            from src.providers.cerebras_provider import CerebrasProvider

            return CerebrasProvider
        if prov == "openrouter":
            from src.providers.openrouter_provider import OpenRouterProvider

            return OpenRouterProvider
        return None

    def _on_chat_prov_change(self, provedor):
        models = self._provider_models(provedor)
        self.combo_chat_modelo.configure(values=models)
        if models:
            self.combo_chat_modelo.set(models[0])
        self._llm_instance = None

    def _create_llm_instance(self, provedor, modelo, cache=False):
        provider_class = self._provider_class(provedor)
        if provider_class is None:
            return None
        llm = provider_class()
        if modelo and modelo != "Outro...":
            llm.modelo_chat = modelo
        llm.refresh_runtime_settings(scope="CHAT", sync_model_from_config=False)
        if cache:
            self._llm_instance = llm
        return llm

    def _get_chat_llm(self):
        prov = self.combo_chat_prov.get().strip().lower()
        modelo = self.combo_chat_modelo.get().strip()
        if self._llm_instance and getattr(self._llm_instance, "provedor", "").lower() == prov:
            self._llm_instance.modelo_chat = modelo
            self._llm_instance.refresh_runtime_settings(scope="CHAT", sync_model_from_config=False)
            return self._llm_instance

        llm = self._create_llm_instance(prov, modelo, cache=True)
        if llm is None:
            return None

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

    def _get_memory_manager(self):
        if self._memory_manager is None:
            from src.memory.memory_manager import HanaMemoryManager

            self._memory_manager = HanaMemoryManager("data/hana_memory.db")
        return self._memory_manager

    def _get_image_gen(self):
        if self._image_gen is None:
            from src.modules.vision.image_gen import HanaImageGen

            self._image_gen = HanaImageGen()
        return self._image_gen

    def _ativar_dragdrop(self):
        if not HAS_DND:
            self.lbl_input_hint.configure(text="Enter envia • Shift+Enter quebra linha • Use o clipe para anexar")
            return
        try:
            TkinterDnD._require(self.winfo_toplevel())
            for widget in (self, self.chat_scroll, self.input_frame, self.entry_msg):
                widget.drop_target_register(DND_FILES)
                widget.dnd_bind("<<Drop>>", self._on_drop_files)
        except Exception as e:
            logger.warning("[CHAT GUI] Drag-and-drop indisponível: %s", e)
            self.lbl_input_hint.configure(text="Enter envia • Shift+Enter quebra linha • Use o clipe para anexar")

    def _on_drop_files(self, event):
        try:
            for path in self.tk.splitlist(event.data):
                if os.path.exists(path) and path not in self._anexos:
                    self._anexos.append(path)
            self._atualizar_container_anexos()
        except Exception as e:
            logger.error("[CHAT GUI] Falha no drop: %s", e)
        return COPY or "copy"

    def _on_input_return(self, event):
        if event.state & 0x0001:
            return None
        self._enviar()
        return "break"

    def _get_input_text(self):
        return self.entry_msg.get("1.0", "end-1c")

    def _clear_input(self):
        self.entry_msg.delete("1.0", "end")
        self._update_input_placeholder()

    def _update_input_placeholder(self, _event=None):
        if self._get_input_text().strip():
            self.entry_placeholder.place_forget()
        else:
            self.entry_placeholder.place(x=12, y=12)

    def _infer_file_kind(self, path):
        ext = os.path.splitext(path)[1].lower()
        if ext in IMAGE_EXTS:
            return "image"
        if ext in AUDIO_EXTS:
            return "audio"
        if ext in VIDEO_EXTS:
            return "video"
        if ext == ".pdf":
            return "pdf"
        if ext in TEXT_EXTS:
            return "text"
        return "file"

    def _icon_for_kind(self, kind):
        return {
            "image": "IMG",
            "audio": "AUD",
            "video": "VID",
            "pdf": "PDF",
            "text": "DOC",
            "file": "ARQ",
        }.get(kind, "ARQ")

    def _contains_media(self, anexos_envio):
        return any(self._infer_file_kind(path) in {"audio", "video", "pdf"} for path in anexos_envio)

    def _classify_task(self, texto, anexos_envio):
        lowered = (texto or "").strip().lower()
        if re.search(r"\b(gera|cria|criar|faz|faça).*(imagem|foto|arte)\b", lowered):
            return "image_action"
        if re.search(r"\b(traduz|traduza|translation)\b", lowered):
            return "traducao"

        has_media = self._contains_media(anexos_envio)
        detail_keywords = ("resuma", "resume", "resumir", "detalha", "detalhe", "detalhar", "analisa", "analise", "analisar", "explica", "explique", "explicar", "reunião", "reuniao", "ata", "pontos")
        if has_media:
            if any(keyword in lowered for keyword in detail_keywords) or not lowered:
                return "analise_midia"
            return "media_summary"

        if any(keyword in lowered for keyword in detail_keywords):
            return "resumo_detalhado"
        return "chat_normal"

    def _build_response_schema(self, task_type):
        if task_type not in HEAVY_MEDIA_TASKS:
            return None

        ordered = [
            "titulo",
            "resumo_executivo",
            "topicos_principais",
            "decisoes",
            "acoes",
            "riscos",
            "linha_do_tempo",
            "trechos_relevantes",
        ]
        return {
            "type": "object",
            "propertyOrdering": ordered,
            "properties": {
                "titulo": {"type": "string", "description": "Título curto e objetivo do conteúdo analisado."},
                "resumo_executivo": {"type": "string", "description": "Resumo claro e útil em português."},
                "topicos_principais": {"type": "array", "items": {"type": "string"}, "description": "Principais assuntos tratados."},
                "decisoes": {"type": "array", "items": {"type": "string"}, "description": "Decisões tomadas ou conclusões fechadas."},
                "acoes": {"type": "array", "items": {"type": "string"}, "description": "Próximas ações, tarefas ou encaminhamentos."},
                "riscos": {"type": "array", "items": {"type": "string"}, "description": "Riscos, bloqueios ou pontos de atenção."},
                "linha_do_tempo": {"type": "array", "items": {"type": "string"}, "description": "Sequência resumida dos momentos ou etapas."},
                "trechos_relevantes": {"type": "array", "items": {"type": "string"}, "description": "Trechos ou citações importantes do conteúdo."},
            },
            "required": ["titulo", "resumo_executivo", "topicos_principais", "acoes", "riscos"],
        }

    def _load_gui_persona(self):
        persona_path = os.path.join(os.path.dirname(__file__), "..", "..", "config", "persona.txt")
        personality = ""
        try:
            with open(os.path.abspath(persona_path), "r", encoding="utf-8") as f:
                personality = f.read()
        except Exception:
            return ""

        personality = re.sub(r"Regra de Tamanho:.*?(?:\n|$)", "", personality, flags=re.IGNORECASE)
        personality = re.sub(r"APENAS 1 a 5 frases.*?(?:\n|$)", "", personality, flags=re.IGNORECASE)
        return personality.strip()

    def _load_prompt_rules(self):
        prompt_path = os.path.join(os.path.dirname(__file__), "..", "..", "config", "prompt.json")
        try:
            with open(os.path.abspath(prompt_path), "r", encoding="utf-8") as f:
                prompt_data = json.load(f)
        except Exception:
            return ""
        return "\n".join([f"- {k}: {v}" for k, v in prompt_data.items()])

    def _attachments_overview(self, anexos_envio):
        lines = []
        for path in anexos_envio:
            kind = self._infer_file_kind(path)
            lines.append(f"- {kind}: {os.path.basename(path)}")
        return "\n".join(lines) if lines else "- nenhum anexo"

    def _build_gui_prompt(self, user_message, memory_context, task_type, anexos_envio, request_context):
        personality = self._load_gui_persona()
        prompt_rules = self._load_prompt_rules()
        task_guidance = {
            "chat_normal": "Converse como um chatbot moderno. Se a pergunta for simples, seja direta. Se a pergunta pedir contexto, explique com calma.",
            "resumo_detalhado": "Responda em markdown claro com seções, parágrafos e listas. Priorize profundidade e utilidade, não resposta curta.",
            "analise_midia": "Analise os anexos com profundidade. Extraia contexto, tópicos, decisões, ações, riscos e trechos importantes.",
            "media_summary": "Resuma o conteúdo anexado com detalhes úteis. Não devolva um resumo raso.",
            "traducao": "Entregue a tradução de forma clara e bem formatada.",
            "image_action": "Se o usuário pedir criação de imagem, responda naturalmente e use <gerar_imagem>...</gerar_imagem> apenas no final.",
        }.get(task_type, "Responda como um chatbot moderno e consciente da GUI.")
        return (
            f"=== [NUCLEO DE PERSONALIDADE: HANA AM NAKAMURA] ===\n{personality}\n\n"
            f"=== [PROTOCOLO OPERACIONAL E REGRAS] ===\n{prompt_rules}\n\n"
            "=== [MODO DE INTERACAO: CHAT DA GUI] ===\n"
            "Voce esta dentro do chat visual do Control Center da Hana.\n"
            "Este ambiente nao e o terminal.\n"
            "IGNORE completamente qualquer regra global do terminal que limite a resposta a 1-5 frases.\n"
            "Voce deve agir como um chatbot moderno da GUI, nao como assistente de linha de comando.\n"
            "Use markdown natural quando a resposta ficar média ou longa: títulos, listas, blocos e espaçamento correto.\n"
            f"{task_guidance}\n"
            "Se arquivos chegaram neste chat, reconheca os anexos explicitamente.\n"
            "Se quiser gerar uma imagem para aparecer neste chat, use <gerar_imagem>...</gerar_imagem> no final.\n"
            "Se quiser editar a ultima imagem gerada no chat, use <editar_imagem>...</editar_imagem> no final.\n"
            "Se quiser salvar algo na memoria longa, use <salvar_memoria>...</salvar_memoria> no final.\n"
            "Nao diga que o usuario esta no terminal, a menos que esta conversa confirme isso.\n\n"
            f"=== [TIPO DE TAREFA] ===\n{task_type}\n\n"
            f"=== [ANEXOS RECEBIDOS] ===\n{self._attachments_overview(anexos_envio)}\n\n"
            f"=== [CONFIGURACAO DE RESPOSTA] ===\n"
            f"- channel: {request_context.get('channel')}\n"
            f"- response_mode: {request_context.get('response_mode')}\n"
            f"- markdown_enabled: {request_context.get('markdown_enabled')}\n"
            f"- max_output_tokens: {request_context.get('max_output_tokens')}\n\n"
            f"=== [CONTEXTO DE MEMORIA COMPARTILHADA] ===\n{memory_context}\n\n"
            f"Mensagem atual do usuario:\n{user_message}"
        )

    def _prepare_attachments_for_llm(self, anexos_envio, capabilities):
        image_b64 = None
        arquivos_multimidia = []
        text_blocks = []
        for path in anexos_envio:
            if not os.path.exists(path):
                continue
            kind = self._infer_file_kind(path)
            name = os.path.basename(path)
            if kind == "image":
                if not capabilities.supports_images:
                    raise RuntimeError(f"O provider atual não aceita imagem neste chat: {name}")
                if image_b64 is None:
                    with open(path, "rb") as bf:
                        image_b64 = base64.b64encode(bf.read()).decode("utf-8")
                text_blocks.append(f"[IMAGEM ANEXADA: {name}]")
            elif kind in {"audio", "video"}:
                if not capabilities.supports_native_media:
                    raise RuntimeError(f"O provider atual não suporta áudio/vídeo nativo: {name}")
                arquivos_multimidia.append(path)
                text_blocks.append(f"[MIDIA ANEXADA: {name}]")
            elif kind == "pdf":
                if capabilities.supports_native_media:
                    arquivos_multimidia.append(path)
                    text_blocks.append(f"[PDF ANEXADO: {name}]")
                else:
                    text_blocks.append(f"[PDF: {name}]\n{self._inbox_manager.read_pdf(path)}")
            else:
                ext = os.path.splitext(path)[1].lower()
                if ext == ".doc":
                    raise RuntimeError("Arquivo .doc antigo ainda não é suportado neste fluxo. Use .docx ou PDF.")
                text_blocks.append(f"[ARQUIVO: {name}]\n{self._inbox_manager.read_text_like(path)}")
        return image_b64, arquivos_multimidia, text_blocks

    def _resolve_execution_target(self, task_type, anexos_envio):
        selected_provider = self.combo_chat_prov.get().strip().lower()
        selected_model = self.combo_chat_modelo.get().strip()
        capabilities = get_provider_capabilities(
            selected_provider,
            selected_model,
            vision_enabled=CONFIG.get("VISAO_ATIVA", False),
        )
        chat_settings = get_chat_settings()
        has_heavy_media = self._contains_media(anexos_envio)
        route_to_media_model = task_type in HEAVY_MEDIA_TASKS and has_heavy_media
        selected_model_key = selected_model.lower()

        if chat_settings["auto_route_media"] and has_heavy_media:
            if selected_provider != "google_cloud" or not capabilities.supports_native_media:
                return {
                    "provider": "google_cloud",
                    "model": chat_settings["media_model"],
                    "routed": True,
                    "route_reason": "native_media",
                }
            if route_to_media_model and ("flash-lite" in selected_model_key or "lite" in selected_model_key):
                return {
                    "provider": "google_cloud",
                    "model": chat_settings["media_model"],
                    "routed": chat_settings["media_model"] != selected_model,
                    "route_reason": "heavy_media_quality",
                }

        return {
            "provider": selected_provider,
            "model": selected_model,
            "routed": False,
            "route_reason": "",
        }

    def _extract_xml_actions(self, texto):
        actions = {}
        for tag_name in ("salvar_memoria", "gerar_imagem", "editar_imagem"):
            actions[tag_name] = [
                item.strip()
                for item in re.findall(rf"<{tag_name}>(.*?)</{tag_name}>", texto, re.DOTALL | re.IGNORECASE)
                if item.strip()
            ]
        return actions

    def _structured_response_to_markdown(self, payload):
        if isinstance(payload, list):
            return "\n".join([f"- {item}" for item in payload if str(item).strip()])

        if not isinstance(payload, dict):
            return str(payload)

        sections = []
        title = str(payload.get("titulo", "")).strip()
        if title:
            sections.append(f"## {title}")

        if payload.get("resumo_executivo"):
            sections.append("### Resumo Executivo")
            sections.append(str(payload["resumo_executivo"]).strip())

        section_labels = {
            "topicos_principais": "### Tópicos Principais",
            "decisoes": "### Decisões",
            "acoes": "### Ações",
            "riscos": "### Riscos",
            "linha_do_tempo": "### Linha do Tempo",
            "trechos_relevantes": "### Trechos Relevantes",
        }
        for key, heading in section_labels.items():
            value = payload.get(key)
            if not value:
                continue
            sections.append(heading)
            if isinstance(value, list):
                sections.extend([f"- {item}" for item in value if str(item).strip()])
            else:
                sections.append(str(value).strip())

        return "\n\n".join(section for section in sections if str(section).strip())

    def _sanitize_response_for_display(self, texto):
        if not texto:
            return ""
        try:
            parsed = json.loads(texto)
            if isinstance(parsed, dict) and parsed.get("acao") == "tool_call":
                texto = (parsed.get("texto") or "").strip() or "O modelo tentou usar ferramentas nativas, mas este fluxo da GUI ainda não executa tool calls automáticas."
            else:
                return self._structured_response_to_markdown(parsed)
        except Exception:
            pass

        pattern = r"<(" + "|".join(XML_TAGS) + r")>.*?</\1>"
        texto = re.sub(pattern, "", texto, flags=re.DOTALL | re.IGNORECASE)
        texto = re.sub(r"\[EMOTION.*?\]\s*", "", texto, flags=re.IGNORECASE)
        texto = re.sub(r"\[INDEX_\d+\.\d+(?:,\s*INDEX_\d+\.\d+)*\]", "", texto)
        texto = re.sub(r"ã€.*?ã€‘", "", texto, flags=re.DOTALL)
        texto = re.sub(r"\n{3,}", "\n\n", texto)
        return texto.strip()

    def _meta_label(self, request_meta):
        if not request_meta:
            return ""
        label = f"{request_meta.get('provider', '?')}/{request_meta.get('model', '?')}"
        backend = request_meta.get("backend")
        if backend:
            label += f" • {backend}"
        if request_meta.get("routed"):
            label += " • auto-route"
        token_count = request_meta.get("token_count")
        if token_count:
            label += f" • {token_count} tok"
        return label

    def _adicionar_msg(self, tag, autor, texto, attachments=None, generated_images=None, request_meta=None):
        attachments = attachments or []
        generated_images = generated_images or []
        if tag == "system":
            lbl = ctk.CTkLabel(self.chat_scroll, text=texto, font=FONT_SMALL, text_color=COLORS["text_muted"], wraplength=920, justify="center")
            lbl.grid(row=self._bubble_row, column=0, padx=40, pady=(4, 2), sticky="ew")
            self._bubble_row += 1
            self._scroll_to_bottom()
            return

        if tag == "user":
            anchor, bg, border, padx, name_color = "e", BUBBLE_USER, BUBBLE_BORDER_USER, (120, 10), COLORS["blue_neon"]
        else:
            anchor, bg, border, padx, name_color = "w", BUBBLE_HANA, BUBBLE_BORDER_HANA, (10, 120), COLORS["purple_neon"]

        bubble = ctk.CTkFrame(self.chat_scroll, fg_color=bg, corner_radius=16, border_width=1, border_color=border)
        bubble.grid(row=self._bubble_row, column=0, padx=padx, pady=(7, 3), sticky=anchor)
        self._bubble_row += 1

        header = ctk.CTkFrame(bubble, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(10, 0))
        ctk.CTkLabel(header, text=autor, font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color=name_color).pack(side="left")
        ctk.CTkLabel(header, text=time.strftime("%H:%M"), font=FONT_SMALL, text_color=COLORS["text_muted"]).pack(side="right")

        meta_label = self._meta_label(request_meta)
        if meta_label:
            ctk.CTkLabel(bubble, text=meta_label, font=FONT_SMALL, text_color=COLORS["text_muted"], wraplength=720, justify="left").pack(anchor="w", padx=12, pady=(4, 0))

        self._render_rich_text(bubble, texto)
        if attachments:
            self._render_attachment_cards(bubble, attachments)
        if generated_images:
            self._render_generated_images(bubble, generated_images)
        if tag == "hana" and texto.strip():
            footer = ctk.CTkFrame(bubble, fg_color="transparent")
            footer.pack(fill="x", padx=12, pady=(0, 10))
            ctk.CTkButton(
                footer,
                text="Ler em voz alta",
                width=104,
                height=26,
                fg_color="transparent",
                hover_color=COLORS["purple_dark"],
                text_color=COLORS["text_muted"],
                font=FONT_SMALL,
                command=lambda t=texto: self._falar_texto(t),
            ).pack(side="left")
        self._scroll_to_bottom()

    def _clean_inline_markdown(self, text):
        text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
        text = re.sub(r"\*(.*?)\*", r"\1", text)
        text = re.sub(r"__(.*?)__", r"\1", text)
        text = re.sub(r"_(.*?)_", r"\1", text)
        text = re.sub(r"`([^`]+)`", r"“\1”", text)
        return text.strip()

    def _render_heading(self, parent, level, text):
        size = {1: 22, 2: 18, 3: 15}.get(level, 14)
        ctk.CTkLabel(
            parent,
            text=self._clean_inline_markdown(text),
            font=ctk.CTkFont(family="Segoe UI", size=size, weight="bold"),
            text_color=COLORS["text_primary"],
            wraplength=720,
            justify="left",
            anchor="w",
        ).pack(fill="x", padx=12, pady=(8, 2))

    def _render_paragraph(self, parent, text):
        cleaned = self._clean_inline_markdown(text)
        if not cleaned:
            return
        ctk.CTkLabel(
            parent,
            text=cleaned,
            font=FONT_BODY,
            text_color=COLORS["text_primary"],
            wraplength=720,
            justify="left",
            anchor="w",
        ).pack(fill="x", padx=12, pady=(3, 1))

    def _render_list_item(self, parent, marker, text):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=(2, 1))
        ctk.CTkLabel(row, text=marker, font=FONT_BODY, text_color=COLORS["purple_neon"], width=24, anchor="n").pack(side="left")
        ctk.CTkLabel(
            row,
            text=self._clean_inline_markdown(text),
            font=FONT_BODY,
            text_color=COLORS["text_primary"],
            wraplength=690,
            justify="left",
            anchor="w",
        ).pack(side="left", fill="x", expand=True)

    def _render_quote(self, parent, text):
        frame = ctk.CTkFrame(parent, fg_color="#16151F", corner_radius=10, border_width=1, border_color=COLORS["border"])
        frame.pack(fill="x", padx=12, pady=(4, 6))
        ctk.CTkLabel(
            frame,
            text=self._clean_inline_markdown(text),
            font=FONT_BODY,
            text_color=COLORS["text_secondary"],
            wraplength=700,
            justify="left",
            anchor="w",
        ).pack(fill="x", padx=10, pady=8)

    def _render_code_block(self, parent, language, code):
        code_box = ctk.CTkFrame(parent, fg_color="#141827", corner_radius=10)
        code_box.pack(fill="x", padx=12, pady=(4, 6))
        if language:
            ctk.CTkLabel(code_box, text=language.upper(), font=FONT_SMALL, text_color=COLORS["text_muted"]).pack(anchor="w", padx=8, pady=(6, 0))
        ctk.CTkLabel(
            code_box,
            text=code.strip(),
            font=("Consolas", 11),
            text_color="#E2E8F0",
            wraplength=700,
            justify="left",
            anchor="w",
        ).pack(fill="x", padx=8, pady=(4, 8))

    def _render_rich_text(self, parent, texto):
        display_text = self._sanitize_response_for_display(texto) or "(Processando internamente...)"
        lines = display_text.splitlines()
        paragraph_lines = []
        in_code = False
        code_lang = ""
        code_lines = []

        def flush_paragraph():
            if paragraph_lines:
                paragraph = "\n".join(paragraph_lines).strip()
                if paragraph:
                    self._render_paragraph(parent, paragraph)
                paragraph_lines.clear()

        for raw_line in lines:
            line = raw_line.rstrip()
            stripped = line.strip()

            if stripped.startswith("```"):
                flush_paragraph()
                if in_code:
                    self._render_code_block(parent, code_lang, "\n".join(code_lines))
                    in_code = False
                    code_lang = ""
                    code_lines = []
                else:
                    in_code = True
                    code_lang = stripped[3:].strip()
                continue

            if in_code:
                code_lines.append(line)
                continue

            if not stripped:
                flush_paragraph()
                ctk.CTkFrame(parent, fg_color="transparent", height=4).pack(fill="x")
                continue

            heading_match = re.match(r"^(#{1,3})\s+(.*)$", stripped)
            if heading_match:
                flush_paragraph()
                self._render_heading(parent, len(heading_match.group(1)), heading_match.group(2))
                continue

            quote_match = re.match(r"^>\s?(.*)$", stripped)
            if quote_match:
                flush_paragraph()
                self._render_quote(parent, quote_match.group(1))
                continue

            bullet_match = re.match(r"^[-*+]\s+(.*)$", stripped)
            if bullet_match:
                flush_paragraph()
                self._render_list_item(parent, "•", bullet_match.group(1))
                continue

            number_match = re.match(r"^(\d+)\.\s+(.*)$", stripped)
            if number_match:
                flush_paragraph()
                self._render_list_item(parent, f"{number_match.group(1)}.", number_match.group(2))
                continue

            paragraph_lines.append(line)

        flush_paragraph()
        if in_code and code_lines:
            self._render_code_block(parent, code_lang, "\n".join(code_lines))

    def _render_attachment_cards(self, parent, attachments):
        container = ctk.CTkFrame(parent, fg_color="transparent")
        container.pack(fill="x", padx=12, pady=(6, 8))
        for path in attachments:
            kind = self._infer_file_kind(path)
            if kind == "image":
                self._render_image_attachment(container, path, os.path.basename(path))
            else:
                self._render_file_card(container, path, kind)

    def _render_generated_images(self, parent, generated_images):
        container = ctk.CTkFrame(parent, fg_color="transparent")
        container.pack(fill="x", padx=12, pady=(6, 8))
        for path in generated_images:
            self._render_image_attachment(container, path, "Imagem gerada")

    def _render_image_attachment(self, parent, path, title):
        frame = ctk.CTkFrame(parent, fg_color=COLORS["bg_darkest"], corner_radius=12, border_width=1, border_color=COLORS["border"])
        frame.pack(anchor="w", pady=4)
        ctk.CTkLabel(frame, text=title, font=FONT_SMALL, text_color=COLORS["text_secondary"]).pack(anchor="w", padx=8, pady=(6, 4))
        if HAS_PIL and os.path.exists(path):
            try:
                img = PILImage.open(path)
                ratio = min(340 / img.size[0], 240 / img.size[1], 1)
                size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=size)
                self._tk_images.append(ctk_img)
                ctk.CTkLabel(frame, text="", image=ctk_img).pack(padx=8, pady=(0, 8))
            except Exception as e:
                logger.warning("[CHAT GUI] Falha ao renderizar imagem %s: %s", path, e)
        ctk.CTkButton(frame, text="Abrir", width=70, height=26, fg_color=COLORS["purple_dim"], hover_color=COLORS["purple_neon"], font=FONT_SMALL, command=lambda p=path: self._open_file(p)).pack(anchor="w", padx=8, pady=(0, 8))

    def _render_file_card(self, parent, path, kind):
        card = ctk.CTkFrame(parent, fg_color=COLORS["bg_darkest"], corner_radius=10, border_width=1, border_color=COLORS["border"])
        card.pack(fill="x", pady=4)
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=(6, 2))
        ctk.CTkLabel(row, text=self._icon_for_kind(kind), font=FONT_SMALL, text_color=COLORS["purple_neon"]).pack(side="left")
        ctk.CTkLabel(row, text=os.path.basename(path), font=FONT_SMALL, text_color=COLORS["text_primary"]).pack(side="left", padx=(8, 0))
        ctk.CTkLabel(card, text=path, font=FONT_SMALL, text_color=COLORS["text_muted"], wraplength=700, justify="left").pack(anchor="w", padx=8, pady=(0, 4))
        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.pack(fill="x", padx=8, pady=(0, 8))
        ctk.CTkButton(actions, text="Abrir", width=68, height=24, fg_color=COLORS["purple_dim"], hover_color=COLORS["purple_neon"], font=FONT_SMALL, command=lambda p=path: self._open_file(p)).pack(side="left")
        if kind == "audio":
            ctk.CTkButton(actions, text="Tocar", width=68, height=24, fg_color=COLORS["bg_card_hover"], hover_color=COLORS["purple_dark"], font=FONT_SMALL, command=lambda p=path: self._tocar_audio_anexo(p)).pack(side="left", padx=(6, 0))

    def _scroll_to_bottom(self):
        self.chat_scroll.update_idletasks()
        self.chat_scroll._parent_canvas.yview_moveto(1.0)

    def _is_request_cancelled(self, request_id, cancel_event):
        return cancel_event.is_set() or self._active_request_id != request_id

    def _status_from_meta(self, request_meta):
        label = self._meta_label(request_meta)
        if not label:
            return "Resposta recebida."
        return f"Resposta recebida • {label}"

    def _enviar(self):
        texto = self._get_input_text().strip()
        if not texto and not self._anexos:
            return
        if not texto and self._anexos:
            texto = "Analise os arquivos anexados neste chat."

        anexos_envio = list(self._anexos)
        self._clear_input()
        self._anexos = []
        self._atualizar_container_anexos()

        self._adicionar_msg("user", "Nakamura", texto, attachments=anexos_envio)
        self.btn_enviar.configure(state="disabled", text="...")
        self.lbl_chat_status.configure(text="Processando resposta da GUI...", text_color=COLORS["yellow"])

        self._request_seq += 1
        request_id = self._request_seq
        cancel_event = threading.Event()
        self._active_request_id = request_id
        self._active_cancel_event = cancel_event

        def _processar():
            request_meta = None
            try:
                task_type = self._classify_task(texto, anexos_envio)
                execution_target = self._resolve_execution_target(task_type, anexos_envio)
                routed = bool(execution_target.get("routed"))

                if execution_target["provider"] == self.combo_chat_prov.get().strip().lower() and execution_target["model"] == self.combo_chat_modelo.get().strip():
                    llm = self._get_chat_llm()
                else:
                    llm = self._create_llm_instance(execution_target["provider"], execution_target["model"], cache=False)

                if not llm:
                    raise RuntimeError("Não foi possível inicializar o provider LLM.")

                if self._is_request_cancelled(request_id, cancel_event):
                    return

                memory_manager = self._get_memory_manager()
                memory_context = memory_manager.get_context(texto)
                capabilities = get_provider_capabilities(
                    execution_target["provider"],
                    execution_target["model"],
                    vision_enabled=CONFIG.get("VISAO_ATIVA", False),
                )
                image_b64, arquivos_multimidia, text_blocks = self._prepare_attachments_for_llm(anexos_envio, capabilities)
                mensagem_final = texto
                if text_blocks:
                    mensagem_final += "\n\n" + "\n\n".join(text_blocks)

                request_context = build_request_context(
                    channel="control_center_chat",
                    task_type=task_type,
                    override_model=execution_target["model"],
                    routed=routed,
                    response_schema=self._build_response_schema(task_type),
                    native_search=False if anexos_envio else None,
                )
                sistema_prompt = self._build_gui_prompt(mensagem_final, memory_context, task_type, anexos_envio, request_context)

                resposta = llm.gerar_resposta(
                    chat_history=self._session_history[-20:],
                    sistema_prompt=sistema_prompt,
                    user_message=mensagem_final,
                    image_b64=image_b64,
                    arquivos_multimidia=arquivos_multimidia if arquivos_multimidia else None,
                    request_context=request_context,
                )
                request_meta = dict(getattr(llm, "last_request_meta", {}) or {})
                request_meta["provider"] = execution_target["provider"]
                request_meta["model"] = request_meta.get("model") or execution_target["model"]
                request_meta["routed"] = routed

                if self._is_request_cancelled(request_id, cancel_event):
                    return

                if not resposta:
                    resposta = "(sem resposta)"

                actions = self._extract_xml_actions(resposta)
                generated_images = []
                for fact in actions.get("salvar_memoria", []):
                    try:
                        memory_manager.add_fact("hana_nota", "deve_lembrar", fact)
                    except Exception as e:
                        logger.warning("[CHAT GUI] Falha ao salvar memória manual: %s", e)

                for prompt in actions.get("gerar_imagem", []):
                    if self._is_request_cancelled(request_id, cancel_event):
                        return
                    path = self._get_image_gen().generate(prompt)
                    if path:
                        generated_images.append(path)

                for prompt in actions.get("editar_imagem", []):
                    if self._is_request_cancelled(request_id, cancel_event):
                        return
                    path = self._get_image_gen().edit(prompt)
                    if path:
                        generated_images.append(path)

                resp_display = self._sanitize_response_for_display(resposta)
                if not resp_display and generated_images:
                    resp_display = "Imagem gerada aqui no chat."
                elif not resp_display:
                    resp_display = "(sem resposta visível)"

                if self._is_request_cancelled(request_id, cancel_event):
                    return

                self._ultima_resposta = resposta
                history_content = resp_display
                self._session_history.append({"role": "Nakamura", "content": texto})
                self._session_history.append({"role": "Hana", "content": history_content})
                memory_manager.add_interaction("Nakamura", texto)
                memory_manager.add_interaction("Hana", history_content)

                self.after(0, lambda: self._adicionar_msg("hana", "Hana", resp_display, generated_images=generated_images, request_meta=request_meta))
                self.after(0, lambda: self.lbl_chat_status.configure(text=self._status_from_meta(request_meta), text_color=COLORS["green"]))
            except Exception as e:
                logger.error("[CHAT GUI] Erro: %s", e)
                if not self._is_request_cancelled(request_id, cancel_event):
                    self.after(0, lambda err=e: self._adicionar_msg("system", "ERRO", f"Erro no chat da GUI: {err}"))
                    self.after(0, lambda: self.lbl_chat_status.configure(text=f"Erro: {e}", text_color=COLORS["red"]))
            finally:
                if self._active_request_id == request_id:
                    self._active_request_id = None
                    self._active_cancel_event = None
                self.after(0, lambda: self.btn_enviar.configure(state="normal", text="Enviar"))

        threading.Thread(target=_processar, daemon=True).start()

    def _abrir_anexo(self):
        filepaths = filedialog.askopenfilenames(
            title="Anexar arquivo(s)",
            filetypes=[
                ("Imagens", "*.png *.jpg *.jpeg *.webp *.gif *.bmp"),
                ("Audio", "*.mp3 *.wav *.ogg *.m4a *.flac *.aac"),
                ("Video", "*.mp4 *.avi *.mov *.webm *.mkv"),
                ("Documentos", "*.pdf *.doc *.docx *.txt *.md *.json *.csv *.xml *.yaml *.yml"),
                ("Todos", "*.*"),
            ],
        )
        if filepaths:
            for path in filepaths:
                if path not in self._anexos and os.path.exists(path):
                    self._anexos.append(path)
            self._atualizar_container_anexos()

    def _atualizar_container_anexos(self):
        for child in self.frame_anexo_list.winfo_children():
            child.destroy()
        if not self._anexos:
            self.frame_anexo.grid_forget()
            return
        self.lbl_anexo.configure(text=f"{len(self._anexos)} arquivo(s) prontos para envio")
        for path in self._anexos:
            kind = self._infer_file_kind(path)
            card = ctk.CTkFrame(self.frame_anexo_list, fg_color=COLORS["bg_darkest"], corner_radius=10, border_width=1, border_color=COLORS["border"])
            card.pack(fill="x", pady=3)
            ctk.CTkLabel(card, text=self._icon_for_kind(kind), font=FONT_SMALL, text_color=COLORS["purple_neon"]).pack(side="left", padx=(8, 6), pady=6)
            ctk.CTkLabel(card, text=os.path.basename(path), font=FONT_SMALL, text_color=COLORS["text_primary"]).pack(side="left", pady=6)
            ctk.CTkButton(card, text="Remover", width=72, height=24, fg_color="transparent", hover_color="#552222", text_color="#FF6B6B", font=FONT_SMALL, command=lambda p=path: self._remover_anexo(p)).pack(side="right", padx=8, pady=6)
        self.frame_anexo.grid(row=4, column=0, padx=15, pady=(0, 6), sticky="ew")

    def _remover_anexo(self, path):
        self._anexos = [item for item in self._anexos if item != path]
        self._atualizar_container_anexos()

    def _gravar_audio(self):
        self.btn_mic.configure(text="REC", text_color=COLORS["red"])
        self._adicionar_msg("system", "Hana", "Gravando áudio... aguarde.")

        def _capturar():
            texto_transcrito = ""
            try:
                from src.modules.voice.stt_whisper import MotorSTTWhisper

                stt = MotorSTTWhisper()
                texto_transcrito = stt.transcrever()
            except Exception as e:
                texto_transcrito = f"(Erro STT: {e})"
            finally:
                self.after(0, lambda: self.btn_mic.configure(text="Mic", text_color=COLORS["text_muted"]))
                if texto_transcrito:
                    self.after(0, lambda t=texto_transcrito: self.entry_msg.insert("end", t))
                    self.after(0, self._update_input_placeholder)

        threading.Thread(target=_capturar, daemon=True).start()

    def _tocar_audio_anexo(self, path):
        try:
            import pygame

            if not pygame.mixer.get_init():
                pygame.mixer.init()
            if pygame.mixer.music.get_busy() and self._audio_preview_path == path:
                pygame.mixer.music.stop()
                self._audio_preview_path = None
                return
            pygame.mixer.music.load(path)
            pygame.mixer.music.play()
            self._audio_preview_path = path
        except Exception as e:
            logger.error("[CHAT GUI] Erro ao tocar áudio %s: %s", path, e)
            self.lbl_chat_status.configure(text=f"Falha ao tocar áudio: {e}", text_color=COLORS["red"])

    def _open_file(self, path):
        try:
            os.startfile(path)
        except AttributeError:
            webbrowser.open(path)
        except Exception as e:
            logger.error("[CHAT GUI] Falha ao abrir arquivo %s: %s", path, e)
            self.lbl_chat_status.configure(text=f"Falha ao abrir arquivo: {e}", text_color=COLORS["red"])

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
                logger.error("[CHAT GUI] Erro TTS: %s", e)

        threading.Thread(target=_run, daemon=True).start()

    def _parar_fala(self):
        if self._active_cancel_event:
            self._active_cancel_event.set()
            self._active_request_id = None
            self.lbl_chat_status.configure(text="Geração cancelada pelo usuário.", text_color=COLORS["yellow"])
        try:
            import pygame

            if pygame.mixer.get_init():
                pygame.mixer.stop()
        except Exception:
            pass
