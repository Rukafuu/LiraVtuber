import os
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# Cores da Lira (Purple/Pink Neon)
COLOR_BG = (18, 18, 18)
COLOR_ACCENT = (244, 114, 182) # Pink
COLOR_TEXT = (255, 255, 255)
COLOR_BAR_BG = (40, 40, 40)

def generate_profile_card(username, level, xp, needed_xp, rank="#1", avatar_url=None, banner_path=None):
    # Dimensões do Card (Estilo Discord/Moderno)
    W, H = 800, 250
    card = Image.new("RGBA", (W, H), COLOR_BG)
    draw = ImageDraw.Draw(card)

    # 1. Banner (Fundo)
    if banner_path and os.path.exists(banner_path):
        banner = Image.open(banner_path).convert("RGBA")
        banner = banner.resize((W, H))
        banner = banner.filter(ImageFilter.GaussianBlur(5)) # Blur para legibilidade
        card.paste(banner, (0, 0), banner)
        # Overlay escuro para o texto ler bem
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 150))
        card.paste(overlay, (0, 0), overlay)

    # 2. Avatar
    avatar_size = 160
    avatar_pos = (40, 45)
    
    # Placeholder de avatar
    avatar = Image.new("RGBA", (avatar_size, avatar_size), COLOR_ACCENT)
    
    if avatar_url:
        try:
            response = requests.get(avatar_url, timeout=5)
            img_data = BytesIO(response.content)
            avatar = Image.open(img_data).convert("RGBA")
            avatar = avatar.resize((avatar_size, avatar_size))
        except:
            pass

    # Máscara circular para o avatar
    mask = Image.new("L", (avatar_size, avatar_size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse((0, 0, avatar_size, avatar_size), fill=255)
    
    card.paste(avatar, avatar_pos, mask)
    
    # Borda do avatar
    draw.ellipse([avatar_pos[0]-5, avatar_pos[1]-5, avatar_pos[0]+avatar_size+5, avatar_pos[1]+avatar_size+5], outline=COLOR_ACCENT, width=5)

    # 3. Textos (Fontes)
    # Tenta carregar fontes do sistema ou usa padrão
    try:
        font_name = ImageFont.truetype("arial.ttf", 45)
        font_stats = ImageFont.truetype("arial.ttf", 30)
        font_rank = ImageFont.truetype("arial.ttf", 35)
    except:
        font_name = ImageFont.load_default()
        font_stats = ImageFont.load_default()
        font_rank = ImageFont.load_default()

    # Nome do Usuário
    draw.text((230, 60), username, font=font_name, fill=COLOR_TEXT)
    
    # Rank e Nível
    draw.text((W - 180, 60), f"LEVEL {level}", font=font_rank, fill=COLOR_ACCENT)
    draw.text((W - 120, 110), rank, font=font_stats, fill=(150, 150, 150))

    # 4. Barra de Progresso XP
    bar_x, bar_y = 230, 160
    bar_w, bar_h = 530, 40
    
    # Fundo da barra
    draw.rounded_rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], radius=20, fill=COLOR_BAR_BG)
    
    # Progresso (calculado)
    progress_ratio = xp / needed_xp if needed_xp > 0 else 1
    progress_w = int(bar_w * progress_ratio)
    if progress_w > 0:
        draw.rounded_rectangle([bar_x, bar_y, bar_x + progress_w, bar_y + bar_h], radius=20, fill=COLOR_ACCENT)

    # Texto do XP
    draw.text((bar_x + 10, bar_y + bar_h + 5), f"{xp} / {needed_xp} XP", font=font_stats, fill=(200, 200, 200))

    # Salva temporário
    output_path = "data/last_profile.png"
    card.save(output_path)
    return output_path
