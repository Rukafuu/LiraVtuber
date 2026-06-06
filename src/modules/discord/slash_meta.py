"""Metadados compartilhados para slash commands (User App vs servidor)."""
from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from discord import app_commands
from discord.ext import commands

if TYPE_CHECKING:
    import discord

logger = logging.getLogger(__name__)

# Só em servidores onde o bot está instalado
GUILD_ONLY_INSTALL = app_commands.allowed_installs(guilds=True, users=False)
GUILD_ONLY_CONTEXT = app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)

# User Install + DM (chat, social, economia, ajuda, afk)
USER_APP_INSTALL = app_commands.allowed_installs(guilds=True, users=True)
USER_APP_CONTEXT = app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)

GLOBAL_SYNC_COOLDOWN_SEC = 3600


class GuildOnlyCog(commands.Cog):
    """Bloqueia slash deste cog fora de servidor (DM / User App sem guild)."""

    async def interaction_check(self, interaction) -> bool:
        if interaction.guild is not None:
            return True
        msg = "❌ Este comando só funciona **dentro de um servidor**."
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
        return False


async def ensure_guild(interaction) -> bool:
    """Retorna False se não houver guild (ex.: DM com User App)."""
    if interaction.guild is not None:
        return True
    if interaction.response.is_done():
        await interaction.followup.send(
            "❌ Este comando só funciona **dentro de um servidor**.",
            ephemeral=True,
        )
    else:
        await interaction.response.send_message(
            "❌ Este comando só funciona **dentro de um servidor**.",
            ephemeral=True,
        )
    return False


def global_sync_allowed(cog: commands.Cog) -> tuple[bool, int]:
    """Cooldown em memória para !sync global (owner)."""
    now = time.monotonic()
    last = getattr(cog, "_last_global_sync_at", 0.0)
    elapsed = now - last
    if elapsed < GLOBAL_SYNC_COOLDOWN_SEC:
        return False, int(GLOBAL_SYNC_COOLDOWN_SEC - elapsed)
    cog._last_global_sync_at = now
    return True, 0


# Grupos/subcomandos antigos e slash soltos que duplicavam /act
ORPHAN_SLASH_NAMES: frozenset[str] = frozenset({
    "interacao",
    "expressao",
    "abracar", "beijar", "fazer_carinho", "socar", "dar_tapa", "aconchegar",
    "morder", "cutucar", "alimentar", "highfive", "chutar", "cocegas",
    "acenar", "arremessar", "xingar", "olhar", "dancar", "chorar", "rir",
    "ficar_com_raiva", "amar", "corar", "facepalm", "pensar", "dormir", "piscar",
    "beijo_rapido", "mao", "apertar_mao", "comer", "matar", "feliz", "sorrir",
    "concordar", "joinha", "satisfeito", "fazer_bico", "triste", "dar_de_ombros",
    "entediado", "recusar", "correr", "bocejar", "espreitar",
})


async def purge_orphan_global_commands(bot: "discord.Client") -> int:
    """Remove comandos globais antigos que não existem mais no código."""
    app_id = bot.application_id
    if not app_id:
        return 0
    removed = 0
    try:
        for cmd in await bot.http.get_global_commands(app_id):
            if cmd.get("name") in ORPHAN_SLASH_NAMES:
                await bot.http.delete_global_command(app_id, cmd["id"])
                removed += 1
                logger.info("[DISCORD] Removido comando global órfão: %s", cmd["name"])
    except Exception as e:
        logger.warning("[DISCORD] Falha ao limpar globais órfãos: %s", e)
    return removed


async def purge_duplicate_guild_commands(bot: "discord.Client", guild: "discord.Guild") -> int:
    """
    Apaga comandos de guild que repetem nomes já registrados globalmente
    (efeito colateral de copy_global_to + sync).
    """
    app_id = bot.application_id
    if not app_id:
        return 0
    removed = 0
    try:
        global_names = {c["name"] for c in await bot.http.get_global_commands(app_id)}
        for cmd in await bot.http.get_guild_commands(app_id, guild.id):
            name = cmd.get("name")
            if name in global_names or name in ORPHAN_SLASH_NAMES:
                await bot.http.delete_guild_command(app_id, guild.id, cmd["id"])
                removed += 1
                logger.info("[DISCORD] Removido duplicata em %s: %s", guild.name, name)
    except Exception as e:
        logger.warning("[DISCORD] Falha ao limpar guild %s: %s", guild.name, e)
    return removed