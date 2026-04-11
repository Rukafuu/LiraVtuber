from __future__ import annotations

import time

import customtkinter as ctk

from src.gui.design import COLORS, FONT_BODY, FONT_SMALL, FONT_TITLE

try:
    import winsound
except ImportError:  # pragma: no cover - Windows-first fallback
    winsound = None


def _pit_pit():
    if winsound is None:
        return
    try:
        winsound.MessageBeep(winsound.MB_ICONASTERISK)
        winsound.MessageBeep(winsound.MB_OK)
    except Exception:
        pass


def confirm_pc_action_popup(
    *,
    title: str,
    body: str,
    risk_label: str,
    timeout_seconds: int = 15,
    parent=None,
) -> bool:
    """Exibe uma confirmação pequena e topmost no canto da tela."""

    _pit_pit()
    temp_root = None
    if parent is None:
        temp_root = ctk.CTk()
        temp_root.withdraw()
        parent = temp_root

    result = {"value": False}
    started_at = time.time()

    popup = ctk.CTkToplevel(parent)
    popup.attributes("-topmost", True)
    popup.resizable(False, False)
    popup.title(title)
    popup.configure(fg_color=COLORS["bg_darkest"])
    try:
        popup.transient(parent)
    except Exception:
        pass

    width = 360
    height = 200
    popup.update_idletasks()
    screen_w = popup.winfo_screenwidth()
    x_pos = max(20, screen_w - width - 28)
    y_pos = 42
    popup.geometry(f"{width}x{height}+{x_pos}+{y_pos}")

    shell = ctk.CTkFrame(
        popup,
        fg_color=COLORS["bg_card"],
        corner_radius=18,
        border_width=2,
        border_color=COLORS["border_strong"],
    )
    shell.pack(fill="both", expand=True)

    ctk.CTkLabel(
        shell,
        text=title,
        font=FONT_TITLE,
        text_color=COLORS["text_primary"],
        anchor="w",
    ).pack(fill="x", padx=16, pady=(14, 4))

    ctk.CTkLabel(
        shell,
        text=f"Risco: {risk_label}",
        font=FONT_SMALL,
        text_color=COLORS["yellow"] if risk_label != "baixo" else COLORS["green"],
        anchor="w",
    ).pack(fill="x", padx=16)

    ctk.CTkLabel(
        shell,
        text=body,
        font=FONT_BODY,
        text_color=COLORS["text_secondary"],
        wraplength=width - 46,
        justify="left",
        anchor="w",
    ).pack(fill="x", padx=16, pady=(10, 10))

    countdown_label = ctk.CTkLabel(
        shell,
        text=f"Negando automaticamente em {timeout_seconds}s",
        font=FONT_SMALL,
        text_color=COLORS["text_muted"],
        anchor="w",
    )
    countdown_label.pack(fill="x", padx=16, pady=(0, 10))

    actions = ctk.CTkFrame(shell, fg_color="transparent")
    actions.pack(fill="x", padx=16, pady=(0, 14))

    def _finish(value: bool):
        result["value"] = bool(value)
        try:
            popup.grab_release()
        except Exception:
            pass
        try:
            popup.destroy()
        except Exception:
            pass

    ctk.CTkButton(
        actions,
        text="Negar",
        width=110,
        height=34,
        fg_color=COLORS["bg_darkest"],
        hover_color="#442323",
        text_color=COLORS["text_primary"],
        border_width=2,
        border_color=COLORS["border"],
        command=lambda: _finish(False),
    ).pack(side="left")

    ctk.CTkButton(
        actions,
        text="Permitir",
        width=110,
        height=34,
        fg_color=COLORS["purple_dim"],
        hover_color=COLORS["purple_neon"],
        text_color=COLORS["text_primary"],
        command=lambda: _finish(True),
    ).pack(side="right")

    def _tick():
        if not popup.winfo_exists():
            return
        elapsed = int(time.time() - started_at)
        remaining = max(0, timeout_seconds - elapsed)
        countdown_label.configure(text=f"Negando automaticamente em {remaining}s")
        if remaining <= 0:
            _finish(False)
            return
        popup.after(250, _tick)

    popup.bind("<Escape>", lambda _event: _finish(False))
    popup.protocol("WM_DELETE_WINDOW", lambda: _finish(False))
    try:
        popup.grab_set()
    except Exception:
        pass
    popup.after(0, lambda: popup.focus_force())
    popup.after(0, lambda: popup.lift())
    popup.after(250, _tick)
    popup.wait_window()

    if temp_root is not None:
        try:
            temp_root.destroy()
        except Exception:
            pass
    return result["value"]
