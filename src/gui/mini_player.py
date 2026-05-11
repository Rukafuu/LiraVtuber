"""
Lira Mini Player — Overlay flutuante e compacto.
Design: Circular, sem bordas, arrastável e com legendas dinâmicas.
"""

import os
import tkinter as tk
import customtkinter as ctk
from PIL import Image, ImageTk

# Cores e design
ACCENT_COLOR = "#f472b6"
BG_COLOR = "#1a1a1a"

class LiraMiniPlayer(ctk.CTkToplevel):
    def __init__(self, master=None):
        super().__init__(master)
        
        # Configurações da janela
        self.title("Lira Mini")
        self.geometry("220x220+100+100")
        self.overrideredirect(True) # Remove bordas
        self.attributes("-topmost", True) # Sempre no topo
        self.configure(fg_color="black") # Cor de fundo para transparência
        self.wm_attributes("-transparentcolor", "black") # Transparência real no Windows
        
        # Frame Principal Circular (simulado com corner_radius alto)
        self.main_frame = ctk.CTkFrame(
            self, width=200, height=200, 
            corner_radius=100, 
            fg_color=BG_COLOR,
            border_width=2,
            border_color=ACCENT_COLOR
        )
        self.main_frame.place(relx=0.5, rely=0.5, anchor="center")
        
        # Foto da Lira
        self._load_avatar()
        
        # Label de Legenda (escondida por padrão)
        self.sub_frame = ctk.CTkFrame(self, fg_color="#000000", corner_radius=10)
        self.caption_label = ctk.CTkLabel(
            self.sub_frame, text="", 
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="white",
            wraplength=180
        )
        self.caption_label.pack(padx=10, pady=5)
        
        # Eventos para arrastar
        self.main_frame.bind("<ButtonPress-1>", self._start_move)
        self.main_frame.bind("<B1-Motion>", self._do_move)
        self.avatar_label.bind("<ButtonPress-1>", self._start_move)
        self.avatar_label.bind("<B1-Motion>", self._do_move)

        self._x = 0
        self._y = 0

    def _load_avatar(self):
        photo_path = r"C:\Users\conta\OneDrive\Imagens\Lira\lira icon new.png"
        try:
            if os.path.exists(photo_path):
                pil_img = Image.open(photo_path).resize((160, 160), Image.LANCZOS)
                self.avatar_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(160, 160))
                self.avatar_label = ctk.CTkLabel(self.main_frame, image=self.avatar_img, text="")
            else:
                self.avatar_label = ctk.CTkLabel(self.main_frame, text="✦", font=("Consolas", 48), text_color=ACCENT_COLOR)
        except:
            self.avatar_label = ctk.CTkLabel(self.main_frame, text="L", font=("Consolas", 48), text_color=ACCENT_COLOR)
        
        self.avatar_label.place(relx=0.5, rely=0.5, anchor="center")

    def show_caption(self, text):
        """Exibe uma legenda flutuante abaixo do mini player."""
        if not text:
            self.sub_frame.place_forget()
            return
            
        self.caption_label.configure(text=text)
        self.sub_frame.place(relx=0.5, rely=0.95, anchor="n")
        
        # Auto-ocultar após 5 segundos
        self.after(5000, lambda: self.sub_frame.place_forget())

    def _start_move(self, event):
        self._x = event.x
        self._y = event.y

    def _do_move(self, event):
        deltax = event.x - self._x
        deltay = event.y - self._y
        x = self.winfo_x() + deltax
        y = self.winfo_y() + deltay
        self.geometry(f"+{x}+{y}")

if __name__ == "__main__":
    app = ctk.CTk()
    app.withdraw() # Esconde a janela principal do tk
    mini = LiraMiniPlayer()
    mini.mainloop()
