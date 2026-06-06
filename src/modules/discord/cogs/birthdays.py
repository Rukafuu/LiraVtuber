"""
╔══════════════════════════════════════════════════════════════╗
║  LiraVT · Cog: Birthdays (Aniversários)                    ║
║  Registra aniversários e parabeniza no dia certo            ║
╚══════════════════════════════════════════════════════════════╝
"""
import discord
from discord.ext import commands, tasks
from discord import app_commands
import json, os
from datetime import datetime, timezone, date
from ..slash_meta import GUILD_ONLY_CONTEXT, GUILD_ONLY_INSTALL, GuildOnlyCog
from ..constants import logger, EMOJI

BDAY_FILE   = os.path.join("data", "birthdays.json")
CONFIG_FILE = os.path.join("data", "birthdays_config.json")


def _load(path: str) -> dict:
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save(path: str, data: dict):
    os.makedirs("data", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class Birthdays(GuildOnlyCog):
    """Registra aniversários e parabeniza automaticamente no dia."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # { "user_id": {"day": int, "month": int, "year": int|null} }
        self._bdays: dict  = _load(BDAY_FILE)
        # { "guild_id": {"channel_id": int, "role_id": int|null, "message": str} }
        self._config: dict = _load(CONFIG_FILE)
        self._already_wished: set[str] = set()   # "user_id-YYYY-MM-DD"
        self.check_loop.start()

    def cog_unload(self):
        self.check_loop.cancel()

    # ── /aniversario registrar ─────────────────────────────────────────────────
    @app_commands.command(name="aniversario", description="Registra sua data de aniversário")
    @GUILD_ONLY_INSTALL
    @GUILD_ONLY_CONTEXT
    @app_commands.describe(
        dia="Dia do seu aniversário (1-31)",
        mes="Mês do seu aniversário (1-12)",
        ano="Ano de nascimento (opcional, para calcular idade)",
    )
    async def register(
        self,
        interaction: discord.Interaction,
        dia: app_commands.Range[int, 1, 31],
        mes: app_commands.Range[int, 1, 12],
        ano: int | None = None,
    ):
        # Valida a data
        try:
            date(ano or 2000, mes, dia)
        except ValueError:
            await interaction.response.send_message(
                "❌ Data inválida! Verifique o dia e mês.", ephemeral=True
            )
            return

        uid = str(interaction.user.id)
        self._bdays[uid] = {"day": dia, "month": mes, "year": ano}
        _save(BDAY_FILE, self._bdays)

        mes_nome = [
            "", "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
            "Jul", "Ago", "Set", "Out", "Nov", "Dez"
        ][mes]

        embed = discord.Embed(
            title=f"{EMOJI.get('birthday', '🎂')} Aniversário registrado!",
            description=f"**{dia} de {mes_nome}**" + (f" de {ano}" if ano else ""),
            color=0xf5a3c7,
        )
        embed.set_thumbnail(url=str(interaction.user.display_avatar.url))
        embed.set_footer(text="Você será parabenizado(a) automaticamente no seu dia! 🎉")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        logger.info(f"[BDAY] {interaction.user} registrou aniversário: {dia}/{mes}/{ano}")

    # ── /aniversario-ver ───────────────────────────────────────────────────────
    @app_commands.command(name="aniversario-ver", description="Veja o aniversário de um usuário")
    @GUILD_ONLY_INSTALL
    @GUILD_ONLY_CONTEXT
    @app_commands.describe(usuario="Usuário para consultar (padrão: você mesmo)")
    async def view(self, interaction: discord.Interaction, usuario: discord.Member | None = None):
        target = usuario or interaction.user
        uid = str(target.id)

        if uid not in self._bdays:
            await interaction.response.send_message(
                f"❌ **{target.display_name}** ainda não registrou o aniversário.",
                ephemeral=True
            )
            return

        entry = self._bdays[uid]
        mes_nome = [
            "", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
            "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
        ][entry["month"]]

        desc = f"**{entry['day']} de {mes_nome}**"
        if entry.get("year"):
            hoje = date.today()
            idade = hoje.year - entry["year"] - (
                (hoje.month, hoje.day) < (entry["month"], entry["day"])
            )
            desc += f" de {entry['year']} *(~{idade} anos)*"

        embed = discord.Embed(
            title=f"🎂 Aniversário de {target.display_name}",
            description=desc,
            color=0xf5a3c7,
        )
        embed.set_thumbnail(url=str(target.display_avatar.url))
        await interaction.response.send_message(embed=embed)

    # ── /aniversario-canal ─────────────────────────────────────────────────────
    @app_commands.command(name="aniversario-canal", description="Define o canal onde a Lira vai parabenizar")
    @GUILD_ONLY_INSTALL
    @GUILD_ONLY_CONTEXT
    @app_commands.describe(
        canal="Canal de texto para mensagens de aniversário",
        cargo="Cargo temporário dado no dia do aniversário (opcional)",
        mensagem="Mensagem personalizada ({user} = menção do usuário)",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def set_channel(
        self,
        interaction: discord.Interaction,
        canal: discord.TextChannel,
        cargo: discord.Role | None = None,
        mensagem: str = "🎉 Hoje é aniversário de {user}! Parabenizem! 🎂",
    ):
        gid = str(interaction.guild_id)
        self._config[gid] = {
            "channel_id": canal.id,
            "role_id":    cargo.id if cargo else None,
            "message":    mensagem,
        }
        _save(CONFIG_FILE, self._config)
        resp = f"✅ Canal de aniversários: {canal.mention}"
        if cargo:
            resp += f"\n🎭 Cargo do dia: {cargo.mention}"
        await interaction.response.send_message(resp, ephemeral=True)
        logger.info(f"[BDAY] Config salva em {interaction.guild.name}")

    # ── /proximos-aniversarios ─────────────────────────────────────────────────
    @app_commands.command(name="proximos-aniversarios", description="Lista os próximos 5 aniversários do servidor")
    @GUILD_ONLY_INSTALL
    @GUILD_ONLY_CONTEXT
    async def upcoming(self, interaction: discord.Interaction):
        await interaction.response.defer()
        hoje = date.today()

        upcoming = []
        for uid, entry in self._bdays.items():
            member = interaction.guild.get_member(int(uid))
            if not member:
                continue
            try:
                # Data deste ano ou próximo ano
                bday_this_year = date(hoje.year, entry["month"], entry["day"])
                if bday_this_year < hoje:
                    bday_this_year = date(hoje.year + 1, entry["month"], entry["day"])
                days_left = (bday_this_year - hoje).days
                upcoming.append((days_left, member, entry))
            except ValueError:
                continue

        upcoming.sort(key=lambda x: x[0])
        upcoming = upcoming[:5]

        if not upcoming:
            await interaction.followup.send("😢 Nenhum membro registrou aniversário ainda.")
            return

        embed = discord.Embed(title="🎂 Próximos aniversários", color=0xf5a3c7)
        mes_nomes = ["", "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
                     "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

        for days_left, member, entry in upcoming:
            if days_left == 0:
                label = "🎉 **HOJE!**"
            elif days_left == 1:
                label = "amanhã"
            else:
                label = f"em {days_left} dias"
            embed.add_field(
                name=f"{member.display_name}",
                value=f"{entry['day']}/{mes_nomes[entry['month']]} — {label}",
                inline=False,
            )
        await interaction.followup.send(embed=embed)

    # ── Task: verifica aniversários 1x por hora ────────────────────────────────
    @tasks.loop(hours=1)
    async def check_loop(self):
        hoje = date.today()

        for uid, entry in list(self._bdays.items()):
            if entry["day"] != hoje.day or entry["month"] != hoje.month:
                continue

            key = f"{uid}-{hoje.isoformat()}"
            if key in self._already_wished:
                continue
            self._already_wished.add(key)

            # Parabeniza em todos os servidores configurados onde o usuário está
            for gid, cfg in self._config.items():
                guild = self.bot.get_guild(int(gid))
                if not guild:
                    continue
                member = guild.get_member(int(uid))
                if not member:
                    continue

                channel = guild.get_channel(cfg["channel_id"])
                if not channel:
                    continue

                # Monta mensagem
                msg_text = cfg["message"].replace("{user}", member.mention)

                embed = discord.Embed(
                    title="🎂 Feliz Aniversário!",
                    description=msg_text,
                    color=0xf5a3c7,
                )
                if entry.get("year"):
                    idade = hoje.year - entry["year"]
                    embed.set_footer(text=f"🎈 Completando {idade} anos hoje!")
                embed.set_thumbnail(url=str(member.display_avatar.url))

                try:
                    await channel.send(embed=embed)
                    logger.info(f"[BDAY] 🎂 Parabenizando {member} em {guild.name}")
                except Exception as e:
                    logger.warning(f"[BDAY] Erro ao enviar parabéns: {e}")

                # Cargo temporário do aniversário
                if cfg.get("role_id"):
                    role = guild.get_role(cfg["role_id"])
                    if role:
                        try:
                            await member.add_roles(role, reason="Cargo de Aniversário")
                        except Exception:
                            pass

    @check_loop.before_loop
    async def before_loop(self):
        await self.bot.wait_until_ready()

    @set_channel.error
    async def perm_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ Você precisa de **Gerenciar Servidor**.", ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Birthdays(bot))
    logger.info("[DISCORD] ✅ Cog Birthdays carregada")
