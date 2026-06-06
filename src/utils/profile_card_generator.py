import io
import os
import re
import logging
import aiohttp
import json
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

CUSTOMS_FILE = "data/profile_customs.json"

# Cores Temáticas Disponíveis
THEME_COLORS = {
    "pink":   (255, 105, 180, 255),
    "purple": (155,  89, 182, 255),
    "blue":   ( 52, 152, 219, 255),
    "green":  ( 46, 204, 113, 255),
}

# ─── Dimensões fixas do card ──────────────────────────────────────────────────
W, H       = 800, 280          # Largura e altura do card
PAD        = 24                # Padding interno geral
AVA_SIZE   = 160               # Diâmetro do avatar
AVA_BORDER = 4                 # Espessura da borda colorida
AVA_TOTAL  = AVA_SIZE + AVA_BORDER * 2   # Tamanho do avatar com borda

AVA_X = PAD + 16              # Posição X do avatar
AVA_Y = (H - AVA_TOTAL) // 2  # Centralizado verticalmente no card

TEXT_X = AVA_X + AVA_TOTAL + 24  # Início dos textos (lado direito do avatar)
# ─────────────────────────────────────────────────────────────────────────────


def load_profile_customs() -> dict:
    if not os.path.exists(CUSTOMS_FILE):
        return {}
    try:
        with open(CUSTOMS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"[PROFILE CARD] Erro ao carregar customizações: {e}")
        return {}


def save_profile_customs(data: dict):
    os.makedirs("data", exist_ok=True)
    try:
        with open(CUSTOMS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logger.error(f"[PROFILE CARD] Erro ao salvar customizações: {e}")


async def _fetch_image(url: str) -> Image.Image | None:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=8) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    return Image.open(io.BytesIO(data))
    except Exception as e:
        logger.warning(f"[PROFILE CARD] Falha ao carregar imagem: {url} ({e})")
    return None


def _aspect_fill(img: Image.Image, tw: int, th: int) -> Image.Image:
    img = img.convert("RGBA")
    w, h = img.size
    if w / h > tw / th:
        nw = int(h * tw / th)
        img = img.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    else:
        nh = int(w * th / tw)
        img = img.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
    return img.resize((tw, th), Image.Resampling.LANCZOS)


def _circular_avatar(img: Image.Image, size: int, border_color: tuple, border: int = 4) -> Image.Image:
    img = img.convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)

    circle = Image.new("RGBA", (size, size))
    circle.paste(img, mask=mask)

    out_size = size + border * 2
    out = Image.new("RGBA", (out_size, out_size), (0, 0, 0, 0))
    ImageDraw.Draw(out).ellipse((0, 0, out_size, out_size), fill=border_color)
    out.paste(circle, (border, border), mask=mask)
    return out


def _gradient(w: int, h: int, c1: tuple, c2: tuple) -> Image.Image:
    base = Image.new("RGBA", (w, h))
    draw = ImageDraw.Draw(base)
    r1, g1, b1 = c1[:3]
    r2, g2, b2 = c2[:3]
    for x in range(w):
        t = x / w
        draw.line([(x, 0), (x, h)], fill=(
            int(r1 + (r2 - r1) * t),
            int(g1 + (g2 - g1) * t),
            int(b1 + (b2 - b1) * t),
            255,
        ))
    return base


def _load_fonts() -> dict:
    """Carrega fontes com fallback seguro. Usa Segoe UI Emoji para emojis."""
    d = "C:\\Windows\\Fonts\\"
    emoji_font_path = os.path.join(d, "seguiemj.ttf")  # Segoe UI Emoji

    def tf(name, size):
        try:
            return ImageFont.truetype(os.path.join(d, name), size)
        except Exception:
            try:
                return ImageFont.truetype("arial.ttf", size)
            except Exception:
                return ImageFont.load_default()

    return {
        "title":    tf("segoeuib.ttf", 32),
        "sub":      tf("segoeui.ttf",  18),
        "lbl":      tf("segoeui.ttf",  14),
        "val":      tf("segoeuib.ttf", 20),
        "level":    tf("segoeuib.ttf", 28),
        "emoji":    tf("seguiemj.ttf", 24) if os.path.exists(emoji_font_path) else None,
    }


def _strip_emojis(text: str) -> str:
    """Remove emojis do texto para renderização limpa sem caixinhas."""
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "\U0001f926-\U0001f937"
        "\U00010000-\U0010ffff"
        "\u2640-\u2642"
        "\u2600-\u2B55"
        "\u200d\u23cf\u23e9\u231a\ufe0f\u3030"
        "]+",
        flags=re.UNICODE,
    )
    return emoji_pattern.sub("", text).strip()


