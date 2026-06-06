"""
Boas-vindas / despedidas com mensagens e GIFs aleatórios (estilo Loritta).
"""
from __future__ import annotations

import discord
from discord.ext import commands
from discord import app_commands
import json
import os

from ..slash_meta import GUILD_ONLY_CONTEXT, GUILD_ONLY_INSTALL, GuildOnlyCog
from ..constants import logger, EMOJI
from ..welcome_utils import (
    DEFAULT_LEAVE_MESSAGES,
    DEFAULT_WELCOME_MESSAGES,
    migrate_guild_config,
    pick_gif_category,
    pick_message,
)

WELCOME_FILE = os.path.join("data", "welcome.json")


def _load() -> dict:
    if os.path.exists(WELCOME_FILE):
        try:
            with open(WELCOME_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for gid, cfg in data.items():
                if isinstance(cfg, dict):
                    data[gid] = migrate_guild_config(cfg)
            return data
        except Exception:
            pass
    return {}


def _save(data: dict):
    os.makedirs("data", exist_ok=True)
    with open(WELCOME_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


async def _send_welcome_embed(
    channel: discord.TextChannel,
    member: discord.Member,
    text: str,
    gif_url: str | None,
):
    embed = discord.Embed(description=text, color=0xF5A3C7)
    embed.set_thumbnail(url=str(member.display_avatar.url))
    if gif_url:
        embed.set_image(url=gif_url)
    await channel.send(content=member.mention, embed=embed)


class Welcome(GuildOnlyCog):
    """Boas-vindas, despedidas e autorole."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._db: dict = _load()

    welcome_group = app_commands.Group(
        name="boas-vindas",
        description="Entradas, saídas e cargos automáticos (GIF e frases aleatórias)",
        default_permissions=discord.Permissions(manage_guild=True),
    )

    def _cfg(self, guild_id: int) -> dict:
        gid = str(guild_id)
        cfg = self._db.setdefault(gid, {})
        return migrate_guild_config(cfg)

    @welcome_group.command(name="configurar", description="Canal de entrada + opções aleatórias")
    @GUILD_ONLY_INSTALL
    @GUILD_ONLY_CONTEXT
    @app_commands.describe(
        canal="Canal das boas-vindas",
        mensagem="Frase extra (entra no pool). Tags: {user} {server} {count} {name}",
        mensagens_aleatorias="Sorteia entre frases padrão + suas",
        gifs_aleatorios="GIF anime aleatório (wave, hug, dance…)",
    )
    async def welcome_config(
        self,
        interaction: discord.Interaction,
        canal: discord.TextChannel,
        mensagem: str | None = None,
        mensagens_aleatorias: bool = True,
        gifs_aleatorios: bool = True,
    ):
        cfg = self._cfg(interaction.guild_id)
        cfg["welcome_channel"] = canal.id
        cfg["welcome_random_msg"] = mensagens_aleatorias
        cfg["welcome_random_gif"] = gifs_aleatorios
        if mensagem:
            pool = cfg.setdefault("welcome_messages", [])
            if mensagem not in pool:
                pool.append(mensagem)
        _save(self._db)

        preview = pick_message(cfg, interaction.user)
        embed = discord.Embed(
            title=f"{EMOJI.get('check', '✅')} Boas-vindas ativas",
            description=(
                f"**Canal:** {canal.mention}\n"
                f"**Frases aleatórias:** {'sim' if mensagens_aleatorias else 'não'}\n"
                f"**GIF aleatório:** {'sim' if gifs_aleatorios else 'não'}\n"
                f"**Frases no pool:** {len(cfg.get('welcome_messages') or [])} custom + "
                f"{len(DEFAULT_WELCOME_MESSAGES)} padrão\n\n"
                f"**Exemplo:**\n{preview}"
            ),
            color=0x7DD8A0,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @welcome_group.command(name="mensagem-adicionar", description="Adiciona uma frase ao pool de entrada")
    @GUILD_ONLY_INSTALL
    @GUILD_ONLY_CONTEXT
    @app_commands.describe(mensagem="Use {user}, {server}, {count}, {name}")
    async def welcome_msg_add(self, interaction: discord.Interaction, mensagem: str):
        cfg = self._cfg(interaction.guild_id)
        pool = cfg.setdefault("welcome_messages", [])
        pool.append(mensagem)
        _save(self._db)
        await interaction.response.send_message(
            f"✅ Frase adicionada ({len(pool)} custom). Aleatório: "
            f"{'ligado' if cfg.get('welcome_random_msg', True) else 'desligado'}.",
            ephemeral=True,
        )

    @welcome_group.command(name="mensagem-listar", description="Lista frases custom de entrada")
    @GUILD_ONLY_INSTALL
    @GUILD_ONLY_CONTEXT
    async def welcome_msg_list(self, interaction: discord.Interaction):
        cfg = self._cfg(interaction.guild_id)
        custom = cfg.get("welcome_messages") or []
        lines = [f"{i + 1}. {m}" for i, m in enumerate(custom)] or ["_(nenhuma — usa só as padrão)_"]
        embed = discord.Embed(
            title="Frases de entrada",
            description="\n".join(lines[:15]),
            color=0xF5A3C7,
        )
        embed.set_footer(text=f"Aleatório: {cfg.get('welcome_random_msg', True)} | GIF: {cfg.get('welcome_random_gif', True)}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @welcome_group.command(name="despedida", description="Canal de saída + opções aleatórias")
    @GUILD_ONLY_INSTALL
    @GUILD_ONLY_CONTEXT
    @app_commands.describe(
        canal="Canal quando alguém sair",
        mensagem="Frase extra no pool. Tags: {user} {server} {name}",
        mensagens_aleatorias="Sorteia frases",
        gifs_aleatorios="GIF na despedida (opcional)",
    )
    async def leave_config(
        self,
        interaction: discord.Interaction,
        canal: discord.TextChannel,
        mensagem: str | None = None,
        mensagens_aleatorias: bool = True,
        gifs_aleatorios: bool = False,
    ):
        cfg = self._cfg(interaction.guild_id)
        cfg["leave_channel"] = canal.id
        cfg["leave_random_msg"] = mensagens_aleatorias
        cfg["leave_random_gif"] = gifs_aleatorios
        if mensagem:
            pool = cfg.setdefault("leave_messages", [])
            if mensagem not in pool:
                pool.append(mensagem)
        _save(self._db)
        await interaction.response.send_message(
            f"✅ Despedidas em {canal.mention} | aleatório: {mensagens_aleatorias} | GIF: {gifs_aleatorios}",
            ephemeral=True,
        )

    @welcome_group.command(name="despedida-adicionar", description="Adiciona frase ao pool de saída")
    @GUILD_ONLY_INSTALL
    @GUILD_ONLY_CONTEXT
    async def leave_msg_add(self, interaction: discord.Interaction, mensagem: str):
        cfg = self._cfg(interaction.guild_id)
        pool = cfg.setdefault("leave_messages", [])
        pool.append(mensagem)
        _save(self._db)
        await interaction.response.send_message(f"✅ Frase de saída adicionada ({len(pool)}).", ephemeral=True)

    @welcome_group.command(name="testar", description="Prévia da mensagem de entrada ou saída no canal configurado")
    @GUILD_ONLY_INSTALL
    @GUILD_ONLY_CONTEXT
    @app_commands.describe(tipo="entrada ou saída")
    @app_commands.choices(tipo=[
        app_commands.Choice(name="Entrada (boas-vindas)", value="entrada"),
        app_commands.Choice(name="Saída (despedida)", value="saida"),
    ])
    async def welcome_test(self, interaction: discord.Interaction, tipo: str):
        cfg = self._cfg(interaction.guild_id)
        leaving = tipo == "saida"
        ch_id = cfg.get("leave_channel" if leaving else "welcome_channel")
        if not ch_id:
            await interaction.response.send_message(
                "❌ Configure o canal antes (`configurar` ou `despedida`).", ephemeral=True
            )
            return
        channel = interaction.guild.get_channel(ch_id)
        if not channel:
            await interaction.response.send_message("❌ Canal não encontrado.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        from .social import fetch_gif

        member = interaction.user
        text = pick_message(cfg, member, leaving=leaving)
        gif_url = None
        cat = pick_gif_category(cfg, leaving=leaving)
        if cat:
            gif_url = await fetch_gif(cat)

        try:
            if leaving:
                embed = discord.Embed(description=text, color=0x9B59B6)
                if gif_url:
                    embed.set_image(url=gif_url)
                await channel.send(embed=embed)
            else:
                await _send_welcome_embed(channel, member, text, gif_url)
            await interaction.followup.send(f"✅ Prévia enviada em {channel.mention}.", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("❌ Sem permissão para enviar nesse canal.", ephemeral=True)

    @welcome_group.command(name="autorole", description="Cargo automático ao entrar")
    @GUILD_ONLY_INSTALL
    @GUILD_ONLY_CONTEXT
    @app_commands.describe(cargo="Vazio = desativar")
    async def autorole_config(self, interaction: discord.Interaction, cargo: discord.Role | None = None):
        cfg = self._cfg(interaction.guild_id)
        if cargo is None:
            cfg["autorole"] = None
            _save(self._db)
            await interaction.response.send_message("✅ Autorole desativado.", ephemeral=True)
            return
        if cargo >= interaction.guild.me.top_role:
            await interaction.response.send_message(
                "❌ Suba meu cargo acima desse role.", ephemeral=True
            )
            return
        cfg["autorole"] = cargo.id
        _save(self._db)
        await interaction.response.send_message(f"✅ Autorole: {cargo.mention}", ephemeral=True)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        cfg = self._db.get(str(member.guild.id))
        if not cfg:
            return
        cfg = migrate_guild_config(cfg)

        role_id = cfg.get("autorole")
        if role_id:
            role = member.guild.get_role(role_id)
            if role:
                try:
                    await member.add_roles(role, reason="Autorole")
                except Exception as e:
                    logger.warning("[WELCOME] autorole %s: %s", member, e)

        channel_id = cfg.get("welcome_channel")
        if not channel_id:
            return
        channel = member.guild.get_channel(channel_id)
        if not channel:
            return

        from .social import fetch_gif

        text = pick_message(cfg, member, leaving=False)
        gif_url = None
        cat = pick_gif_category(cfg, leaving=False)
        if cat:
            gif_url = await fetch_gif(cat)

        try:
            await _send_welcome_embed(channel, member, text, gif_url)
        except Exception as e:
            logger.warning("[WELCOME] join %s: %s", member, e)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        cfg = self._db.get(str(member.guild.id))
        if not cfg:
            return
        cfg = migrate_guild_config(cfg)
        channel_id = cfg.get("leave_channel")
        if not channel_id:
            return
        channel = member.guild.get_channel(channel_id)
        if not channel:
            return

        from .social import fetch_gif

        text = pick_message(cfg, member, leaving=True)
        embed = discord.Embed(description=text, color=0x9B59B6)
        cat = pick_gif_category(cfg, leaving=True)
        if cat:
            gif_url = await fetch_gif(cat)
            if gif_url:
                embed.set_image(url=gif_url)
        try:
            await channel.send(embed=embed)
        except Exception:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(Welcome(bot))
    logger.info("[DISCORD] ✅ Cog Welcome carregada")