"""
Tab Perfil — Foto da Nyra e customização visual.
"""

import customtkinter as ctk
from PIL import Image

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from src.gui.design import COLORS, FONT_TITLE, FONT_BODY, FONT_SMALL, FONT_MONO, FONT_HEADER

REF_IMAGE_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "persona", "nyra_refs", "ref_01.jpg")


class TabPerfil(ctk.CTkFrame):
    """Perfil da Nyra — foto, identidade e cores."""

    def __init__(self, master, runtime=None):
        super().__init__(master, corner_radius=12, fg_color=COLORS["bg_dark"], border_width=2, border_color=COLORS["border_strong"])
        self.runtime = runtime
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # ─── HEADER ───
        header = ctk.CTkLabel(self, text="Perfil da Nyra", font=FONT_TITLE, text_color=COLORS["text_primary"])
        header.grid(row=0, column=0, columnspan=2, padx=25, pady=(20, 5), sticky="w")
        sub = ctk.CTkLabel(self, text="Identidade visual e personalidade", font=FONT_SMALL, text_color=COLORS["text_muted"])
        sub.grid(row=1, column=0, columnspan=2, padx=25, pady=(0, 20), sticky="w")

        # ═══ COLUNA ESQUERDA: Foto ═══
        card_foto = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=12, border_width=2, border_color=COLORS["border"])
        card_foto.grid(row=2, column=0, padx=(15, 8), pady=8, sticky="nsew")
        self.grid_rowconfigure(2, weight=1)

        # Tenta carregar a imagem de referência
        try:
            path = os.path.abspath(REF_IMAGE_PATH)
            if os.path.exists(path):
                pil_img = Image.open(path)
                # Redimensiona para caber no card
                img_ctk = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(320, 320))
                lbl_img = ctk.CTkLabel(card_foto, image=img_ctk, text="")
                lbl_img.pack(padx=20, pady=20)
            else:
                lbl_img = ctk.CTkLabel(card_foto, text="📷\n\nImagem não encontrada\nref_01.jpg", font=FONT_BODY, text_color=COLORS["text_muted"])
                lbl_img.pack(padx=20, pady=60)
        except Exception as e:
            lbl_img = ctk.CTkLabel(card_foto, text=f"Erro ao carregar imagem:\n{e}", font=FONT_SMALL, text_color=COLORS["red"])
            lbl_img.pack(padx=20, pady=60)

        # Nome embaixo da foto
        nome_frame = ctk.CTkFrame(card_foto, fg_color="transparent")
        nome_frame.pack(pady=(0, 15))

        ctk.CTkLabel(nome_frame, text="N Y R A", font=FONT_HEADER, text_color=COLORS["purple_neon"]).pack()
        ctk.CTkLabel(nome_frame, text="IA Assistente Autônoma  •  v2.0", font=FONT_SMALL, text_color=COLORS["text_muted"]).pack()

        # ═══ COLUNA DIREITA: Info + Cores ═══
        card_info = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=12, border_width=2, border_color=COLORS["border"])
        card_info.grid(row=2, column=1, padx=(8, 15), pady=8, sticky="nsew")

        ctk.CTkLabel(card_info, text="📋  Identidade", font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), text_color=COLORS["text_primary"]).pack(anchor="w", padx=15, pady=(15, 10))

        # Info cards
        infos = [
            ("Nome", "Nyra"),
            ("Função", "Assistente IA Autônoma"),
            ("Criador", "Nakamura (Mestre)"),
            ("LLM Base", "Gemini 2.5 Flash"),
            ("Memória", "GraphRAG V2 Híbrido"),
            ("TTS", "Google Cloud"),
            ("Visão", "Modo 2 (Sob Demanda)"),
            ("Personalidade", "Tsundere Gamer"),
        ]

        for label, valor in infos:
            row = ctk.CTkFrame(card_info, fg_color=COLORS["bg_darkest"], corner_radius=6)
            row.pack(fill="x", padx=12, pady=2)

            ctk.CTkLabel(row, text=f"  {label}:", font=FONT_SMALL, text_color=COLORS["text_muted"], width=120, anchor="w").pack(side="left", padx=(8, 0), pady=6)
            ctk.CTkLabel(row, text=valor, font=ctk.CTkFont(family="Consolas", size=12), text_color=COLORS["purple_neon"], anchor="w").pack(side="left", padx=5, pady=6, fill="x", expand=True)

        # Seção de Cores (futura customização)
        ctk.CTkLabel(card_info, text="🎨  Tema Visual", font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), text_color=COLORS["text_primary"]).pack(anchor="w", padx=15, pady=(20, 8))

        cores_frame = ctk.CTkFrame(card_info, fg_color="transparent")
        cores_frame.pack(fill="x", padx=12, pady=(0, 15))

        cores = [
            ("Roxo Neon", COLORS["purple_neon"]),
            ("Azul Neon", COLORS["blue_neon"]),
            ("Verde", COLORS["green"]),
            ("Fundo", COLORS["bg_darkest"]),
        ]

        for nome, cor in cores:
            cf = ctk.CTkFrame(cores_frame, fg_color="transparent")
            cf.pack(side="left", padx=10)
            swatch = ctk.CTkLabel(cf, text="", width=30, height=30, fg_color=cor, corner_radius=6)
            swatch.pack()
            ctk.CTkLabel(cf, text=nome, font=FONT_SMALL, text_color=COLORS["text_muted"]).pack(pady=(3, 0))