async def generate_profile_card(
    username: str,
    level: int,
    xp: int,
    xp_next: int,
    wallet_coins: int,
    bank_coins: int,
    avatar_url: str,
    custom_bg_url: str = None,
    theme_name: str = "pink",
    bio: str = None,
    marriage_partner: str = None,
) -> str:
    theme = THEME_COLORS.get(theme_name.lower(), THEME_COLORS["pink"])
    fonts = _load_fonts()

    # ── 1. Plano de fundo ────────────────────────────────────────────────────
    if custom_bg_url:
        bg_raw = await _fetch_image(custom_bg_url)
        bg = _aspect_fill(bg_raw, W, H) if bg_raw else None
    else:
        bg = None

    if not bg:
        bg = _gradient(W, H, (40, 10, 60), (100, 20, 120))  # Roxo profundo padrão

    # ── 2. Overlay escuro arredondado (glassmorphism) ────────────────────────
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(overlay).rounded_rectangle(
        [(PAD // 2, PAD // 2), (W - PAD // 2, H - PAD // 2)],
        radius=20,
        fill=(10, 8, 18, 210),
    )

    # ── 3. Avatar circular ───────────────────────────────────────────────────
    if avatar_url:
        ava_raw = await _fetch_image(avatar_url)
        if ava_raw:
            ava = _circular_avatar(ava_raw, AVA_SIZE, theme, AVA_BORDER)
            bg.paste(ava, (AVA_X, AVA_Y), mask=ava)
        else:
            _fallback_avatar(bg, theme)
    else:
        _fallback_avatar(bg, theme)

    # ── 4. Compor overlay sobre o background ────────────────────────────────
    composite = Image.alpha_composite(bg, overlay)
    draw = ImageDraw.Draw(composite)

    # ── 5. Barra colorida lateral esquerda (acento de cor) ───────────────────
    draw.rounded_rectangle(
        [(PAD // 2, PAD // 2), (PAD // 2 + 4, H - PAD // 2)],
        radius=2,
        fill=theme,
    )

    # ── 6. Textos: Nome, Bio, Casamento ──────────────────────────────────────
    # Ponto Y do topo da coluna de texto (alinhado ao topo do avatar)
    ty = AVA_Y  # ~44px

    # Nome (sem emojis para evitar caixinhas no Pillow)
    name_clean = _strip_emojis(username)
    draw.text((TEXT_X, ty), name_clean, font=fonts["title"], fill=(255, 255, 255, 255))
    ty += 38  # altura do título

    # Bio
    bio_text = _strip_emojis(bio[:65] if bio else "Membro fútil tentando impressionar a Lira Amarinth.")
    draw.text((TEXT_X, ty), bio_text, font=fonts["sub"], fill=(190, 185, 210, 255))
    ty += 24

    # Casamento
    if marriage_partner:
        draw.text(
            (TEXT_X, ty),
            f"♥ Casado(a) com {_strip_emojis(marriage_partner)}",
            font=fonts["sub"],
            fill=(255, 120, 180, 255),
        )
        ty += 24

    ty += 8  # gap extra antes das stats

    # ── 7. Estatísticas de saldo ─────────────────────────────────────────────
    # Três colunas equidistantes a partir de TEXT_X
    cols = [TEXT_X, TEXT_X + 175, TEXT_X + 350]
    labels = ["CARTEIRA", "BANCO LUNÁDORO", "TOTAL"]
    values = [
        f"{wallet_coins:,} L$",
        f"{bank_coins:,} L$",
        f"{wallet_coins + bank_coins:,} L$",
    ]
    val_colors = [theme, (255, 215, 0, 255), (255, 255, 255, 255)]

    for cx, lbl, val, col in zip(cols, labels, values, val_colors):
        draw.text((cx, ty),      lbl, font=fonts["lbl"], fill=(140, 135, 165, 255))
        draw.text((cx, ty + 18), val, font=fonts["val"], fill=col)

    ty += 52  # espaço para label + valor + gap

    # ── 8. Linha divisória sutil ─────────────────────────────────────────────
    draw.line([(TEXT_X, ty), (W - PAD, ty)], fill=(60, 55, 80, 255), width=1)
    ty += 10

    # ── 9. XP e Nível na mesma linha ────────────────────────────────────────
    xp_str = f"{xp:,} / {xp_next:,} XP"
    lvl_str = f"NÍVEL {level}"

    # XP à esquerda
    draw.text((TEXT_X, ty), xp_str, font=fonts["sub"], fill=(190, 185, 210, 255))

    # Nível à direita (alinhado à mesma baseline)
    lvl_bbox = draw.textbbox((0, 0), lvl_str, font=fonts["level"])
    lvl_w = lvl_bbox[2] - lvl_bbox[0]
    draw.text((W - PAD - lvl_w, ty - 4), lvl_str, font=fonts["level"], fill=theme)

    ty += 26  # gap abaixo do texto XP

    # ── 10. Barra de XP ──────────────────────────────────────────────────────
    progress = max(0.0, min(1.0, xp / xp_next if xp_next > 0 else 0))
    bar_x0, bar_x1 = TEXT_X, W - PAD
    bar_y0, bar_y1 = ty, ty + 16

    # Track (fundo)
    draw.rounded_rectangle([(bar_x0, bar_y0), (bar_x1, bar_y1)], radius=8, fill=(40, 35, 58, 255))

    # Fill (progresso)
    fill_w = int((bar_x1 - bar_x0) * progress)
    if fill_w > 16:
        draw.rounded_rectangle([(bar_x0, bar_y0), (bar_x0 + fill_w, bar_y1)], radius=8, fill=theme)

    # ── 11. Salvar ───────────────────────────────────────────────────────────
    os.makedirs("temp", exist_ok=True)
    out_path = os.path.abspath(os.path.join("temp", f"profile_{username}_{level}.png"))
    composite.convert("RGB").save(out_path, "PNG")
    return out_path


def _fallback_avatar(bg: Image.Image, theme: tuple):
    fb = Image.new("RGBA", (AVA_TOTAL, AVA_TOTAL), (0, 0, 0, 0))
    ImageDraw.Draw(fb).ellipse((0, 0, AVA_TOTAL, AVA_TOTAL), fill=theme)
    bg.paste(fb, (AVA_X, AVA_Y), mask=fb)
