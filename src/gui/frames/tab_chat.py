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
from src.core.prompt_builder import build_gui_system_prompt
from src.core.provider_catalog import get_llm_providers, get_model_ids_for_provider
from src.core.request_profiles import build_request_context, get_chat_settings
from src.core.runtime_capabilities import get_provider_capabilities, get_stop_hotkey_settings
from src.gui.design import COLORS, FONT_BODY, FONT_SMALL, FONT_TITLE
from src.modules.media import HanaMusicGen
from src.modules.tools.inbox_manager import InboxManager
from src.modules.tools.pc_control import execute_pc_action, parse_pc_action_payload
from src.modules.voice.audio_control import poll_external_stop, register_stop_callback, request_global_stop, unregister_stop_callback
from src.utils.hana_tags import DISPLAY_XML_TAGS, MEDIA_XML_TAGS, extract_xml_actions, strip_xml_tags
from src.utils.sentence_divider import SentenceDivider
from src.utils.text import repair_mojibake_text

logger = logging.getLogger(__name__)

try:
    from PIL import Image as PILImage
    from PIL import ImageGrab as PILImageGrab

    HAS_PIL = True
except ImportError:
    PILImageGrab = None
    HAS_PIL = False

try:
    from tkinterdnd2 import COPY, DND_FILES, TkinterDnD

    HAS_DND = True
except Exception:
    COPY = None
    DND_FILES = None
    TkinterDnD = None
    HAS_DND = False

try:
    import keyboard
