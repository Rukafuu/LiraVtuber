"""Carteira de gemas — busca web (Tavily) e recompensas daily/weekly/PIX."""
from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any



logger = logging.getLogger(__name__)

_DATA_DIR = Path(os.getenv("LIRA_DATA_DIR", "data"))
_DB_PATH = _DATA_DIR / "lira_gems.db"
_CONFIG_PATH = _DATA_DIR / "gems_shop.json"

_DEFAULT_CONFIG: dict[str, Any] = {
    "tavily_cost": 1,
    "daily_reward": 2,
    "weekly_reward": 10,
    "pix_key": "",
    "shop_note": "Envie o comprovante PIX para @Rukafuu com seu @Discord ou número de WhatsApp.",
    "packs": [
        {"gems": 15, "price_brl": 9.90, "label": "Bolsa de gemas"},
        {"gems": 50, "price_brl": 29.90, "label": "Saco de gemas"},
        {"gems": 120, "price_brl": 59.90, "label": "Baú de gemas"},
    ],
}


def _load_config() -> dict[str, Any]:
    cfg = dict(_DEFAULT_CONFIG)
    if _CONFIG_PATH.is_file():
        try:
            raw = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                cfg.update(raw)
        except Exception as exc:
            logger.warning("[GEMS] Config inválida (%s): %s", _CONFIG_PATH, exc)
    pix = (os.getenv("GEMS_PIX_KEY") or os.getenv("VIP_PIX_KEY") or "").strip()
    if pix:
        cfg["pix_key"] = pix
    if not cfg.get("pix_key"):
        try:
            vip_path = _DATA_DIR / "vip_users.json"
            if vip_path.is_file():
                vip = json.loads(vip_path.read_text(encoding="utf-8"))
                cfg["pix_key"] = vip.get("config", {}).get("pix_key", "")
        except Exception:
            pass
    return cfg


def get_tavily_gem_cost() -> int:
    return max(1, int(_load_config().get("tavily_cost", 1)))


def _normalize_whatsapp_jid(jid: str) -> str:
    text = (jid or "").strip()
    if not text:
        return ""
    base = text.split(":")[0]
    if "@" not in base and "@" in text:
        base = f"{base}@{text.split('@', 1)[1]}"
    return base


def account_from_caller(ctx: Any) -> str | None:
    if ctx is None:
        return None
    if hasattr(ctx, "channel"):
        channel = str(getattr(ctx, "channel", "") or "").strip().lower()
        user_id = str(getattr(ctx, "user_id", "") or "").strip()
        jid = str(getattr(ctx, "jid", "") or "").strip()
        extra = getattr(ctx, "extra", None) or {}
    else:
        data = ctx if isinstance(ctx, dict) else {}
        channel = str(data.get("channel", "") or "").strip().lower()
        user_id = str(data.get("user_id", "") or "").strip()
        jid = str(data.get("jid", "") or "").strip()
        extra = data.get("extra") or {}
    if channel == "discord" and user_id:
        return f"discord:{user_id}"
    if channel == "whatsapp":
        clean = _normalize_whatsapp_jid(jid or str(extra.get("jid", "")))
        if clean:
            return f"whatsapp:{clean}"
    return None


