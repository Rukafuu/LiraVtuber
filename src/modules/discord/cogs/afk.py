"""
╔══════════════════════════════════════════════════════════════╗
║  LiraVT · Cog: AFK                                          ║
║  Avisa quem mencionar um usuário que está AFK               ║
╚══════════════════════════════════════════════════════════════╝
"""
import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import time
from datetime import datetime, timezone
from ..constants import logger, EMOJI
from ..slash_meta import USER_APP_CONTEXT, USER_APP_INSTALL

AFK_FILE = os.path.join("data", "afk.json")


def _load() -> dict:
    if os.path.exists(AFK_FILE):
        try:
            with open(AFK_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save(data: dict):
    os.makedirs("data", exist_ok=True)
    with open(AFK_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _fmt_delta(seconds: float) -> str:
    """Formata segundos em '2h 5min' ou '30s'."""
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    parts = []
    if h:
        parts.append(f"{h}h")
    if m:
        parts.append(f"{m}min")
    if not parts:
        parts.append(f"{s}s")
    return " ".join(parts)


class AFK(commands.Cog):
    """Sistema de AFK — avisa quem mencionar usuários ausentes."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._db: dict = _load()           # { "user_id": {"motivo": str, "since": float} }
        self._cooldown: dict = {}          # evita múltiplos avisos seguidos por mensagem

    # ── /afk ─────────────────────────────────────────────────────────────────
    @app_commands.command(name="afk", description="Ativa o modo AFK e avisa quem te mencionar")
    @USER_APP_INSTALL
    @USER_APP_CONTEXT
    @app_commands.describe(motivo="Motivo do AFK (opcional)")
    async def afk_cmd(self, interaction: discord.Interaction, motivo: str = "Sem motivo"):
        uid = str(interaction.user.id)

        if uid in self._db:
            await interaction.response.send_message(
                f"{EMOJI.get('info','ℹ️')} Você já está em AFK! Use `/voltei` para sair.",
                ephemeral=True
            )
            return

        self._db[uid] = {"motivo": motivo, "since": time.time()}
        _save(self._db)

        embed = discord.Embed(
            title=f"{EMOJI.get('sleep','😴')} AFK ativado",
            description=f"**{interaction.user.display_name}** agora está AFK\n> {motivo}",
            color=0x9b8ec4,
        )
        embed.set_footer(text="Qualquer um que te mencionar será avisado automaticamente.")
        await interaction.response.send_message(embed=embed)
        logger.info(f"[AFK] {interaction.user} entrou em AFK: {motivo}")

    # ── /voltei ───────────────────────────────────────────────────────────────
    @app_commands.command(name="voltei", description="Remove o modo AFK")
    @USER_APP_INSTALL
    @USER_APP_CONTEXT
    async def back_cmd(self, interaction: discord.Interaction):
        uid = str(interaction.user.id)

        if uid not in self._db:
            await interaction.response.send_message(
                f"{EMOJI.get('info','ℹ️')} Você não está em AFK.",
                ephemeral=True
            )
            return

        entry = self._db.pop(uid)
        _save(self._db)
        elapsed = _fmt_delta(time.time() - entry["since"])

        embed = discord.Embed(
            title=f"{EMOJI.get('wave','👋')} Bem-vindo(a) de volta!",
            description=f"AFK removido após **{elapsed}**\nMotivo estava: *{entry['motivo']}*",
            color=0x7dd8a0,
        )
        await interaction.response.send_message(embed=embed)
        logger.info(f"[AFK] {interaction.user} saiu do AFK após {elapsed}")

    # ── Detecta menções a usuários AFK ───────────────────────────────────────
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.mentions:
            return

        # Remove quem mandou a mensagem do próprio AFK automaticamente
        author_id = str(message.author.id)
        if author_id in self._db:
            entry = self._db.pop(author_id)
            _save(self._db)
            elapsed = _fmt_delta(time.time() - entry["since"])
            try:
                await message.channel.send(
                    f"👋 {message.author.mention} Bem-vindo(a) de volta! "
                    f"Você estava AFK por **{elapsed}** *(motivo: {entry['motivo']})*",
                    delete_after=15,
                )
            except Exception:
                pass

        # Avisa sobre usuários AFK mencionados (evita spam: 1 aviso por mensagem por destino)
        avisados = set()
        for mentioned in message.mentions:
            mid = str(mentioned.id)
            if mid in self._db and mid not in avisados:
                avisados.add(mid)
                entry = self._db[mid]
                elapsed = _fmt_delta(time.time() - entry["since"])
                try:
                    await message.channel.send(
                        f"😴 **{mentioned.display_name}** está AFK há **{elapsed}**\n"
                        f"> {entry['motivo']}",
                        delete_after=12,
                    )
                except Exception:
                    pass


async def setup(bot: commands.Bot):
    await bot.add_cog(AFK(bot))
    logger.info("[DISCORD] ✅ Cog AFK carregada")
