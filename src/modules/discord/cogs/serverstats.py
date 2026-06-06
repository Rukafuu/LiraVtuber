"""
╔══════════════════════════════════════════════════════════════╗
║  LiraVT · Cog: Server Stats                                 ║
║  Canais de voz com contadores de membros/bots/etc.          ║
╚══════════════════════════════════════════════════════════════╝
"""
import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os
from ..slash_meta import GUILD_ONLY_CONTEXT, GUILD_ONLY_INSTALL, GuildOnlyCog
from ..constants import logger, EMOJI

STATS_FILE = os.path.join("data", "serverstats.json")

# Templates de nome — use {value} como placeholder
DEFAULT_TEMPLATES = {
    "total":   "👥 Membros: {value}",
    "humans":  "🧑 Usuários: {value}",
    "bots":    "🤖 Bots: {value}",
    "online":  "🟢 Online: {value}",
    "boosts":  "🚀 Boosts: {value}",
    "roles":   "🎭 Cargos: {value}",
    "channels":"📚 Canais: {value}",
}

STAT_CHOICES = [
    app_commands.Choice(name="Membros totais",  value="total"),
    app_commands.Choice(name="Usuários humanos",value="humans"),
    app_commands.Choice(name="Bots",            value="bots"),
    app_commands.Choice(name="Membros online",  value="online"),
    app_commands.Choice(name="Boosts do server",value="boosts"),
    app_commands.Choice(name="Total de cargos", value="roles"),
    app_commands.Choice(name="Total de canais", value="channels"),
]


def _load() -> dict:
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save(data: dict):
    os.makedirs("data", exist_ok=True)
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _get_stat_value(guild: discord.Guild, stat: str) -> int | str:
    if stat == "total":
        return guild.member_count or 0
    if stat == "humans":
        return sum(1 for m in guild.members if not m.bot)
    if stat == "bots":
        return sum(1 for m in guild.members if m.bot)
    if stat == "online":
        return sum(
            1 for m in guild.members
            if m.status != discord.Status.offline and not m.bot
        )
    if stat == "boosts":
        return guild.premium_subscription_count or 0
    if stat == "roles":
        return len(guild.roles)
    if stat == "channels":
        return len(guild.channels)
    return "?"


