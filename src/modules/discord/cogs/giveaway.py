"""
╔══════════════════════════════════════════════════════════════╗
║  LiraVT · Cog: Giveaway                                     ║
║  Sorteios com timer, reação e múltiplos ganhadores          ║
╚══════════════════════════════════════════════════════════════╝
"""
import discord
from discord.ext import commands, tasks
from discord import app_commands
import json, os, random, asyncio
from datetime import datetime, timezone, timedelta
from ..slash_meta import GUILD_ONLY_CONTEXT, GUILD_ONLY_INSTALL, GuildOnlyCog
from ..constants import logger, EMOJI

GIVEAWAY_FILE = os.path.join("data", "giveaways.json")
GIVEAWAY_EMOJI = "🎉"


def _load() -> dict:
    if os.path.exists(GIVEAWAY_FILE):
        try:
            with open(GIVEAWAY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save(data: dict):
    os.makedirs("data", exist_ok=True)
    with open(GIVEAWAY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _parse_duration(text: str) -> int | None:
    """Converte '10m', '2h', '1d' em segundos."""
    text = text.strip().lower()
    multipliers = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    if text[-1] in multipliers and text[:-1].isdigit():
        return int(text[:-1]) * multipliers[text[-1]]
    return None


def _build_embed(entry: dict, ended: bool = False) -> discord.Embed:
    ends_at = datetime.fromisoformat(entry["ends_at"])
    ts = int(ends_at.timestamp())

    color = 0xED4245 if ended else 0xF5D800
    title = f"🎊 GIVEAWAY {'— ENCERRADO' if ended else ''}"

    embed = discord.Embed(title=title, color=color)
    embed.add_field(name="🎁 Prêmio", value=f"**{entry['prize']}**", inline=False)
    embed.add_field(name="🏆 Ganhadores", value=str(entry["winners_count"]), inline=True)
    embed.add_field(
        name="⏰ " + ("Encerrou em" if ended else "Encerra em"),
        value=f"<t:{ts}:R>",
        inline=True,
    )
    embed.add_field(name="👤 Criado por", value=entry["host"], inline=True)

    if entry.get("require_role"):
        embed.add_field(name="📌 Cargo necessário", value=f"<@&{entry['require_role']}>", inline=True)

    participants = len(entry.get("participants", []))
    embed.add_field(name="👥 Participantes", value=str(participants), inline=True)

    if ended:
        winners = entry.get("winners", [])
        if winners:
            embed.add_field(
                name="🥳 Ganhadores",
                value="\n".join(f"<@{w}>" for w in winners),
                inline=False,
            )
        else:
            embed.add_field(name="😢 Resultado", value="Ninguém participou...", inline=False)

    embed.set_footer(text=f"ID: {entry['id']} | Reaja com {GIVEAWAY_EMOJI} para participar!")
    return embed


class Giveaway(GuildOnlyCog):
    """Sistema de sorteios com reação, timer e múltiplos ganhadores."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._db: dict = _load()
        self.check_loop.start()

    def cog_unload(self):
        self.check_loop.cancel()

    # ── /giveaway criar ────────────────────────────────────────────────────────
    @app_commands.command(name="giveaway", description="Cria um novo sorteio")
    @GUILD_ONLY_INSTALL
    @GUILD_ONLY_CONTEXT
    @app_commands.describe(
        premio="O que vai ser sorteado",
        duracao="Duração: ex. 30m, 2h, 1d",
        ganhadores="Quantidade de ganhadores (padrão: 1)",
        cargo="Cargo obrigatório para participar (opcional)",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def create(
        self,
        interaction: discord.Interaction,
        premio: str,
        duracao: str,
        ganhadores: app_commands.Range[int, 1, 20] = 1,
        cargo: discord.Role | None = None,
    ):
        secs = _parse_duration(duracao)
        if not secs or secs < 10:
            await interaction.response.send_message(
                "❌ Duração inválida! Use: `10s`, `30m`, `2h`, `1d`", ephemeral=True
            )
            return

        ends_at = datetime.now(timezone.utc) + timedelta(seconds=secs)
        gid = f"{interaction.guild_id}-{int(ends_at.timestamp())}"

        entry = {
            "id":            gid,
            "prize":         premio,
            "winners_count": ganhadores,
            "host":          interaction.user.mention,
            "ends_at":       ends_at.isoformat(),
            "channel_id":    interaction.channel_id,
            "guild_id":      interaction.guild_id,
            "msg_id":        None,
            "participants":  [],
            "winners":       [],
            "ended":         False,
            "require_role":  cargo.id if cargo else None,
        }

        embed = _build_embed(entry)
        await interaction.response.send_message("✅ Criando sorteio...", ephemeral=True)
        msg = await interaction.channel.send(embed=embed)
        await msg.add_reaction(GIVEAWAY_EMOJI)

        entry["msg_id"] = msg.id
        self._db[gid] = entry
        _save(self._db)
        logger.info(f"[GIVEAWAY] Criado: {premio} por {interaction.user} | {duracao} | {ganhadores} ganhadores")

    # ── /giveaway-reroll ───────────────────────────────────────────────────────
    @app_commands.command(name="giveaway-reroll", description="Resorteia um giveaway encerrado")
    @GUILD_ONLY_INSTALL
    @GUILD_ONLY_CONTEXT
    @app_commands.describe(id="ID do giveaway (mostrado no footer)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def reroll(self, interaction: discord.Interaction, id: str):
        entry = self._db.get(id)
        if not entry or not entry.get("ended"):
            await interaction.response.send_message(
                "❌ Giveaway não encontrado ou ainda está ativo.", ephemeral=True
            )
            return

        pool = entry.get("participants", [])
        if not pool:
            await interaction.response.send_message("😢 Ninguém participou.", ephemeral=True)
            return

        n = min(entry["winners_count"], len(pool))
        new_winners = random.sample(pool, n)
        entry["winners"] = new_winners
        _save(self._db)

        mentions = " ".join(f"<@{w}>" for w in new_winners)
        await interaction.response.send_message(
            f"🎊 **Novo(s) ganhador(es):** {mentions}\nParabéns! 🎁"
        )
        logger.info(f"[GIVEAWAY] Reroll {id}: {new_winners}")

    # ── /giveaway-encerrar ─────────────────────────────────────────────────────
    @app_commands.command(name="giveaway-encerrar", description="Encerra um giveaway antes do tempo")
    @GUILD_ONLY_INSTALL
    @GUILD_ONLY_CONTEXT
    @app_commands.describe(id="ID do giveaway")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def force_end(self, interaction: discord.Interaction, id: str):
        entry = self._db.get(id)
        if not entry or entry.get("ended"):
            await interaction.response.send_message(
                "❌ Giveaway não encontrado ou já encerrado.", ephemeral=True
            )
            return

        await self._end_giveaway(id, entry)
        await interaction.response.send_message("✅ Giveaway encerrado!", ephemeral=True)

    # ── Listener de reactions ─────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id or str(payload.emoji) != GIVEAWAY_EMOJI:
            return

        entry = self._find_by_msg(payload.message_id)
        if not entry or entry["ended"]:
            return

        uid = str(payload.user_id)

        # Verifica cargo necessário
        if entry.get("require_role"):
            guild = self.bot.get_guild(entry["guild_id"])
            member = guild.get_member(payload.user_id) if guild else None
            if not member or not any(r.id == entry["require_role"] for r in member.roles):
                # Remove a reação silenciosamente
                try:
                    ch = self.bot.get_channel(entry["channel_id"])
                    msg = await ch.fetch_message(entry["msg_id"])
                    user = self.bot.get_user(payload.user_id)
                    if user:
                        await msg.remove_reaction(GIVEAWAY_EMOJI, user)
                except Exception:
                    pass
                return

        if uid not in entry["participants"]:
            entry["participants"].append(uid)
            _save(self._db)
            # Atualiza embed com contagem
            await self._update_embed(entry)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id or str(payload.emoji) != GIVEAWAY_EMOJI:
            return

        entry = self._find_by_msg(payload.message_id)
        if not entry or entry["ended"]:
            return

        uid = str(payload.user_id)
        if uid in entry["participants"]:
            entry["participants"].remove(uid)
            _save(self._db)
            await self._update_embed(entry)

    # ── Task: verifica giveaways expirados a cada 30s ─────────────────────────
    @tasks.loop(seconds=30)
    async def check_loop(self):
        now = datetime.now(timezone.utc)
        for gid, entry in list(self._db.items()):
            if entry["ended"]:
                continue
            ends_at = datetime.fromisoformat(entry["ends_at"])
            if ends_at.tzinfo is None:
                ends_at = ends_at.replace(tzinfo=timezone.utc)
            if now >= ends_at:
                await self._end_giveaway(gid, entry)

    async def _end_giveaway(self, gid: str, entry: dict):
        entry["ended"] = True
        pool = entry.get("participants", [])
        n = min(entry["winners_count"], len(pool))
        winners = random.sample(pool, n) if pool else []
        entry["winners"] = winners
        _save(self._db)

        # Atualiza o embed
        try:
            ch = self.bot.get_channel(entry["channel_id"])
            if ch:
                msg = await ch.fetch_message(entry["msg_id"])
                await msg.edit(embed=_build_embed(entry, ended=True))

                if winners:
                    mentions = " ".join(f"<@{w}>" for w in winners)
                    await ch.send(
                        f"🎊 O sorteio **{entry['prize']}** encerrou!\n"
                        f"🏆 Ganhador(es): {mentions}\nParabéns! 🎁",
                        reference=msg,
                    )
                else:
                    await ch.send(
                        f"😢 O sorteio **{entry['prize']}** encerrou sem participantes.",
                        reference=msg,
                    )
        except Exception as e:
            logger.warning(f"[GIVEAWAY] Erro ao encerrar {gid}: {e}")

        logger.info(f"[GIVEAWAY] Encerrado: {gid} | Ganhadores: {winners}")

    async def _update_embed(self, entry: dict):
        try:
            ch = self.bot.get_channel(entry["channel_id"])
            if ch:
                msg = await ch.fetch_message(entry["msg_id"])
                await msg.edit(embed=_build_embed(entry))
        except Exception:
            pass

    def _find_by_msg(self, msg_id: int) -> dict | None:
        for entry in self._db.values():
            if entry.get("msg_id") == msg_id:
                return entry
        return None

    @check_loop.before_loop
    async def before_loop(self):
        await self.bot.wait_until_ready()

    @create.error
    @reroll.error
    @force_end.error
    async def perm_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ Você precisa de **Gerenciar Servidor**.", ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Giveaway(bot))
    logger.info("[DISCORD] ✅ Cog Giveaway carregada")
