"""
╔══════════════════════════════════════════════════════════════╗
║  LiraVT · Cog: Reaction Roles                               ║
║  Dá/remove cargos baseado em reactions em mensagens         ║
╚══════════════════════════════════════════════════════════════╝
"""
import discord
from discord.ext import commands
from discord import app_commands
import json, os
from ..slash_meta import GUILD_ONLY_CONTEXT, GUILD_ONLY_INSTALL, GuildOnlyCog
from ..constants import logger, EMOJI

RR_FILE = os.path.join("data", "reactionroles.json")

# Modos de funcionamento
MODE_NORMAL  = "normal"   # toggle: adiciona/remove ao reagir/remover
MODE_UNIQUE  = "unique"   # só pode ter 1 dos cargos da mensagem
MODE_VERIFY  = "verify"   # reação adiciona cargo, não pode remover


def _load() -> dict:
    if os.path.exists(RR_FILE):
        try:
            with open(RR_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save(data: dict):
    os.makedirs("data", exist_ok=True)
    with open(RR_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


MODE_CHOICES = [
    app_commands.Choice(name="Normal (toggle)",           value=MODE_NORMAL),
    app_commands.Choice(name="Único (só 1 cargo por vez)",value=MODE_UNIQUE),
    app_commands.Choice(name="Verificação (só adiciona)", value=MODE_VERIFY),
]


class ReactionRoles(GuildOnlyCog):
    """Atribui cargos automaticamente via reaction em mensagens."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # { "msg_id": {"mode": str, "guild_id": int, "channel_id": int,
        #              "roles": {"emoji": role_id} } }
        self._db: dict = _load()

    # ── /rr-add ───────────────────────────────────────────────────────────────
    @app_commands.command(name="rr-add", description="Adiciona um reaction role a uma mensagem")
    @GUILD_ONLY_INSTALL
    @GUILD_ONLY_CONTEXT
    @app_commands.describe(
        msg_id="ID da mensagem alvo",
        emoji="Emoji que o usuário vai reagir",
        cargo="Cargo que será dado ao reagir",
        modo="Modo de funcionamento",
    )
    @app_commands.choices(modo=MODE_CHOICES)
    @app_commands.checks.has_permissions(manage_roles=True)
    async def rr_add(
        self,
        interaction: discord.Interaction,
        msg_id: str,
        emoji: str,
        cargo: discord.Role,
        modo: app_commands.Choice[str] = None,
    ):
        await interaction.response.defer(ephemeral=True)

        # Valida a mensagem
        try:
            msg = await interaction.channel.fetch_message(int(msg_id))
        except Exception:
            await interaction.followup.send("❌ Mensagem não encontrada neste canal.", ephemeral=True)
            return

        # Valida hierarquia de cargo
        if cargo >= interaction.guild.me.top_role:
            await interaction.followup.send(
                "❌ Esse cargo é maior ou igual ao cargo da Lira. Mova o cargo da Lira acima.",
                ephemeral=True,
            )
            return

        mode_val = modo.value if modo else MODE_NORMAL
        mid = str(msg.id)

        entry = self._db.setdefault(mid, {
            "mode":       mode_val,
            "guild_id":   interaction.guild_id,
            "channel_id": interaction.channel_id,
            "roles":      {},
        })
        entry["roles"][emoji] = cargo.id
        entry["mode"] = mode_val
        _save(self._db)

        # Adiciona a reaction na mensagem
        try:
            await msg.add_reaction(emoji)
        except Exception as e:
            await interaction.followup.send(
                f"⚠️ Reaction role salvo, mas não consegui adicionar o emoji: {e}", ephemeral=True
            )
            return

        await interaction.followup.send(
            f"✅ Reaction Role criado!\n"
            f"Emoji: {emoji} → {cargo.mention}\n"
            f"Modo: `{mode_val}`",
            ephemeral=True,
        )
        logger.info(f"[RR] Adicionado: {emoji}→{cargo.name} em msg {mid} (modo: {mode_val})")

    # ── /rr-remove ────────────────────────────────────────────────────────────
    @app_commands.command(name="rr-remove", description="Remove um reaction role de uma mensagem")
    @GUILD_ONLY_INSTALL
    @GUILD_ONLY_CONTEXT
    @app_commands.describe(
        msg_id="ID da mensagem",
        emoji="Emoji do reaction role a remover",
    )
    @app_commands.checks.has_permissions(manage_roles=True)
    async def rr_remove(self, interaction: discord.Interaction, msg_id: str, emoji: str):
        mid = str(msg_id)
        if mid not in self._db or emoji not in self._db[mid]["roles"]:
            await interaction.response.send_message(
                "❌ Reaction role não encontrado.", ephemeral=True
            )
            return

        del self._db[mid]["roles"][emoji]
        if not self._db[mid]["roles"]:
            del self._db[mid]
        _save(self._db)

        await interaction.response.send_message(
            f"✅ Reaction role `{emoji}` removido da mensagem `{msg_id}`.", ephemeral=True
        )
        logger.info(f"[RR] Removido: {emoji} de msg {mid}")

    # ── /rr-list ──────────────────────────────────────────────────────────────
    @app_commands.command(name="rr-list", description="Lista todos os reaction roles deste servidor")
    @GUILD_ONLY_INSTALL
    @GUILD_ONLY_CONTEXT
    @app_commands.checks.has_permissions(manage_roles=True)
    async def rr_list(self, interaction: discord.Interaction):
        guild_entries = {
            mid: entry for mid, entry in self._db.items()
            if entry["guild_id"] == interaction.guild_id
        }

        if not guild_entries:
            await interaction.response.send_message(
                "📋 Nenhum reaction role configurado. Use `/rr-add`.", ephemeral=True
            )
            return

        embed = discord.Embed(title="🎭 Reaction Roles", color=0x5865F2)
        for mid, entry in guild_entries.items():
            lines = []
            for em, rid in entry["roles"].items():
                role = interaction.guild.get_role(rid)
                lines.append(f"{em} → {role.mention if role else f'@{rid}'}")
            ch = interaction.guild.get_channel(entry["channel_id"])
            embed.add_field(
                name=f"Msg `{mid}` em {ch.mention if ch else '?'} ({entry['mode']})",
                value="\n".join(lines) or "—",
                inline=False,
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── Listener: reaction add ─────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return

        mid = str(payload.message_id)
        entry = self._db.get(mid)
        if not entry:
            return

        emoji = str(payload.emoji)
        role_id = entry["roles"].get(emoji)
        if not role_id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        member = guild.get_member(payload.user_id)
        if not member:
            return

        role = guild.get_role(role_id)
        if not role:
            return

        try:
            # Modo UNIQUE: remove outros cargos da mesma mensagem antes
            if entry["mode"] == MODE_UNIQUE:
                roles_to_remove = [
                    guild.get_role(rid) for em, rid in entry["roles"].items()
                    if em != emoji and rid != role_id
                ]
                for r in roles_to_remove:
                    if r and r in member.roles:
                        await member.remove_roles(r, reason="Reaction Role (único)")
                        # Remove a reaction do emoji anterior
                        try:
                            ch = guild.get_channel(entry["channel_id"])
                            msg = await ch.fetch_message(payload.message_id)
                            for em, rid in entry["roles"].items():
                                if rid != role_id and em != emoji:
                                    await msg.remove_reaction(em, member)
                        except Exception:
                            pass

            await member.add_roles(role, reason=f"Reaction Role: {emoji}")
            logger.info(f"[RR] +{role.name} → {member} via {emoji}")
        except discord.Forbidden:
            logger.warning(f"[RR] Sem permissão para dar {role.name} a {member}")

    # ── Listener: reaction remove ──────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return

        mid = str(payload.message_id)
        entry = self._db.get(mid)
        if not entry:
            return

        # Modo VERIFY não remove ao desreagir
        if entry["mode"] == MODE_VERIFY:
            return

        emoji = str(payload.emoji)
        role_id = entry["roles"].get(emoji)
        if not role_id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        member = guild.get_member(payload.user_id)
        if not member:
            return

        role = guild.get_role(role_id)
        if role and role in member.roles:
            try:
                await member.remove_roles(role, reason=f"Reaction Role removido: {emoji}")
                logger.info(f"[RR] -{role.name} → {member} via {emoji}")
            except discord.Forbidden:
                logger.warning(f"[RR] Sem permissão para remover {role.name} de {member}")

    # ── Erro de permissão ─────────────────────────────────────────────────────
    @rr_add.error
    @rr_remove.error
    @rr_list.error
    async def perm_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ Você precisa da permissão **Gerenciar Cargos**.", ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(ReactionRoles(bot))
    logger.info("[DISCORD] ✅ Cog ReactionRoles carregada")
