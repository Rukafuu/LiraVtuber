"""
╔══════════════════════════════════════════════════════════════╗
║  LiraVT · Cog: Sticky Messages                              ║
║  Mantém uma mensagem sempre no final de um canal            ║
╚══════════════════════════════════════════════════════════════╝
"""
import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import asyncio
from ..slash_meta import GUILD_ONLY_CONTEXT, GUILD_ONLY_INSTALL, GuildOnlyCog
from ..constants import logger, EMOJI

STICKY_FILE = os.path.join("data", "sticky.json")


def _load() -> dict:
    if os.path.exists(STICKY_FILE):
        try:
            with open(STICKY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save(data: dict):
    os.makedirs("data", exist_ok=True)
    with open(STICKY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class StickyMessages(GuildOnlyCog):
    """
    Mantém uma mensagem 'grudada' no final de um canal.
    Cada vez que alguém manda uma nova mensagem, a sticky é re-postada embaixo.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # { "channel_id": {"text": str, "msg_id": int|None} }
        self._db: dict = _load()
        # Lock por canal para evitar condição de corrida
        self._locks: dict[int, asyncio.Lock] = {}

    def _get_lock(self, channel_id: int) -> asyncio.Lock:
        if channel_id not in self._locks:
            self._locks[channel_id] = asyncio.Lock()
        return self._locks[channel_id]

    # ── /sticky set ──────────────────────────────────────────────────────────
    @app_commands.command(name="sticky-set", description="Cria/atualiza a mensagem grudada neste canal")
    @GUILD_ONLY_INSTALL
    @GUILD_ONLY_CONTEXT
    @app_commands.describe(texto="Texto da mensagem que ficará presa no fim do canal")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def sticky_set(self, interaction: discord.Interaction, texto: str):
        cid = str(interaction.channel_id)

        # Remove a sticky antiga se existir
        if cid in self._db and self._db[cid].get("msg_id"):
            try:
                old = await interaction.channel.fetch_message(self._db[cid]["msg_id"])
                await old.delete()
            except Exception:
                pass

        # Posta a nova sticky
        embed = discord.Embed(
            description=f"📌 {texto}",
            color=0xf0c060,
        )
        embed.set_footer(text="📌 Mensagem fixada (sticky)")
        sticky_msg = await interaction.channel.send(embed=embed)

        self._db[cid] = {"text": texto, "msg_id": sticky_msg.id}
        _save(self._db)

        await interaction.response.send_message(
            f"{EMOJI.get('check','✅')} Sticky definida neste canal!", ephemeral=True
        )
        logger.info(f"[STICKY] Sticky criada em #{interaction.channel} por {interaction.user}")

    # ── /sticky remove ────────────────────────────────────────────────────────
    @app_commands.command(name="sticky-remove", description="Remove a mensagem grudada deste canal")
    @GUILD_ONLY_INSTALL
    @GUILD_ONLY_CONTEXT
    @app_commands.checks.has_permissions(manage_messages=True)
    async def sticky_remove(self, interaction: discord.Interaction):
        cid = str(interaction.channel_id)

        if cid not in self._db:
            await interaction.response.send_message(
                f"{EMOJI.get('info','ℹ️')} Não há sticky neste canal.", ephemeral=True
            )
            return

        # Apaga a mensagem sticky
        if self._db[cid].get("msg_id"):
            try:
                msg = await interaction.channel.fetch_message(self._db[cid]["msg_id"])
                await msg.delete()
            except Exception:
                pass

        del self._db[cid]
        _save(self._db)

        await interaction.response.send_message(
            f"{EMOJI.get('check','✅')} Sticky removida!", ephemeral=True
        )
        logger.info(f"[STICKY] Sticky removida em #{interaction.channel} por {interaction.user}")

    # ── /sticky info ──────────────────────────────────────────────────────────
    @app_commands.command(name="sticky-info", description="Mostra a sticky atual deste canal")
    @GUILD_ONLY_INSTALL
    @GUILD_ONLY_CONTEXT
    async def sticky_info(self, interaction: discord.Interaction):
        cid = str(interaction.channel_id)
        if cid not in self._db:
            await interaction.response.send_message(
                f"{EMOJI.get('info','ℹ️')} Sem sticky neste canal.", ephemeral=True
            )
            return
        txt = self._db[cid]["text"]
        await interaction.response.send_message(
            f"📌 **Sticky atual:**\n{txt}", ephemeral=True
        )

    # ── Listener — re-posta a sticky quando alguém manda mensagem ─────────────
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        cid = str(message.channel.id)
        if cid not in self._db:
            return

        async with self._get_lock(message.channel.id):
            entry = self._db.get(cid)
            if not entry:
                return

            # Se a mensagem mais recente já for a sticky, não faz nada
            if message.id == entry.get("msg_id"):
                return

            # Apaga a sticky antiga
            if entry.get("msg_id"):
                try:
                    old = await message.channel.fetch_message(entry["msg_id"])
                    await old.delete()
                except Exception:
                    pass

            # Re-posta
            embed = discord.Embed(
                description=f"📌 {entry['text']}",
                color=0xf0c060,
            )
            embed.set_footer(text="📌 Mensagem fixada (sticky)")
            try:
                new_msg = await message.channel.send(embed=embed)
                self._db[cid]["msg_id"] = new_msg.id
                _save(self._db)
            except Exception as e:
                logger.warning(f"[STICKY] Erro ao re-postar sticky: {e}")

    # ── Tratamento de erro de permissão ───────────────────────────────────────
    @sticky_set.error
    @sticky_remove.error
    async def permission_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ Você precisa da permissão **Gerenciar Mensagens** para isso.",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(StickyMessages(bot))
    logger.info("[DISCORD] ✅ Cog StickyMessages carregada")
