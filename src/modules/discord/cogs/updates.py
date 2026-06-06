"""
Anúncios automáticos de novidades da Lira em um canal fixo.
Fonte: data/lira_changelog.json — estado: data/lira_updates_state.json
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import discord
from discord.ext import commands

from ..constants import logger

CHANGELOG_FILE = os.path.join("data", "lira_changelog.json")
STATE_FILE = os.path.join("data", "lira_updates_state.json")
DEFAULT_UPDATES_CHANNEL_ID = 1511174461347594365


def _updates_channel_id() -> int:
    raw = os.getenv("LIRA_UPDATES_CHANNEL_ID", str(DEFAULT_UPDATES_CHANNEL_ID))
    try:
        return int(raw.strip())
    except ValueError:
        return DEFAULT_UPDATES_CHANNEL_ID


def _load_changelog() -> list[dict]:
    if not os.path.exists(CHANGELOG_FILE):
        return []
    try:
        with open(CHANGELOG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return list(data.get("entries") or [])
    except Exception as e:
        logger.warning("[UPDATES] changelog inválido: %s", e)
        return []


def _load_state() -> set[str]:
    if not os.path.exists(STATE_FILE):
        return set()
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return set(data.get("posted_ids") or [])
    except Exception:
        return set()


def _save_state(posted: set[str]):
    os.makedirs("data", exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"posted_ids": sorted(posted)}, f, ensure_ascii=False, indent=2)


class UpdatesAnnouncer(commands.Cog):
    """Posta entradas novas do changelog no canal de novidades."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._announced_this_session = False

    @commands.Cog.listener()
    async def on_ready(self):
        if self._announced_this_session:
            return
        self._announced_this_session = True
        await self._post_pending_updates()

    async def _post_pending_updates(self):
        channel_id = _updates_channel_id()
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            try:
                ch = await self.bot.fetch_channel(channel_id)
                if isinstance(ch, discord.TextChannel):
                    channel = ch
            except Exception as e:
                logger.warning("[UPDATES] Canal %s inacessível: %s", channel_id, e)
                return

        if not isinstance(channel, discord.TextChannel):
            logger.warning("[UPDATES] ID %s não é canal de texto", channel_id)
            return

        posted = _load_state()
        entries = _load_changelog()
        pending = [e for e in entries if e.get("id") and e["id"] not in posted]
        if not pending:
            logger.info("[UPDATES] Nenhuma novidade pendente.")
            return

        for entry in pending:
            eid = entry["id"]
            title = entry.get("title", "Novidade")
            body = entry.get("body", "")
            highlights = entry.get("highlights") or []

            embed = discord.Embed(
                title=f"🌸 Novidade — {title}",
                description=body,
                color=0xE91E63,
                timestamp=datetime.now(timezone.utc),
            )
            if highlights:
                embed.add_field(
                    name="Destaques",
                    value="\n".join(f"• {h}" for h in highlights[:8]),
                    inline=False,
                )
            embed.set_footer(text="Lira Amarinth · atualização automática")

            try:
                await channel.send(embed=embed)
                posted.add(eid)
                logger.info("[UPDATES] Anunciado: %s em #%s", eid, channel.name)
            except discord.Forbidden:
                logger.error("[UPDATES] Sem permissão em #%s (%s)", channel.name, channel_id)
                break
            except Exception as e:
                logger.error("[UPDATES] Falha ao postar %s: %s", eid, e)
                break

        _save_state(posted)


async def setup(bot: commands.Bot):
    await bot.add_cog(UpdatesAnnouncer(bot))
    logger.info("[DISCORD] ✅ Cog Updates (novidades automáticas) carregada")