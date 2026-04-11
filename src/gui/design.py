"""
Design Tokens — Paleta de cores dinâmicas, fontes e constantes visuais.
As cores de acento são geradas a partir da cor escolhida pelo usuário no config.json.
"""

import colorsys
import logging

logger = logging.getLogger(__name__)


def _hex_to_hsl(hex_color: str):
    """Converte hex (#rrggbb) para HSL (0-1)."""
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16) / 255, int(hex_color[2:4], 16) / 255, int(hex_color[4:6], 16) / 255
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return h, s, l


def _hsl_to_hex(h, s, l):
    """Converte HSL (0-1) para hex."""
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"


def get_accent_palette(hex_color: str) -> dict:
    """Gera variantes de uma cor de acento (neon, dim, dark)."""
    h, s, l = _hex_to_hsl(hex_color)
    return {
        "accent_neon": hex_color,
        "accent_dim": _hsl_to_hex(h, s, max(0.2, l - 0.15)),
        "accent_dark": _hsl_to_hex(h, max(0.3, s - 0.2), max(0.08, l - 0.35)),
    }


# =====================================================
# PALETA BASE (DARK MODE — nunca muda)
# =====================================================
_BASE_COLORS = {
    "bg_darkest":    "#08080a",
    "bg_dark":       "#0e0e14",
    "bg_sidebar":    "#111118",
    "bg_card":       "#16161f",
    "bg_card_hover": "#1e1e2a",
    "border_subtle": "#232433",
    "border":        "#36384c",
    "border_strong": "#50536f",
    "green":         "#4ade80",
    "red":           "#ef4444",
    "yellow":        "#facc15",
    "text_primary":  "#e2e8f0",
    "text_secondary": "#94a3b8",
    "text_muted":    "#64748b",
    # Azul fixo (usado em labels e barras secundárias)
    "blue_neon":     "#3b82f6",
    "blue_dim":      "#1e40af",
}

# =====================================================
# CORES COMPLETAS (base + acento dinâmico)
# =====================================================
DEFAULT_ACCENT = "#f472b6"  # Rosa floral

COLORS = dict(_BASE_COLORS)


def reload_colors(accent_hex: str = None):
    """Atualiza as cores de acento globalmente. Chamado quando o usuário muda o tema."""
    accent = accent_hex or DEFAULT_ACCENT
    palette = get_accent_palette(accent)
    COLORS["purple_neon"] = palette["accent_neon"]   # Mantemos a chave "purple_neon" para compatibilidade
    COLORS["purple_dim"] = palette["accent_dim"]
    COLORS["purple_dark"] = palette["accent_dark"]
    COLORS["border_focus"] = palette["accent_dim"]


# Inicializa com a cor padrão
reload_colors(DEFAULT_ACCENT)


# =====================================================
# FONTES
# =====================================================
FONT_HEADER  = ("Consolas", 24, "bold")
FONT_TITLE   = ("Segoe UI", 16, "bold")
FONT_BODY    = ("Segoe UI", 13)
FONT_SMALL   = ("Segoe UI", 11)
FONT_MONO    = ("Consolas", 12)
FONT_MONO_SM = ("Consolas", 10)