class ServerStats(GuildOnlyCog):
    """Canais de voz que exibem estatísticas do servidor em tempo real."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # { "guild_id": { "stat_key": {"channel_id": int, "template": str} } }
        self._db: dict = _load()
        self.update_loop.start()

    def cog_unload(self):
        self.update_loop.cancel()

    # ── /stats-add ────────────────────────────────────────────────────────────
    @app_commands.command(name="stats-add", description="Cria um canal de voz com uma estatística do servidor")
    @GUILD_ONLY_INSTALL
    @GUILD_ONLY_CONTEXT
    @app_commands.describe(
        stat="Qual estatística exibir",
        template="Formato do nome (use {value} onde o número vai aparecer)",
    )
    @app_commands.choices(stat=STAT_CHOICES)
    @app_commands.checks.has_permissions(manage_channels=True)
    async def stats_add(
        self,
        interaction: discord.Interaction,
        stat: app_commands.Choice[str],
        template: str = "",
    ):
        await interaction.response.defer(ephemeral=True)
        gid = str(interaction.guild_id)
        tmpl = template or DEFAULT_TEMPLATES.get(stat.value, f"📊 {stat.name}: {{value}}")

        # Calcula valor atual
        value = _get_stat_value(interaction.guild, stat.value)
        name = tmpl.replace("{value}", str(value))

        # Cria o canal de voz (somente leitura para @everyone)
        overwrites = {interaction.guild.default_role: discord.PermissionOverwrite(connect=False)}
        try:
            vc = await interaction.guild.create_voice_channel(
                name=name, overwrites=overwrites, reason="LiraVT ServerStats"
            )
        except discord.Forbidden:
            await interaction.followup.send("❌ Sem permissão para criar canais de voz.", ephemeral=True)
            return

        self._db.setdefault(gid, {})[stat.value] = {
            "channel_id": vc.id,
            "template":   tmpl,
        }
        _save(self._db)

        await interaction.followup.send(
            f"✅ Canal criado: **{vc.name}**\nAtualizado automaticamente a cada 5 min.",
            ephemeral=True,
        )
        logger.info(f"[STATS] Canal '{stat.value}' criado em {interaction.guild}: #{vc.name}")

    # ── /stats-remove ─────────────────────────────────────────────────────────
    @app_commands.command(name="stats-remove", description="Remove um canal de estatísticas")
    @GUILD_ONLY_INSTALL
    @GUILD_ONLY_CONTEXT
    @app_commands.describe(stat="Qual estatística remover")
    @app_commands.choices(stat=STAT_CHOICES)
    @app_commands.checks.has_permissions(manage_channels=True)
    async def stats_remove(self, interaction: discord.Interaction, stat: app_commands.Choice[str]):
        gid = str(interaction.guild_id)
        guild_stats = self._db.get(gid, {})

        if stat.value not in guild_stats:
            await interaction.response.send_message(
                f"❌ Nenhum canal de `{stat.name}` configurado.", ephemeral=True
            )
            return

        channel_id = guild_stats[stat.value]["channel_id"]
        vc = interaction.guild.get_channel(channel_id)
        if vc:
            try:
                await vc.delete(reason="LiraVT ServerStats removido")
            except Exception:
                pass

        del guild_stats[stat.value]
        if not guild_stats:
            del self._db[gid]
        else:
            self._db[gid] = guild_stats
        _save(self._db)

        await interaction.response.send_message(
            f"✅ Canal de `{stat.name}` removido.", ephemeral=True
        )
        logger.info(f"[STATS] Canal '{stat.value}' removido de {interaction.guild}")

    # ── /stats-list ───────────────────────────────────────────────────────────
    @app_commands.command(name="stats-list", description="Lista os canais de estatísticas deste servidor")
    @GUILD_ONLY_INSTALL
    @GUILD_ONLY_CONTEXT
    async def stats_list(self, interaction: discord.Interaction):
        gid = str(interaction.guild_id)
        guild_stats = self._db.get(gid, {})

        if not guild_stats:
            await interaction.response.send_message(
                "📊 Nenhum canal de estatísticas configurado. Use `/stats-add`.", ephemeral=True
            )
            return

        lines = []
        for key, data in guild_stats.items():
            ch = interaction.guild.get_channel(data["channel_id"])
            ch_ref = ch.mention if ch else f"(canal removido: {data['channel_id']})"
            lines.append(f"• **{key}** → {ch_ref}\n  template: `{data['template']}`")

        embed = discord.Embed(
            title="📊 Canais de Estatísticas",
            description="\n".join(lines),
            color=0x5865F2,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── Task: atualiza os canais a cada 5 minutos ─────────────────────────────
    @tasks.loop(minutes=5)
    async def update_loop(self):
        for gid, guild_stats in list(self._db.items()):
            guild = self.bot.get_guild(int(gid))
            if not guild:
                continue

            for stat_key, data in list(guild_stats.items()):
                vc = guild.get_channel(data["channel_id"])
                if not vc:
                    continue

                value = _get_stat_value(guild, stat_key)
                new_name = data["template"].replace("{value}", str(value))

                if vc.name != new_name:
                    try:
                        await vc.edit(name=new_name, reason="LiraVT ServerStats update")
                    except discord.Forbidden:
                        logger.warning(f"[STATS] Sem permissão para editar canal {vc.id} em {guild.name}")
                    except Exception as e:
                        logger.warning(f"[STATS] Erro ao atualizar {vc.id}: {e}")

    @update_loop.before_loop
    async def before_loop(self):
        await self.bot.wait_until_ready()

    # ── Erros de permissão ────────────────────────────────────────────────────
    @stats_add.error
    @stats_remove.error
    async def perm_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ Você precisa da permissão **Gerenciar Canais**.", ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(ServerStats(bot))
    logger.info("[DISCORD] ✅ Cog ServerStats carregada")