class GemWallet:
    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or _DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS gem_wallets (
                    account TEXT PRIMARY KEY,
                    gems INTEGER NOT NULL DEFAULT 0,
                    last_daily TEXT,
                    last_weekly TEXT,
                    updated_at TEXT
                )
                """
            )

    def _ensure_row(self, conn: sqlite3.Connection, account: str) -> None:
        conn.execute(
            "INSERT OR IGNORE INTO gem_wallets (account, gems, updated_at) VALUES (?, 0, ?)",
            (account, datetime.now().isoformat()),
        )

    def get_balance(self, account: str) -> int:
        with self._connect() as conn:
            self._ensure_row(conn, account)
            row = conn.execute(
                "SELECT gems FROM gem_wallets WHERE account = ?",
                (account,),
            ).fetchone()
            return int(row["gems"]) if row else 0

    def add_gems(self, account: str, amount: int, *, reason: str = "") -> int:
        amount = int(amount)
        if amount <= 0:
            return self.get_balance(account)
        now = datetime.now().isoformat()
        with self._connect() as conn:
            self._ensure_row(conn, account)
            conn.execute(
                "UPDATE gem_wallets SET gems = gems + ?, updated_at = ? WHERE account = ?",
                (amount, now, account),
            )
        logger.info("[GEMS] +%d para %s (%s)", amount, account, reason or "credit")
        return self.get_balance(account)

    def spend_gems(self, account: str, amount: int, *, reason: str = "") -> bool:
        amount = int(amount)
        if amount <= 0:
            return True
        now = datetime.now().isoformat()
        with self._connect() as conn:
            self._ensure_row(conn, account)
            row = conn.execute(
                "SELECT gems FROM gem_wallets WHERE account = ?",
                (account,),
            ).fetchone()
            if not row or int(row["gems"]) < amount:
                return False
            conn.execute(
                "UPDATE gem_wallets SET gems = gems - ?, updated_at = ? WHERE account = ?",
                (amount, now, account),
            )
        logger.info("[GEMS] -%d de %s (%s)", amount, account, reason or "spend")
        return True

    def claim_daily(self, account: str) -> dict[str, Any]:
        cfg = _load_config()
        reward = int(cfg.get("daily_reward", 2))
        now = datetime.now()
        with self._connect() as conn:
            self._ensure_row(conn, account)
            row = conn.execute(
                "SELECT last_daily, gems FROM gem_wallets WHERE account = ?",
                (account,),
            ).fetchone()
            if row and row["last_daily"]:
                last = datetime.fromisoformat(row["last_daily"])
                if now < last + timedelta(days=1):
                    wait = last + timedelta(days=1) - now
                    hours = int(wait.total_seconds() // 3600)
                    return {
                        "success": False,
                        "message": f"Daily de gemas disponível em ~{hours}h.",
                    }
            conn.execute(
                """
                UPDATE gem_wallets
                SET gems = gems + ?, last_daily = ?, updated_at = ?
                WHERE account = ?
                """,
                (reward, now.isoformat(), now.isoformat(), account),
            )
        new_balance = self.get_balance(account)
        return {
            "success": True,
            "gems": reward,
            "balance": new_balance,
            "message": f"Você recebeu {reward} gemas 💎",
        }

    def claim_weekly(self, account: str) -> dict[str, Any]:
        cfg = _load_config()
        reward = int(cfg.get("weekly_reward", 10))
        now = datetime.now()
        with self._connect() as conn:
            self._ensure_row(conn, account)
            row = conn.execute(
                "SELECT last_weekly FROM gem_wallets WHERE account = ?",
                (account,),
            ).fetchone()
            if row and row["last_weekly"]:
                last = datetime.fromisoformat(row["last_weekly"])
                if now < last + timedelta(days=7):
                    wait = last + timedelta(days=7) - now
                    days = max(1, int(wait.total_seconds() // 86400))
                    return {
                        "success": False,
                        "message": f"Weekly de gemas disponível em ~{days} dia(s).",
                    }
            conn.execute(
                """
                UPDATE gem_wallets
                SET gems = gems + ?, last_weekly = ?, updated_at = ?
                WHERE account = ?
                """,
                (reward, now.isoformat(), now.isoformat(), account),
            )
        new_balance = self.get_balance(account)
        return {
            "success": True,
            "gems": reward,
            "balance": new_balance,
            "message": f"Você recebeu {reward} gemas 💎 (weekly)",
        }

    def shop_text(self) -> str:
        cfg = _load_config()
        lines = [
            "💎 **Loja de Gemas** — cada busca na web (Tavily) custa "
            f"**{get_tavily_gem_cost()}** gema(s).",
            "",
            "🎁 **Grátis**",
            f"• `/daily` — +{cfg.get('daily_reward', 2)} gemas/dia",
            f"• `/weekly` — +{cfg.get('weekly_reward', 10)} gemas/semana",
            "",
            "🛒 **Pacotes PIX**",
        ]
        pix = (cfg.get("pix_key") or "").strip()
        for pack in cfg.get("packs") or []:
            lines.append(
                f"• **{pack.get('label', 'Pacote')}**: {pack.get('gems')} gemas — "
                f"R$ {float(pack.get('price_brl', 0)):.2f}"
            )
        if pix:
            lines.extend(["", f"🏦 **PIX:** `{pix}`"])
        note = (cfg.get("shop_note") or "").strip()
        if note:
            lines.extend(["", note])
        return "\n".join(lines)


gems_wallet = GemWallet()