except Exception:
    keyboard = None


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
AUDIO_EXTS = {".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac"}
VIDEO_EXTS = {".mp4", ".avi", ".mov", ".webm", ".mkv", ".m4v"}
TEXT_EXTS = {".txt", ".md", ".json", ".csv", ".xml", ".yaml", ".yml", ".log", ".docx"}
LONG_FORM_TASKS = {"analise_midia_estruturada", "media_summary", "media_exact_request", "media_question", "resumo_detalhado"}
STRUCTURED_MEDIA_TASKS = {"analise_midia_estruturada"}
CLIPBOARD_CACHE_DIR = os.path.join("temp", "clipboard_attachments")

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
            border_width=0,
            border_color=COLORS["bg_dark"],
        )
        self._ultima_resposta = ""
        self._anexos = []
        self._tk_images = []
        self._llm_instance = None
        self._memory_manager = None
        self._image_gen = None
        self._music_gen = None
        self._session_history = []
        self._audio_preview_path = None
        self._inbox_manager = InboxManager()
        self._request_seq = 0
        self._active_request_id = None
        self._active_cancel_event = None
        self._active_media_jobs = {}
        self._active_stream_state = None
        self._stop_hotkey_handle = None
        self._stop_hotkey_signature = None
        self._active_tts_thread = None
        self._stop_callback_name = f"chat_gui_{id(self)}"

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        self._build_layout()
        self._carregar_config_chat()
        register_stop_callback(self._stop_callback_name, self._handle_global_stop_signal)
        self.after(200, self._ativar_dragdrop)
        self.after(300, self._sync_stop_hotkey_binding)
        self.after(350, self._poll_global_stop_signal)

    def _build_layout(self):
        top_shell, top_panel = self._create_visual_shell(
            self,
            outer_color=COLORS["border_strong"],
            inner_color=COLORS["bg_card"],
            corner_radius=14,
            padding=2,
        )
        top_shell.grid(row=0, column=0, padx=15, pady=(14, 8), sticky="ew")
        top_panel.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(top_panel, fg_color="transparent")
        header.grid(row=0, column=0, padx=16, pady=(12, 6), sticky="ew")
        ctk.CTkLabel(header, text="Control Center Chat", font=FONT_TITLE, text_color=COLORS["text_primary"]).pack(side="left")
        ctk.CTkLabel(header, text="GUI da Hana", font=FONT_SMALL, text_color=COLORS["text_muted"]).pack(side="left", padx=(10, 0))

        self.toolbar = ctk.CTkFrame(
            top_panel,
            fg_color=COLORS["bg_darkest"],
            corner_radius=11,
            height=44,
            border_width=0,
        )
        self.toolbar.grid(row=1, column=0, padx=14, pady=(0, 6), sticky="ew")
        self.toolbar.grid_columnconfigure(4, weight=1)
        ctk.CTkLabel(self.toolbar, text="Provedor:", font=FONT_SMALL, text_color=COLORS["text_muted"]).grid(row=0, column=0, padx=(12, 4), pady=8, sticky="w")
        self.combo_chat_prov = ctk.CTkComboBox(
            self.toolbar,
            values=get_llm_providers(),
            width=135,
            height=30,
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
        self.combo_chat_prov.grid(row=0, column=1, padx=(0, 8), pady=7, sticky="w")
        ctk.CTkLabel(self.toolbar, text="Modelo:", font=FONT_SMALL, text_color=COLORS["text_muted"]).grid(row=0, column=2, padx=(0, 4), pady=8, sticky="w")
        self.combo_chat_modelo = ctk.CTkComboBox(
            self.toolbar,
            values=[""],
            width=225,
            height=30,
            fg_color=COLORS["bg_darkest"],
            border_color=COLORS["border"],
            button_color=COLORS["purple_dim"],
            button_hover_color=COLORS["purple_neon"],
            dropdown_fg_color=COLORS["bg_card"],
            dropdown_hover_color=COLORS["purple_dark"],
            text_color=COLORS["text_primary"],
            font=FONT_SMALL,
        )
        self.combo_chat_modelo.grid(row=0, column=3, padx=(0, 10), pady=7, sticky="w")
        self.lbl_input_hint = ctk.CTkLabel(
            self.toolbar,
            text="Enter envia | Shift+Enter quebra linha | Arraste arquivos aqui",
            font=FONT_SMALL,
            text_color=COLORS["text_muted"],
            anchor="w",
        )
        self.lbl_input_hint.grid(row=0, column=4, padx=(6, 12), pady=8, sticky="ew")
        self.btn_stop = ctk.CTkButton(
            self.toolbar,
            text="Parar",
            width=84,
            height=30,
            fg_color=COLORS["bg_darkest"],
            hover_color=COLORS["red"],
            text_color=COLORS["text_secondary"],
            border_width=2,
            border_color=COLORS["border"],
            font=FONT_SMALL,
            command=self._parar_fala,
        )
        self.btn_stop.grid(row=0, column=5, padx=(0, 10), pady=7, sticky="e")

        status_shell, self.status_bar = self._create_visual_shell(
            top_panel,
            outer_color=COLORS["border_focus"],
            inner_color=COLORS["bg_darkest"],
            corner_radius=11,
            padding=1,
        )
        status_shell.grid(row=2, column=0, padx=14, pady=(0, 12), sticky="ew")
        self.status_bar.grid_columnconfigure(0, weight=1)
        self.lbl_chat_status = ctk.CTkLabel(self.status_bar, text="Chat da GUI pronto.", font=FONT_SMALL, text_color=COLORS["text_muted"], anchor="w")
        self.lbl_chat_status.grid(row=0, column=0, padx=12, pady=(6, 5), sticky="ew")

        chat_shell, chat_inner = self._create_visual_shell(
            self,
            outer_color=COLORS["border_strong"],
            inner_color=COLORS["bg_darkest"],
            corner_radius=14,
            padding=2,
        )
        chat_shell.grid(row=3, column=0, padx=15, pady=(0, 8), sticky="nsew")
        chat_inner.grid_columnconfigure(0, weight=1)
        chat_inner.grid_rowconfigure(0, weight=1)

        self.chat_scroll = ctk.CTkScrollableFrame(
            chat_inner,
            fg_color=COLORS["bg_darkest"],
            corner_radius=12,
            border_width=0,
            border_color=COLORS["bg_darkest"],
            scrollbar_button_color=COLORS["purple_dim"],
            scrollbar_button_hover_color=COLORS["purple_neon"],
        )
        self.chat_scroll.grid(row=0, column=0, sticky="nsew")
        self.chat_scroll.grid_columnconfigure(0, weight=1)
        self._bubble_row = 0

        self.frame_anexo = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=12, border_width=2, border_color=COLORS["border"])
        self.lbl_anexo = ctk.CTkLabel(self.frame_anexo, text="Arquivos prontos para envio", font=FONT_SMALL, text_color=COLORS["text_secondary"])
        self.lbl_anexo.pack(anchor="w", padx=12, pady=(8, 4))
        self.frame_anexo_list = ctk.CTkFrame(self.frame_anexo, fg_color="transparent")
        self.frame_anexo_list.pack(fill="x", padx=10, pady=(0, 8))

        self.input_frame = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=12, border_width=2, border_color=COLORS["border"])
        self.input_frame.grid(row=5, column=0, padx=15, pady=(0, 15), sticky="ew")
        self.input_frame.grid_columnconfigure(2, weight=1)

        self.btn_mic = ctk.CTkButton(self.input_frame, text="Mic", width=44, height=44, fg_color="transparent", hover_color=COLORS["purple_dark"], text_color=COLORS["text_muted"], font=("Segoe UI", 12, "bold"), command=self._gravar_audio)
        self.btn_mic.grid(row=0, column=0, padx=(8, 4), pady=8)
        self.btn_anexo = ctk.CTkButton(self.input_frame, text="+", width=44, height=44, fg_color="transparent", hover_color=COLORS["bg_card_hover"], text_color=COLORS["text_muted"], font=("Segoe UI", 20, "bold"), command=self._abrir_anexo)
        self.btn_anexo.grid(row=0, column=1, padx=(0, 0), pady=8)

        textbox_frame = ctk.CTkFrame(
            self.input_frame,
            fg_color=COLORS["bg_darkest"],
            corner_radius=10,
            border_width=1,
            border_color=COLORS["border_subtle"],
        )
        textbox_frame.grid(row=0, column=2, padx=8, pady=8, sticky="ew")
        textbox_frame.grid_columnconfigure(0, weight=1)
        self.entry_msg = ctk.CTkTextbox(textbox_frame, height=84, fg_color=COLORS["bg_darkest"], border_width=0, text_color=COLORS["text_primary"], font=FONT_BODY, wrap="word")
        self.entry_msg.grid(row=0, column=0, sticky="ew")
        self.entry_msg.bind("<Return>", self._on_input_return)
        self.entry_msg.bind("<KP_Enter>", self._on_input_return)
        self.entry_msg.bind("<KeyRelease>", self._update_input_placeholder)
        self.entry_msg.bind("<Control-v>", self._on_paste)
        self.entry_msg.bind("<Control-V>", self._on_paste)
        self.entry_placeholder = ctk.CTkLabel(textbox_frame, text="Digite uma mensagem para a Hana... (Shift+Enter quebra linha)", font=FONT_BODY, text_color=COLORS["text_muted"])
        self.entry_placeholder.place(x=12, y=12)

        self.btn_enviar = ctk.CTkButton(self.input_frame, text="Enviar", width=110, height=44, fg_color=COLORS["purple_dim"], hover_color=COLORS["purple_neon"], font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), command=self._enviar)
        self.btn_enviar.grid(row=0, column=3, padx=(0, 8), pady=8)

        self._adicionar_msg("system", "Hana", "Control Center online. Este chat nao e o terminal.")

    def _create_visual_shell(self, parent, *, outer_color, inner_color, corner_radius=12, padding=2):
        shell = ctk.CTkFrame(parent, fg_color=outer_color, corner_radius=corner_radius, border_width=0)
        inner = ctk.CTkFrame(
            shell,
            fg_color=inner_color,
            corner_radius=max(0, corner_radius - padding),
            border_width=0,
        )
        inner.pack(fill="both", expand=True, padx=padding, pady=padding)
        return shell, inner

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
        return get_model_ids_for_provider(provedor)

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
        if prov == "openai":
            from src.providers.openai_provider import OpenAIProvider

            return OpenAIProvider
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

    def _get_music_gen(self):
        if self._music_gen is None:
            self._music_gen = HanaMusicGen()
        return self._music_gen

    def on_config_reload(self):
        self._sync_stop_hotkey_binding()

    def destroy(self):
        self._teardown_stop_hotkey()
        unregister_stop_callback(self._stop_callback_name)
        return super().destroy()

    def _handle_global_stop_signal(self, **_kwargs):
        if self.winfo_exists():
            self.after(0, self._parar_fala_local)

    def _poll_global_stop_signal(self):
        if not self.winfo_exists():
            return
        try:
            poll_external_stop()
        except Exception:
            logger.debug("[CHAT GUI] Falha ao verificar sinal global de stop.", exc_info=True)
        self.after(250, self._poll_global_stop_signal)

    def _handle_stop_hotkey(self):
        if self.winfo_exists():
            request_global_stop("gui_hotkey")

    def _teardown_stop_hotkey(self):
        if keyboard is None or self._stop_hotkey_handle is None:
            self._stop_hotkey_handle = None
            return
        try:
            keyboard.remove_hotkey(self._stop_hotkey_handle)
        except Exception:
            logger.debug("[CHAT GUI] Nao foi possivel remover hotkey de parada.", exc_info=True)
        self._stop_hotkey_handle = None

    def _sync_stop_hotkey_binding(self):
        settings = get_stop_hotkey_settings()
        signature = (bool(settings["enabled"]), str(settings["key"]).upper())
        if signature == self._stop_hotkey_signature:
            return

        self._teardown_stop_hotkey()
        self._stop_hotkey_signature = signature

        if not settings["enabled"]:
            return
        if keyboard is None:
            logger.warning("[CHAT GUI] Biblioteca 'keyboard' indisponivel para o hotkey de parada.")
            return

        try:
            self._stop_hotkey_handle = keyboard.add_hotkey(
                settings["key"],
                lambda: self.after(0, self._handle_stop_hotkey),
                suppress=False,
                trigger_on_release=False,
            )
            logger.info("[CHAT GUI] Hotkey global de parada registrada: %s", settings["key"])
        except Exception as e:
            logger.warning("[CHAT GUI] Falha ao registrar hotkey de parada %s: %s", settings["key"], e)

    def _add_attachment_paths(self, paths):
        added = 0
        for raw_path in paths or []:
            path = os.path.abspath(str(raw_path).strip().strip('"').strip("'"))
            if not path or not os.path.exists(path):
                continue
            if path in self._anexos:
                continue
            self._anexos.append(path)
            added += 1
        if added:
            self._atualizar_container_anexos()
            self.lbl_chat_status.configure(text=f"{added} anexo(s) adicionados ao chat.", text_color=COLORS["green"])
        return added > 0

    def _save_clipboard_image(self, image):
        os.makedirs(CLIPBOARD_CACHE_DIR, exist_ok=True)
        filepath = os.path.join(CLIPBOARD_CACHE_DIR, f"clipboard_{int(time.time() * 1000)}.png")
        image.save(filepath, "PNG")
        return filepath

    def _extract_paths_from_text(self, text):
        if not text:
            return []

        candidates = []
        lines = [line.strip() for line in str(text).replace("\r", "\n").split("\n") if line.strip()]
        if not lines:
            return []

        for line in lines:
            clean = line.strip().strip('"').strip("'")
            if clean.startswith("{") and clean.endswith("}"):
                clean = clean[1:-1].strip()
            if not os.path.exists(clean):
                return []
            candidates.append(clean)
        return candidates

    def _on_paste(self, _event=None):
        try:
            clipboard_payload = PILImageGrab.grabclipboard() if PILImageGrab else None
        except Exception as e:
            logger.debug("[CHAT GUI] Falha ao ler clipboard via ImageGrab: %s", e)
            clipboard_payload = None

        if isinstance(clipboard_payload, list) and self._add_attachment_paths(clipboard_payload):
            return "break"

        if HAS_PIL and clipboard_payload is not None and hasattr(clipboard_payload, "save"):
            try:
                image_path = self._save_clipboard_image(clipboard_payload)
                if self._add_attachment_paths([image_path]):
                    return "break"
            except Exception as e:
                logger.error("[CHAT GUI] Falha ao salvar imagem colada: %s", e)

        try:
            text = self.clipboard_get()
        except Exception:
            return None

        candidate_paths = self._extract_paths_from_text(text)
        if candidate_paths and self._add_attachment_paths(candidate_paths):
            return "break"
        return None

    def _ativar_dragdrop(self):
        if not HAS_DND:
            self.lbl_input_hint.configure(text="Enter envia | Shift+Enter quebra linha | Use o clipe para anexar")
            return
        try:
            TkinterDnD._require(self.winfo_toplevel())
            for widget in (self, self.chat_scroll, self.input_frame, self.entry_msg):
                widget.drop_target_register(DND_FILES)
                widget.dnd_bind("<<Drop>>", self._on_drop_files)
        except Exception as e:
            logger.warning("[CHAT GUI] Drag-and-drop indisponivel: %s", e)
            self.lbl_input_hint.configure(text="Enter envia | Shift+Enter quebra linha | Use o clipe para anexar")

    def _on_drop_files(self, event):
        try:
            self._add_attachment_paths(self.tk.splitlist(event.data))
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
        if re.search(r"\b(gera|cria|criar|faz|fa[cç]a).*(imagem|foto|arte)\b", lowered):
            return "image_action"
        if re.search(r"\b(gera|cria|criar|faz|fa[cç]a|comp[oô]e|componha).*(m[uú]sica|musica|trilha|beat|can[cç][aã]o|song)\b", lowered):
            return "music_action"
        if re.search(r"\b(traduz|traduza|translation)\b", lowered):
            return "traducao"

        has_media = self._contains_media(anexos_envio)
        detail_keywords = ("resuma", "resume", "resumir", "detalha", "detalhe", "detalhar", "analisa", "analise", "analisar", "explica", "explique", "explicar")
        structured_media_keywords = ("reuniao", "reunião", "ata", "pontos", "decisoes", "decisões", "acoes", "ações", "encaminhamentos", "timeline", "linha do tempo")
        exact_media_keywords = (
            "letra",
            "lyrics",
            "transcreve",
            "transcrever",
            "transcricao",
            "transcrição",
            "texto completo",
            "fala completa",
            "palavra por palavra",
            "ritmo",
            "bpm",
            "andamento",
            "estrutura",
            "verso",
            "versos",
            "refrao",
            "refrão",
            "bridge",
            "ponte",
            "instrumentacao",
            "instrumentação",
            "melodia",
            "harmonia",
            "compasso",
        )
        if has_media:
            if any(keyword in lowered for keyword in exact_media_keywords):
                return "media_exact_request"
            if any(keyword in lowered for keyword in structured_media_keywords):
                return "analise_midia_estruturada"
            if any(keyword in lowered for keyword in detail_keywords) or not lowered:
                return "media_summary"
            return "media_question"

        if any(keyword in lowered for keyword in detail_keywords):
            return "resumo_detalhado"
        return "chat_normal"

    def _build_response_schema(self, task_type):
        if task_type not in STRUCTURED_MEDIA_TASKS:
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
                "titulo": {"type": "string", "description": "Titulo curto e objetivo do conteudo analisado."},
                "resumo_executivo": {"type": "string", "description": "Resumo claro e util em portugues."},
                "topicos_principais": {"type": "array", "items": {"type": "string"}, "description": "Principais assuntos tratados."},
                "decisoes": {"type": "array", "items": {"type": "string"}, "description": "Decisoes tomadas ou conclusoes fechadas."},
                "acoes": {"type": "array", "items": {"type": "string"}, "description": "Proximas acoes, tarefas ou encaminhamentos."},
                "riscos": {"type": "array", "items": {"type": "string"}, "description": "Riscos, bloqueios ou pontos de atencao."},
                "linha_do_tempo": {"type": "array", "items": {"type": "string"}, "description": "Sequencia resumida dos momentos ou etapas."},
                "trechos_relevantes": {"type": "array", "items": {"type": "string"}, "description": "Trechos ou citacoes importantes do conteudo."},
            },
            "required": ["titulo", "resumo_executivo", "topicos_principais", "acoes", "riscos"],
        }

    def _attachments_overview(self, anexos_envio):
        lines = []
        for path in anexos_envio:
            kind = self._infer_file_kind(path)
            lines.append(f"- {kind}: {os.path.basename(path)}")
        return "\n".join(lines) if lines else "- nenhum anexo"

    def _build_gui_prompt(self, user_message, memory_context, task_type, anexos_envio, request_context):
        return (
            build_gui_system_prompt(
                task_type=task_type,
                memory_context=memory_context,
                request_context=request_context,
                attachments_overview=self._attachments_overview(anexos_envio),
            )
            + f"\nMensagem atual do usuario:\n{user_message}"
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
                    raise RuntimeError("Arquivo .doc antigo ainda nao e suportado neste fluxo. Use .docx ou PDF.")
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
        route_to_media_model = task_type in LONG_FORM_TASKS and has_heavy_media
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
        return extract_xml_actions(
            texto,
            ("salvar_memoria", "gerar_imagem", "editar_imagem", "gerar_musica", "acao_pc"),
        )

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
            "topicos_principais": "### Topicos Principais",
            "decisoes": "### Decisoes",
            "acoes": "### Acoes",
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
                texto = (parsed.get("texto") or "").strip() or "O modelo tentou usar ferramentas nativas, mas este fluxo da GUI ainda nao executa tool calls automaticas."
            else:
                return self._structured_response_to_markdown(parsed)
        except Exception:
            pass

        texto = repair_mojibake_text(texto)
        texto = strip_xml_tags(texto, DISPLAY_XML_TAGS)
        texto = re.sub(r"\[EMOTION.*?\]\s*", "", texto, flags=re.IGNORECASE)
        texto = re.sub(r"\[INDEX_\d+\.\d+(?:,\s*INDEX_\d+\.\d+)*\]", "", texto)
        texto = re.sub(r"[\u200b-\u200f\u202a-\u202e]+", "", texto)
        texto = re.sub(r"\n{3,}", "\n\n", texto)
        return texto.strip()

    def _meta_label(self, request_meta):
        if not request_meta:
            return ""
        label = f"{request_meta.get('provider', '?')}/{request_meta.get('model', '?')}"
        backend = request_meta.get("backend")
        if backend:
            label += f" | {backend}"
        if request_meta.get("routed"):
            label += " | auto-route"
        token_count = request_meta.get("token_count")
        if token_count:
            label += f" | {token_count} tok"
        return label

    def _create_bubble_shell(self, tag, autor, request_meta=None):
        if tag == "user":
            side, bg, border, padx, name_color = "right", BUBBLE_USER, BUBBLE_BORDER_USER, (150, 18), COLORS["blue_neon"]
        else:
            side, bg, border, padx, name_color = "left", BUBBLE_HANA, BUBBLE_BORDER_HANA, (18, 150), COLORS["purple_neon"]

        row_shell = ctk.CTkFrame(self.chat_scroll, fg_color="transparent")
        row_shell.grid(row=self._bubble_row, column=0, padx=padx, pady=(8, 4), sticky="ew")
        row_shell.grid_columnconfigure(0, weight=1)
        self._bubble_row += 1

        bubble_shell = ctk.CTkFrame(row_shell, fg_color=border, corner_radius=18, border_width=0)
        bubble_shell.pack(side=side)
        bubble = ctk.CTkFrame(bubble_shell, fg_color=bg, corner_radius=16, border_width=0)
        bubble.pack(fill="both", expand=True, padx=2, pady=2)

        header = ctk.CTkFrame(bubble, fg_color="transparent")
        header.pack(fill="x", padx=14, pady=(12, 0))
        ctk.CTkLabel(
            header,
            text=repair_mojibake_text(autor),
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=name_color,
        ).pack(side="left")
        ctk.CTkLabel(header, text=time.strftime("%H:%M"), font=FONT_SMALL, text_color=COLORS["text_muted"]).pack(side="right", padx=(10, 0))

        meta_widget = None
        meta_label = self._meta_label(request_meta)
        if meta_label:
            meta_widget = ctk.CTkLabel(
                bubble,
                text=repair_mojibake_text(meta_label),
                font=FONT_SMALL,
                text_color=COLORS["text_muted"],
                wraplength=640,
                justify="left",
            )
            meta_widget.pack(anchor="w", padx=14, pady=(4, 0))

        body = ctk.CTkFrame(bubble, fg_color="transparent")
        body.pack(fill="x")
        return bubble, body, meta_widget

    def _add_hana_footer(self, bubble, texto):
        if not texto or not texto.strip():
            return
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

    def _create_streaming_bubble(self, request_id):
        bubble, body, meta_widget = self._create_bubble_shell("hana", "Hana")
        label = ctk.CTkLabel(
            body,
            text="Processando resposta da GUI...",
            font=FONT_BODY,
            text_color=COLORS["text_secondary"],
            wraplength=640,
            justify="left",
            anchor="w",
            width=540,
        )
        label.pack(fill="x", padx=14, pady=(8, 12))
        self._active_stream_state = {
            "request_id": request_id,
            "bubble": bubble,
            "body": body,
            "label": label,
            "meta": meta_widget,
            "text": "",
        }
        self._scroll_to_bottom()

    def _update_streaming_bubble(self, request_id, texto, request_meta=None):
        state = self._active_stream_state
        if not state or state.get("request_id") != request_id:
            return
        state["text"] = texto
        label = state.get("label")
        if label and label.winfo_exists():
            display_text = repair_mojibake_text(texto or "")
            if display_text.strip():
                label.configure(text=display_text, text_color=COLORS["text_primary"])
            else:
                label.configure(text="Processando resposta da GUI...", text_color=COLORS["text_secondary"])
        meta_widget = state.get("meta")
        meta_label = self._meta_label(request_meta)
        if meta_widget and meta_widget.winfo_exists():
            meta_widget.configure(text=repair_mojibake_text(meta_label))
        elif meta_label:
            state["meta"] = ctk.CTkLabel(
                state["bubble"],
                text=repair_mojibake_text(meta_label),
                font=FONT_SMALL,
                text_color=COLORS["text_muted"],
                wraplength=640,
                justify="left",
            )
            state["meta"].pack(anchor="w", padx=14, pady=(4, 0), before=state["body"])
        self._scroll_to_bottom()

    def _finalize_streaming_bubble(self, request_id, texto, generated_images=None, generated_media=None, request_meta=None):
        state = self._active_stream_state
        if not state or state.get("request_id") != request_id:
            self._adicionar_msg("hana", "Hana", texto, generated_images=generated_images, generated_media=generated_media, request_meta=request_meta)
            return

        body = state["body"]
        for child in body.winfo_children():
            child.destroy()
        self._render_rich_text(body, texto)
        if generated_images:
            self._render_generated_images(body, generated_images)
        if generated_media:
            self._render_generated_media(body, generated_media)
        self._add_hana_footer(state["bubble"], texto)
        self._active_stream_state = None
        self._scroll_to_bottom()

    def _cancel_streaming_bubble(self, request_id):
        state = self._active_stream_state
        if not state or state.get("request_id") != request_id:
            return
        if not (state.get("text") or "").strip():
            try:
                state["bubble"].destroy()
            except Exception:
                pass
            self._active_stream_state = None
            return
        label = state.get("label")
        if label and label.winfo_exists():
            label.configure(text=repair_mojibake_text((state.get("text") or "").strip()))
        self._active_stream_state = None

    def _adicionar_msg(self, tag, autor, texto, attachments=None, generated_images=None, generated_media=None, request_meta=None):
        attachments = attachments or []
        generated_images = generated_images or []
        generated_media = generated_media or []
        if tag == "system":
            lbl = ctk.CTkLabel(self.chat_scroll, text=repair_mojibake_text(texto), font=FONT_SMALL, text_color=COLORS["text_muted"], wraplength=900, justify="center")
            lbl.grid(row=self._bubble_row, column=0, padx=48, pady=(6, 4), sticky="ew")
            self._bubble_row += 1
            self._scroll_to_bottom()
            return

        bubble, body, _meta = self._create_bubble_shell(tag, autor, request_meta=request_meta)
        self._render_rich_text(body, texto)
        if attachments:
            self._render_attachment_cards(body, attachments)
        if generated_images:
            self._render_generated_images(body, generated_images)
        if generated_media:
            self._render_generated_media(body, generated_media)
        if tag == "hana" and texto.strip():
            self._add_hana_footer(bubble, texto)
        self._scroll_to_bottom()

    def _clean_inline_markdown(self, text):
        text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
        text = re.sub(r"\*(.*?)\*", r"\1", text)
        text = re.sub(r"__(.*?)__", r"\1", text)
        text = re.sub(r"_(.*?)_", r"\1", text)
        text = re.sub(r"`([^`]+)`", r"'\1'", text)
        return text.strip()

    def _render_heading(self, parent, level, text):
        size = {1: 22, 2: 18, 3: 15}.get(level, 14)
        ctk.CTkLabel(
            parent,
            text=self._clean_inline_markdown(text),
            font=ctk.CTkFont(family="Segoe UI", size=size, weight="bold"),
            text_color=COLORS["text_primary"],
            wraplength=640,
            justify="left",
            anchor="w",
        ).pack(fill="x", padx=14, pady=(8, 2))

    def _render_paragraph(self, parent, text):
        cleaned = self._clean_inline_markdown(text)
        if not cleaned:
            return
        ctk.CTkLabel(
            parent,
            text=cleaned,
            font=FONT_BODY,
            text_color=COLORS["text_primary"],
            wraplength=640,
            justify="left",
            anchor="w",
        ).pack(fill="x", padx=14, pady=(3, 1))

    def _render_list_item(self, parent, marker, text):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(2, 1))
        ctk.CTkLabel(row, text=marker, font=FONT_BODY, text_color=COLORS["purple_neon"], width=24, anchor="n").pack(side="left")
        ctk.CTkLabel(
            row,
            text=self._clean_inline_markdown(text),
            font=FONT_BODY,
            text_color=COLORS["text_primary"],
            wraplength=610,
            justify="left",
            anchor="w",
        ).pack(side="left", fill="x", expand=True)

    def _render_quote(self, parent, text):
        frame = ctk.CTkFrame(parent, fg_color="#16151F", corner_radius=12, border_width=2, border_color=COLORS["border"])
        frame.pack(fill="x", padx=14, pady=(4, 6))
        ctk.CTkLabel(
            frame,
            text=self._clean_inline_markdown(text),
            font=FONT_BODY,
            text_color=COLORS["text_secondary"],
            wraplength=620,
            justify="left",
            anchor="w",
        ).pack(fill="x", padx=10, pady=8)

    def _render_code_block(self, parent, language, code):
        code_box = ctk.CTkFrame(parent, fg_color="#141827", corner_radius=12, border_width=1, border_color=COLORS["border_subtle"])
        code_box.pack(fill="x", padx=14, pady=(4, 6))
        if language:
            ctk.CTkLabel(code_box, text=language.upper(), font=FONT_SMALL, text_color=COLORS["text_muted"]).pack(anchor="w", padx=8, pady=(6, 0))
        ctk.CTkLabel(
            code_box,
            text=code.strip(),
            font=("Consolas", 11),
            text_color="#E2E8F0",
            wraplength=620,
            justify="left",
            anchor="w",
        ).pack(fill="x", padx=8, pady=(4, 8))

    def _render_rich_text(self, parent, texto):
        display_text = repair_mojibake_text(self._sanitize_response_for_display(texto) or "(Processando internamente...)")
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
                self._render_list_item(parent, "-", bullet_match.group(1))
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
        container.pack(fill="x", padx=14, pady=(6, 8))
        for path in attachments:
            kind = self._infer_file_kind(path)
            if kind == "image":
                self._render_image_attachment(container, path, os.path.basename(path))
            else:
                self._render_file_card(container, path, kind)

    def _render_generated_images(self, parent, generated_images):
        container = ctk.CTkFrame(parent, fg_color="transparent")
        container.pack(fill="x", padx=14, pady=(6, 8))
        for path in generated_images:
            self._render_image_attachment(container, path, "Imagem gerada")

    def _normalize_generated_media_kind(self, kind, path):
        normalized = str(kind or "").strip().lower()
        if normalized == "music":
            return "audio"
        if normalized in {"audio", "video", "image", "pdf", "text", "file"}:
            return normalized
        return self._infer_file_kind(path)

    def _render_generated_media(self, parent, generated_media):
        container = ctk.CTkFrame(parent, fg_color="transparent")
        container.pack(fill="x", padx=14, pady=(6, 8))
        for item in generated_media:
            if isinstance(item, str):
                path = item
                title = None
                kind = self._normalize_generated_media_kind(None, path)
            else:
                path = item.get("path")
                title = item.get("title")
                kind = self._normalize_generated_media_kind(item.get("kind"), path)
            if not path:
                continue
            if kind == "image":
                self._render_image_attachment(container, path, title or "Imagem gerada")
            else:
                self._render_file_card(container, path, kind, title=title)

    def _render_image_attachment(self, parent, path, title):
        frame = ctk.CTkFrame(parent, fg_color=COLORS["bg_darkest"], corner_radius=12, border_width=2, border_color=COLORS["border"])
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

    def _render_file_card(self, parent, path, kind, title=None):
        card = ctk.CTkFrame(parent, fg_color=COLORS["bg_darkest"], corner_radius=10, border_width=2, border_color=COLORS["border"])
        card.pack(fill="x", pady=4)
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=(6, 2))
        ctk.CTkLabel(row, text=self._icon_for_kind(kind), font=FONT_SMALL, text_color=COLORS["purple_neon"]).pack(side="left")
        ctk.CTkLabel(row, text=title or os.path.basename(path), font=FONT_SMALL, text_color=COLORS["text_primary"]).pack(side="left", padx=(8, 0))
        ctk.CTkLabel(card, text=path, font=FONT_SMALL, text_color=COLORS["text_muted"], wraplength=620, justify="left").pack(anchor="w", padx=8, pady=(0, 4))
        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.pack(fill="x", padx=8, pady=(0, 8))
        ctk.CTkButton(actions, text="Abrir", width=68, height=24, fg_color=COLORS["purple_dim"], hover_color=COLORS["purple_neon"], font=FONT_SMALL, command=lambda p=path: self._open_file(p)).pack(side="left")
        if kind == "audio":
            ctk.CTkButton(actions, text="Tocar", width=68, height=24, fg_color=COLORS["bg_card_hover"], hover_color=COLORS["purple_dark"], font=FONT_SMALL, command=lambda p=path: self._tocar_audio_anexo(p)).pack(side="left", padx=(6, 0))

    def _media_kind_label(self, kind):
        return "musica"

    def _build_media_request_meta(self, status, fallback_meta=None):
        details = dict(status.get("details") or {})
        request_meta = dict(fallback_meta or {})
        request_meta["provider"] = request_meta.get("provider") or "google_cloud"
        request_meta["model"] = details.get("model") or request_meta.get("model") or "desconhecido"
        request_meta["backend"] = details.get("backend") or request_meta.get("backend")
        request_meta["routed"] = True
        return request_meta

    def _monitor_media_job(self, job_id, kind, fallback_meta=None):
        generator = self._get_music_gen()
        kind_label = self._media_kind_label(kind)
        completed_text = "concluida"
        ready_text = "gerada"
        state_text = {
            "queued": f"{kind_label.capitalize()} na fila...",
            "running": f"{kind_label.capitalize()} em geracao...",
        }
        last_state = None

        while True:
            status = generator.get_status(job_id)
            state = status.get("state")
            if state in {"queued", "running"}:
                if state != last_state:
                    self.after(
                        0,
                        lambda msg=state_text.get(state, f"{kind_label.capitalize()} em andamento."): self.lbl_chat_status.configure(
                            text=msg,
                            text_color=COLORS["yellow"],
                        ),
                    )
                last_state = state
                time.sleep(1.5)
                continue

            self._active_media_jobs.pop(job_id, None)
            if state == "completed":
                output_path = status.get("output_path")
                generated_media = [{
                    "path": output_path,
                    "kind": "audio",
                    "title": f"{kind_label.capitalize()} {ready_text}",
                }]
                result_meta = self._build_media_request_meta(status, fallback_meta)
                self.after(
                    0,
                    lambda: self._adicionar_msg(
                        "hana",
                        "Hana",
                        f"{kind_label.capitalize()} {ready_text} aqui no chat.",
                        generated_media=generated_media,
                        request_meta=result_meta,
                    ),
                )
                self.after(
                    0,
                    lambda: self.lbl_chat_status.configure(
                        text=f"{kind_label.capitalize()} {completed_text}.",
                        text_color=COLORS["green"],
                    ),
                )
                return

            if state == "cancelled":
                self.after(0, lambda: self._adicionar_msg("system", "Hana", f"Geracao de {kind_label} cancelada."))
                self.after(
                    0,
                    lambda: self.lbl_chat_status.configure(
                        text=f"Geração de {kind_label} cancelada.",
                        text_color=COLORS["yellow"],
                    ),
                )
                return

            error = status.get("error") or f"Falha ao gerar {kind_label}."
            self.after(0, lambda err=error: self._adicionar_msg("system", "Hana", f"Falha ao gerar {kind_label}: {err}"))
            self.after(
                0,
                lambda: self.lbl_chat_status.configure(
                    text=f"Falha na geracao de {kind_label}.",
                    text_color=COLORS["red"],
                ),
            )
            return

    def _queue_media_job(self, kind, prompt, request_meta=None):
        kind_label = self._media_kind_label(kind)
        if str(kind or "").strip().lower() != "music":
            self.after(0, lambda: self._adicionar_msg("system", "Hana", f"Geracao de {kind_label} foi desativada nesta versao."))
            return False

        generator = self._get_music_gen()
        try:
            job_id = generator.submit(prompt, origin="control_center_chat", request_meta=request_meta)
        except Exception as e:
            self.after(0, lambda err=e: self._adicionar_msg("system", "Hana", f"Falha ao iniciar geracao de {kind_label}: {err}"))
            self.after(
                0,
                lambda: self.lbl_chat_status.configure(
                    text=f"Falha ao iniciar {kind_label}.",
                    text_color=COLORS["red"],
                ),
            )
            return False

        self._active_media_jobs[job_id] = {"kind": kind}
        self.after(0, lambda: self._adicionar_msg("system", "Hana", f"{kind_label.capitalize()} em geracao em segundo plano. Quando terminar, eu te entrego aqui no chat."))
        self.after(
            0,
            lambda: self.lbl_chat_status.configure(
                text=f"Gerando {kind_label} em background...",
                text_color=COLORS["yellow"],
            ),
        )
        threading.Thread(
            target=self._monitor_media_job,
            args=(job_id, kind, request_meta),
            daemon=True,
            name=f"ChatMedia-{kind}-{job_id}",
        ).start()
        return True

    def _confirm_pc_action(self, request):
        decision = {"value": False}
        done = threading.Event()

        def _show():
            try:
                from src.gui.widgets.pc_action_popup import confirm_pc_action_popup

                decision["value"] = confirm_pc_action_popup(
                    title="Confirmar ação no PC",
                    body=request.summary,
                    risk_label=request.risk,
                    timeout_seconds=15,
                    parent=self.winfo_toplevel(),
                )
            finally:
                done.set()

        self.after(0, _show)
        done.wait()
        return bool(decision["value"])

    def _format_pc_action_result(self, result):
        base = result.get("message") or result.get("summary") or "Ação no PC concluída."
        content = str(result.get("content") or "").strip()
        stdout = str(result.get("stdout") or "").strip()
        stderr = str(result.get("stderr") or "").strip()

        extra_parts = []
        if content:
            extra_parts.append(content[:2500])
        if stdout:
            extra_parts.append(f"[stdout]\n{stdout[:1800]}")
        if stderr:
            extra_parts.append(f"[stderr]\n{stderr[:1200]}")
        if extra_parts:
            return f"{base}\n\n" + "\n\n".join(extra_parts)
        return base

    def _execute_pc_actions(self, action_payloads, request_id, cancel_event):
        for raw_payload in action_payloads or []:
            if self._is_request_cancelled(request_id, cancel_event):
                return
            try:
                request = parse_pc_action_payload(raw_payload)
            except Exception as e:
                self.after(0, lambda err=e: self._adicionar_msg("system", "PC", f"Falha ao interpretar <acao_pc>: {err}"))
                continue

            result = execute_pc_action(request.payload, confirm_callback=self._confirm_pc_action)
            message = self._format_pc_action_result(result)
            self.after(0, lambda msg=message: self._adicionar_msg("system", "PC", msg))
            if result.get("ok"):
                self.after(0, lambda: self.lbl_chat_status.configure(text="Ação no PC executada.", text_color=COLORS["green"]))
            else:
                self.after(0, lambda: self.lbl_chat_status.configure(text="Ação no PC negada ou falhou.", text_color=COLORS["yellow"]))

    def _scroll_to_bottom(self):
        self.chat_scroll.update_idletasks()
        self.chat_scroll._parent_canvas.yview_moveto(1.0)

    def _is_request_cancelled(self, request_id, cancel_event):
        return cancel_event.is_set() or self._active_request_id != request_id

    def _status_from_meta(self, request_meta):
        label = self._meta_label(request_meta)
        if not label:
            return "Resposta recebida."
        return f"Resposta recebida - {label}"

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
            divider = SentenceDivider(faster_first_response=True)
            streamed_visible_parts = []
            try:
                task_type = self._classify_task(texto, anexos_envio)
                execution_target = self._resolve_execution_target(task_type, anexos_envio)
                routed = bool(execution_target.get("routed"))

                if execution_target["provider"] == self.combo_chat_prov.get().strip().lower() and execution_target["model"] == self.combo_chat_modelo.get().strip():
                    llm = self._get_chat_llm()
                else:
                    llm = self._create_llm_instance(execution_target["provider"], execution_target["model"], cache=False)

                if not llm:
                    raise RuntimeError("Nao foi possivel inicializar o provider LLM.")

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
                self.after(0, lambda rid=request_id: self._create_streaming_bubble(rid))

                token_stream = llm.gerar_resposta_stream(
                    chat_history=self._session_history[-20:],
                    sistema_prompt=sistema_prompt,
                    user_message=mensagem_final,
                    image_b64=image_b64,
                    arquivos_multimidia=arquivos_multimidia if arquivos_multimidia else None,
                    request_context=request_context,
                )

                for chunk in divider.process_stream(token_stream):
                    request_meta = dict(getattr(llm, "last_request_meta", {}) or {})
                    request_meta["provider"] = execution_target["provider"]
                    request_meta["model"] = request_meta.get("model") or execution_target["model"]
                    request_meta["routed"] = routed

                    if self._is_request_cancelled(request_id, cancel_event):
                        return

                    if chunk.is_thought:
                        continue

                    if chunk.text.strip():
                        streamed_visible_parts.append(chunk.text.strip())
                        preview = " ".join(streamed_visible_parts).strip()
                        self.after(
                            0,
                            lambda rid=request_id, preview_text=preview, meta=dict(request_meta): self._update_streaming_bubble(
                                rid,
                                preview_text,
                                meta,
                            ),
                        )

                if self._is_request_cancelled(request_id, cancel_event):
                    return

                resposta = divider.complete_response or " ".join(streamed_visible_parts).strip() or "(sem resposta)"
                request_meta = dict(getattr(llm, "last_request_meta", {}) or {})
                request_meta["provider"] = execution_target["provider"]
                request_meta["model"] = request_meta.get("model") or execution_target["model"]
                request_meta["routed"] = routed

                actions = self._extract_xml_actions(resposta)
                generated_images = []
                queued_media = []
                for fact in actions.get("salvar_memoria", []):
                    try:
                        memory_manager.add_fact("hana_nota", "deve_lembrar", fact)
                    except Exception as e:
                        logger.warning("[CHAT GUI] Falha ao salvar memoria manual: %s", e)

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

                for prompt in actions.get("gerar_musica", []):
                    if self._is_request_cancelled(request_id, cancel_event):
                        return
                    if self._queue_media_job("music", prompt, request_meta=request_meta):
                        queued_media.append("music")

                resp_display = self._sanitize_response_for_display(resposta)
                if not resp_display and generated_images:
                    resp_display = "Imagem gerada aqui no chat."
                elif not resp_display and queued_media:
                    resp_display = "Pedido de midia recebido. Vou gerar e te entregar aqui no chat assim que terminar."
                elif not resp_display:
                    resp_display = "(sem resposta visivel)"

                if self._is_request_cancelled(request_id, cancel_event):
                    return

                self._ultima_resposta = resposta
                history_content = resp_display
                self._session_history.append({"role": "Nakamura", "content": texto})
                self._session_history.append({"role": "Hana", "content": history_content})
                memory_manager.add_interaction("Nakamura", texto)
                memory_manager.add_interaction("Hana", history_content)

                self.after(
                    0,
                    lambda rid=request_id, display_text=resp_display, imgs=list(generated_images), meta=dict(request_meta): self._finalize_streaming_bubble(
                        rid,
                        display_text,
                        generated_images=imgs,
                        request_meta=meta,
                    ),
                )
                self.after(0, lambda meta=dict(request_meta): self.lbl_chat_status.configure(text=self._status_from_meta(meta), text_color=COLORS["green"]))
                self._execute_pc_actions(actions.get("acao_pc", []), request_id, cancel_event)
            except Exception as e:
                logger.error("[CHAT GUI] Erro: %s", e)
                if not self._is_request_cancelled(request_id, cancel_event):
                    self.after(0, lambda rid=request_id: self._cancel_streaming_bubble(rid))
                    self.after(0, lambda err=e: self._adicionar_msg("system", "ERRO", repair_mojibake_text(f"Erro no chat da GUI: {err}")))
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
            self._add_attachment_paths(filepaths)

    def _atualizar_container_anexos(self):
        for child in self.frame_anexo_list.winfo_children():
            child.destroy()
        if not self._anexos:
            self.frame_anexo.grid_forget()
            return
        self.lbl_anexo.configure(text=f"{len(self._anexos)} arquivo(s) prontos para envio")
        for path in self._anexos:
            kind = self._infer_file_kind(path)
            card = ctk.CTkFrame(self.frame_anexo_list, fg_color=COLORS["bg_darkest"], corner_radius=10, border_width=2, border_color=COLORS["border"])
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
        self._adicionar_msg("system", "Hana", "Gravando audio... aguarde.")

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
            pygame.mixer.music.stop()
            pygame.mixer.music.load(path)
            pygame.mixer.music.play()
            self._audio_preview_path = path
        except Exception as e:
            logger.error("[CHAT GUI] Erro ao tocar audio %s: %s", path, e)
            self.lbl_chat_status.configure(text=repair_mojibake_text(f"Falha ao tocar audio: {e}"), text_color=COLORS["red"])

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

        self._active_tts_thread = threading.Thread(target=_run, daemon=True)
        self._active_tts_thread.start()

    def _parar_fala(self):
        request_global_stop("chat_button")

    def _parar_fala_local(self):
        cancelled_request = False
        if self._active_cancel_event:
            self._active_cancel_event.set()
            cancelled_request = True
        request_id = self._active_request_id
        if request_id is not None:
            self._active_request_id = None
            self._cancel_streaming_bubble(request_id)
        if cancelled_request:
            self.lbl_chat_status.configure(text="Geracao cancelada pelo usuario.", text_color=COLORS["yellow"])

        cancelled_media_jobs = 0
        for job_id, meta in list(self._active_media_jobs.items()):
            generator = self._get_music_gen()
            try:
                if generator.cancel(job_id):
                    cancelled_media_jobs += 1
            except Exception as e:
                logger.warning("[CHAT GUI] Falha ao cancelar job %s: %s", job_id, e)

        if cancelled_media_jobs:
            self.lbl_chat_status.configure(
                text=f"Cancelando {cancelled_media_jobs} job(s) de midia...",
                text_color=COLORS["yellow"],
            )

        try:
            import pygame

            if pygame.mixer.get_init():
                pygame.mixer.stop()
                self._audio_preview_path = None
        except Exception:
            pass

        try:
            from src.modules.voice.tts_selector import get_tts

            get_tts().parar()
        except Exception:
            logger.debug("[CHAT GUI] Falha ao parar TTS ativo.", exc_info=True)
