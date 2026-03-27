"""
Hana Control Center — Painel Premium (CustomTkinter).

Janela principal com sidebar de navegação e 8 abas dinâmicas.
Design: Dark Mode com acento customizável, transparência via pywinstyles.

Uso standalone:
    python -m src.gui.hana_gui

Uso integrado:
    from src.gui.hana_gui import HanaControlCenter
    gui = HanaControlCenter()
    gui.mainloop()
"""

import os
import sys
import logging
import customtkinter as ctk #  biblioteka
from PIL import Image

logger = logging.getLogger(__name__)

# Garante imports relativos do projeto
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.config.config_loader import CONFIG
from src.gui.design import COLORS, FONT_SMALL, reload_colors

# Caminho da foto de perfil da Hana
PROFILE_PHOTO_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "image", "hana_perfil.png")

# =====================================================
# JANELA PRINCIPAL
# =====================================================

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")


class HanaControlCenter(ctk.CTk):
    """Painel de Controle Premium da Hana."""

    def __init__(self):
        super().__init__()

        # Carrega cor de acento do config
        gui_config = CONFIG.get("GUI", {})
        accent = gui_config.get("accent_color", "#f472b6") if isinstance(gui_config, dict) else "#f472b6"
        reload_colors(accent)

        # --- Janela ---
        self.title("HANA OS — Control Center")
        self.geometry("1200x750")
        self.minsize(950, 650)
        self.configure(fg_color=COLORS["bg_darkest"])

        # --- Transparência via pywinstyles ---
        self._apply_transparency(gui_config)

        # Grid: sidebar (col 0) + conteúdo (col 1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # =============================================
        # SIDEBAR — Navegação
        # =============================================
        self.sidebar = ctk.CTkFrame(
            self, width=220, corner_radius=0,
            fg_color=COLORS["bg_sidebar"],
            border_width=0
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(12, weight=1)
        self.sidebar.grid_propagate(False)

        # ── Foto de Perfil da Hana ──
        try:
            photo_path = os.path.abspath(PROFILE_PHOTO_PATH)
            if os.path.exists(photo_path):
                pil_img = Image.open(photo_path)
                self._profile_img = ctk.CTkImage(
                    light_image=pil_img, dark_image=pil_img,
                    size=(65, 65)
                )
                self.logo_img = ctk.CTkLabel(
                    self.sidebar, image=self._profile_img, text="",
                    fg_color=COLORS["bg_darkest"], corner_radius=32,
                    width=70, height=70
                )
                self.logo_img.grid(row=0, column=0, padx=20, pady=(20, 3))
            else:
                raise FileNotFoundError("Foto não encontrada")
        except Exception:
            self.logo_img = ctk.CTkLabel(
                self.sidebar, text="✦",
                font=("Consolas", 36, "bold"),
                text_color=COLORS["purple_neon"]
            )
            self.logo_img.grid(row=0, column=0, padx=20, pady=(20, 3))

        # Nome da Hana abaixo da foto
        self.logo_name = ctk.CTkLabel(
            self.sidebar, text="HANA OS",
            font=ctk.CTkFont(family="Consolas", size=18, weight="bold"),
            text_color=COLORS["purple_neon"]
        )
        self.logo_name.grid(row=1, column=0, padx=20, pady=(2, 0))

        # Subtítulo versão
        self.version_label = ctk.CTkLabel(
            self.sidebar, text="Control Center  v1.0",
            font=FONT_SMALL,
            text_color=COLORS["text_muted"]
        )
        self.version_label.grid(row=2, column=0, padx=20, pady=(0, 15))

        # Separador visual
        sep = ctk.CTkFrame(self.sidebar, height=1, fg_color=COLORS["border"])
        sep.grid(row=3, column=0, sticky="ew", padx=15, pady=(0, 8))

        # Botões de navegação (8 abas)
        self._menu_btns = []
        menus = [
            ("🖥  Monitor Geral",     4,  "geral"),
            ("🧠  Cérebro",           5,  "llm"),
            ("💾  Memória",           6,  "memoria"),
            ("💬  Terminal Chat",     7,  "chat"),
            ("📝  Persona",          8,  "persona"),
            ("⚙  Prompts",           9,  "prompts"),
            ("🔌  Conexões",         10, "conexoes"),
            ("🎨  Personalização",   11, "personalizacao"),
            ("📋  Logs",             12, "logs"),
        ]
        for texto, row, key in menus:
            btn = ctk.CTkButton(
                self.sidebar, text=texto,
                command=lambda k=key: self._mostrar_frame(k),
                fg_color="transparent",
                text_color=COLORS["text_secondary"],
                hover_color=COLORS["purple_dark"],
                anchor="w", height=40,
                font=ctk.CTkFont(family="Segoe UI", size=14),
                corner_radius=8,
            )
            btn.grid(row=row, column=0, padx=12, pady=3, sticky="ew")
            self._menu_btns.append((key, btn))

        # Status na base da sidebar
        self._status_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self._status_frame.grid(row=13, column=0, padx=15, pady=(5, 15), sticky="sew")

        self._status_dot = ctk.CTkLabel(
            self._status_frame, text="●",
            font=("Segoe UI", 14),
            text_color=COLORS["green"]
        )
        self._status_dot.pack(side="left", padx=(5, 5))

        self._status_text = ctk.CTkLabel(
            self._status_frame, text="ONLINE  •  Standalone",
            font=FONT_SMALL,
            text_color=COLORS["text_muted"]
        )
        self._status_text.pack(side="left")

        # =============================================
        # FRAMES DAS ABAS
        # =============================================
        self.frames = {}
        self._active_frame = None

        from src.gui.frames.tab_geral import TabGeral
        from src.gui.frames.tab_llm import TabLLM
        from src.gui.frames.tab_memoria import TabMemoria
        from src.gui.frames.tab_chat import TabChat
        from src.gui.frames.tab_persona import TabPersona
        from src.gui.frames.tab_prompts import TabPrompts
        from src.gui.frames.tab_conexoes import TabConexoes
        from src.gui.frames.tab_personalizacao import TabPersonalizacao
        from src.gui.frames.tab_logs import TabLogs

        tab_classes = {
            "geral":          TabGeral,
            "llm":            TabLLM,
            "memoria":        TabMemoria,
            "chat":           TabChat,
            "persona":        TabPersona,
            "prompts":        TabPrompts,
            "conexoes":       TabConexoes,
            "personalizacao": TabPersonalizacao,
            "logs":           TabLogs,
        }

        for key, cls in tab_classes.items():
            frame = cls(self)
            self.frames[key] = frame

        # Inicia na aba Geral
        self._mostrar_frame("geral")

        # Hot-reload do config.json (a cada 2s)
        self._settings_path = os.path.abspath(CONFIG.config_path)
        self._last_mtime = os.path.getmtime(self._settings_path) if os.path.exists(self._settings_path) else 0
        self.after(2000, self._check_settings_changes)

    # =========================================================
    # TRANSPARÊNCIA
    # =========================================================

    def _apply_transparency(self, gui_config):
        """Aplica estilo visual via pywinstyles (dark titlebar)."""
        try:
            import pywinstyles
            # Usa 'dark' para barra de título escura (não usa 'acrylic' pois causa
            # efeito esbranquiçado ao perder foco, e '-alpha' torna TUDO transparente)
            pywinstyles.apply_style(self, "dark")
            logger.info("[GUI] Estilo dark aplicado via pywinstyles.")
        except ImportError:
            logger.warning("[GUI] pywinstyles não instalado — sem estilo.")
        except Exception as e:
            logger.warning(f"[GUI] Erro ao aplicar estilo: {e}")

    # =========================================================
    # NAVEGAÇÃO
    # =========================================================

    def _mostrar_frame(self, key: str):
        """Troca o frame ativo da área de conteúdo."""
        if self._active_frame and self._active_frame in self.frames:
            self.frames[self._active_frame].grid_forget()

        self.frames[key].grid(row=0, column=1, padx=(0, 12), pady=12, sticky="nsew")
        self._active_frame = key

        for btn_key, btn in self._menu_btns:
            if btn_key == key:
                btn.configure(
                    fg_color=COLORS["purple_dark"],
                    text_color=COLORS["purple_neon"]
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=COLORS["text_secondary"]
                )

    # =========================================================
    # HOT-RELOAD DO CONFIG.JSON
    # =========================================================

    def _check_settings_changes(self):
        """Verifica se o config.json foi alterado externamente."""
        if os.path.exists(self._settings_path):
            try:
                current_mtime = os.path.getmtime(self._settings_path)
                if current_mtime > self._last_mtime:
                    self._last_mtime = current_mtime
                    CONFIG.reload()

                    # Atualiza a Tab LLM se tiver método de recarga
                    if "llm" in self.frames and hasattr(self.frames["llm"], "_carregar_settings"):
                        self.frames["llm"]._carregar_settings()
            except Exception:
                pass

        self.after(2000, self._check_settings_changes)

    # =========================================================
    # MÉTODOS PÚBLICOS (usados pelas tabs)
    # =========================================================

    def refresh_accent(self, accent_hex: str, opacity: float = None):
        """Chamado pela TabPersonalizacao para atualizar as cores em tempo real."""
        reload_colors(accent_hex)

        # Atualiza sidebar
        self.logo_name.configure(text_color=COLORS["purple_neon"])
        for _, btn in self._menu_btns:
            btn.configure(hover_color=COLORS["purple_dark"])
        if self._active_frame:
            self._mostrar_frame(self._active_frame)  # Re-aplica highlight

        # Atualiza opacidade
        if opacity is not None:
            try:
                self.attributes("-alpha", opacity)
            except Exception:
                pass


# =====================================================
# STANDALONE ENTRY POINT
# =====================================================

def main():
    """Abre o painel em modo standalone."""
    app = HanaControlCenter()
    app.mainloop()


if __name__ == "__main__":
    main()
