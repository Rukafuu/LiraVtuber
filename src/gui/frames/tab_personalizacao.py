"""
Tab Personalização — Cores, opacidade e tema visual da Hana Control Center.
Mudanças são aplicadas em tempo real e salvas no config.json.
"""

import customtkinter as ctk
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from src.gui.design import COLORS, FONT_TITLE, FONT_BODY, FONT_SMALL, FONT_MONO, reload_colors
from src.config.config_loader import CONFIG

try:
    from PIL import Image as PILImage
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

HANA_PHOTO_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "image", "hana_foto_01.png")

# Paleta de cores pré-definidas
PRESET_COLORS = [
    ("🌸 Rosa Floral",     "#f472b6"),
    ("💜 Roxo Neon",       "#a855f7"),
    ("💙 Azul Cyberpunk",  "#3b82f6"),
    ("💚 Verde Matrix",    "#4ade80"),
    ("🧡 Laranja Sunset",  "#fb923c"),
    ("❤️ Vermelho Rubi",   "#f43f5e"),
    ("✨ Dourado",          "#fbbf24"),
    ("🩵 Ciano",           "#22d3ee"),
]


class TabPersonalizacao(ctk.CTkFrame):
    """Personalização — cores, opacidade e tema visual."""

    def __init__(self, master, **kwargs):
        super().__init__(master, corner_radius=12, fg_color=COLORS["bg_dark"], border_width=1, border_color=COLORS["border"])
        self.master_window = master
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # ─── HEADER ───
        header = ctk.CTkLabel(self, text="🎨  Personalização", font=FONT_TITLE, text_color=COLORS["text_primary"])
        header.grid(row=0, column=0, columnspan=2, padx=25, pady=(20, 2), sticky="w")
        sub = ctk.CTkLabel(self, text="Altere as cores de acento da interface", font=FONT_SMALL, text_color=COLORS["text_muted"])
        sub.grid(row=1, column=0, columnspan=2, padx=25, pady=(0, 15), sticky="w")

        # ═══ COLUNA ESQUERDA: Cores ═══
        card_cores = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=10, border_width=1, border_color=COLORS["border"])
        card_cores.grid(row=2, column=0, padx=(15, 8), pady=8, sticky="nsew")
        self.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(card_cores, text="🎨  Cor de Acento", font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), text_color=COLORS["text_primary"]).pack(anchor="w", padx=15, pady=(15, 10))

        # Botões de cores pré-definidas
        colors_grid = ctk.CTkFrame(card_cores, fg_color="transparent")
        colors_grid.pack(fill="x", padx=15, pady=(0, 10))

        self._cor_selecionada = None
        gui_cfg = CONFIG.get("GUI", {})
        current_accent = gui_cfg.get("accent_color", "#f472b6") if isinstance(gui_cfg, dict) else "#f472b6"

        for i, (nome, hex_cor) in enumerate(PRESET_COLORS):
            col = i % 4
            row = i // 4

            btn = ctk.CTkButton(
                colors_grid, text="", width=50, height=50,
                fg_color=hex_cor, hover_color=hex_cor,
                corner_radius=25,
                border_width=3,
                border_color=COLORS["bg_darkest"] if hex_cor != current_accent else "#ffffff",
                command=lambda c=hex_cor: self._selecionar_cor(c)
            )
            btn.grid(row=row, column=col, padx=8, pady=8)
            colors_grid.grid_columnconfigure(col, weight=1)

        # Campo hex customizado
        hex_frame = ctk.CTkFrame(card_cores, fg_color="transparent")
        hex_frame.pack(fill="x", padx=15, pady=(5, 10))

        ctk.CTkLabel(hex_frame, text="Cor customizada:", font=FONT_SMALL, text_color=COLORS["text_muted"]).pack(side="left", padx=(0, 8))

        self.entry_hex = ctk.CTkEntry(
            hex_frame, placeholder_text="#f472b6", width=120,
            fg_color=COLORS["bg_darkest"], border_color=COLORS["border"],
            text_color=COLORS["text_primary"], font=FONT_MONO
        )
        self.entry_hex.pack(side="left", padx=(0, 8))
        self.entry_hex.insert(0, current_accent)

        btn_custom = ctk.CTkButton(
            hex_frame, text="Aplicar", width=80,
            fg_color=COLORS["purple_dim"], hover_color=COLORS["purple_neon"],
            command=lambda: self._selecionar_cor(self.entry_hex.get().strip())
        )
        btn_custom.pack(side="left")

        # ── Info ──
        info_frame = ctk.CTkFrame(card_cores, fg_color=COLORS["bg_darkest"], corner_radius=8)
        info_frame.pack(fill="x", padx=15, pady=(10, 10))
        ctk.CTkLabel(info_frame, text="💡  A cor de acento muda botões, links e destaques da interface.", font=FONT_SMALL, text_color=COLORS["text_muted"], wraplength=350).pack(padx=10, pady=8)

        # ── Preview da cor ──
        self.preview_frame = ctk.CTkFrame(card_cores, fg_color=current_accent, corner_radius=10, height=40)
        self.preview_frame.pack(fill="x", padx=15, pady=(5, 10))
        self.preview_label = ctk.CTkLabel(self.preview_frame, text=f"Preview: {current_accent}", font=FONT_MONO, text_color="#000000")
        self.preview_label.pack(pady=8)

        # ── Botão Salvar ──
        self.btn_salvar = ctk.CTkButton(
            card_cores, text="💾  Salvar & Aplicar", width=200, height=36,
            fg_color=COLORS["purple_dim"], hover_color=COLORS["purple_neon"],
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            command=self._salvar
        )
        self.btn_salvar.pack(pady=(5, 10))

        self.lbl_status = ctk.CTkLabel(card_cores, text="", font=FONT_SMALL, text_color=COLORS["green"])
        self.lbl_status.pack(pady=(0, 10))

        # ═══ COLUNA DIREITA: Foto da Hana ═══
        card_foto = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=10, border_width=1, border_color=COLORS["border"])
        card_foto.grid(row=2, column=1, padx=(8, 15), pady=8, sticky="nsew")

        try:
            path = os.path.abspath(HANA_PHOTO_PATH)
            if os.path.exists(path) and HAS_PIL:
                pil_img = PILImage.open(path)
                img_ctk = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(320, 400))
                lbl_img = ctk.CTkLabel(card_foto, image=img_ctk, text="")
                lbl_img.pack(padx=20, pady=20)
            else:
                lbl_img = ctk.CTkLabel(card_foto, text="🌸\n\nHana Nakamura", font=FONT_TITLE, text_color=COLORS["text_muted"])
                lbl_img.pack(padx=20, pady=60)
        except Exception:
            lbl_img = ctk.CTkLabel(card_foto, text="🌸\n\nHana Nakamura", font=FONT_TITLE, text_color=COLORS["text_muted"])
            lbl_img.pack(padx=20, pady=60)

        ctk.CTkLabel(card_foto, text="H A N A", font=("Consolas", 24, "bold"), text_color=COLORS["purple_neon"]).pack(pady=(0, 5))
        ctk.CTkLabel(card_foto, text="Drowsy Onee-san  •  v1.0", font=FONT_SMALL, text_color=COLORS["text_muted"]).pack(pady=(0, 15))

    def _selecionar_cor(self, hex_cor: str):
        """Seleciona uma cor de acento e atualiza o preview."""
        if not hex_cor.startswith("#") or len(hex_cor) not in (4, 7):
            return

        self._cor_selecionada = hex_cor
        self.entry_hex.delete(0, "end")
        self.entry_hex.insert(0, hex_cor)
        self.preview_frame.configure(fg_color=hex_cor)
        self.preview_label.configure(text=f"Preview: {hex_cor}")

        # Aplica em tempo real
        reload_colors(hex_cor)
        if hasattr(self.master_window, "refresh_accent"):
            self.master_window.refresh_accent(hex_cor)

    def _salvar(self):
        """Salva cor de acento no config.json."""
        hex_cor = self.entry_hex.get().strip() or "#f472b6"

        gui_cfg = CONFIG.get("GUI", {})
        if not isinstance(gui_cfg, dict):
            gui_cfg = {}
        gui_cfg["accent_color"] = hex_cor
        CONFIG["GUI"] = gui_cfg

        try:
            CONFIG.save()
            self.lbl_status.configure(text=f"✓ Tema salvo! ({hex_cor})", text_color=COLORS["green"])
        except Exception as e:
            self.lbl_status.configure(text=f"Erro: {e}", text_color=COLORS["red"])
