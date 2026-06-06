"""
╔══════════════════════════════════════════════════════════════╗
║  LiraVT · Cog: Sugestões                                    ║
║  Cria embeds de sugestão com votação 👍/👎                  ║
╚══════════════════════════════════════════════════════════════╝
"""
import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from datetime import datetime, timezone
from ..slash_meta import GUILD_ONLY_CONTEXT, GUILD_ONLY_INSTALL, GuildOnlyCog
from ..constants import logger, EMOJI

SUGGESTIONS_FILE = os.path.join("data", "suggestions.json")
SUGGESTIONS_CONFIG_FILE = os.path.join("data", "suggestions_config.json")

VOTE_UP   = "👍"
VOTE_DOWN = "👎"

STATUS_COLORS = {
    "pending":  0x5865F2,   # azul Discord
    "approved": 0x57F287,   # verde
    "denied":   0xED4245,   # vermelho
    "review":   0xFEE75C,   # amarelo
}

STATUS_LABELS = {
    "pending":  "⏳ Aguardando análise",
    "approved": "✅ Aprovada",
    "denied":   "❌ Negada",
    "review":   "🔎 Em análise",
}


def _load_suggestions() -> dict:
    if os.path.exists(SUGGESTIONS_FILE):
        try:
            with open(SUGGESTIONS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_suggestions(data: dict):
    os.makedirs("data", exist_ok=True)
    with open(SUGGESTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _load_config() -> dict:
    if os.path.exists(SUGGESTIONS_CONFIG_FILE):
        try:
            with open(SUGGESTIONS_CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_config(data: dict):
    os.makedirs("data", exist_ok=True)
    with open(SUGGESTIONS_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _build_embed(entry: dict, suggestion_id: str) -> discord.Embed:
    status = entry.get("status", "pending")
    embed = discord.Embed(
        title=f"💡 Sugestão #{suggestion_id}",
        description=entry["text"],
        color=STATUS_COLORS.get(status, 0x5865F2),
        timestamp=datetime.fromisoformat(entry["created_at"]) if "created_at" in entry else None,
    )
    embed.set_author(name=entry["author_name"], icon_url=entry.get("author_avatar"))
    embed.add_field(name="Status", value=STATUS_LABELS.get(status, status), inline=True)
    embed.add_field(name="Votos", value=f"{VOTE_UP} {entry.get('up', 0)}  {VOTE_DOWN} {entry.get('down', 0)}", inline=True)

    if entry.get("admin_note"):
        embed.add_field(name="📝 Nota da equipe", value=entry["admin_note"], inline=False)

    embed.set_footer(text=f"ID: {suggestion_id}")
    return embed


class Suggestions(GuildOnlyCog):
    """Sistema de sugestões com votação e gerenciamento por admins."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._db: dict     = _load_suggestions()   # { "id": { ...dados } }
        self._config: dict = _load_config()         # { "guild_id": { "channel_id": int } }
        self._counter: int = max((int(k) for k in self._db if k.isdigit()), default=0)

    def _next_id(self) -> str:
        self._counter += 1
        return str(self._counter)

    def _get_channel_id(self, guild_id: int) -> int | None:
        return self._config.get(str(guild_id), {}).get("channel_id")

    # ── /sugestao-canal ────────────────────────────────────────────────────────
    @app_commands.command(name="sugestao-canal", description="Define o canal onde as sugestões serão postadas")
    @GUILD_ONLY_INSTALL
    @GUILD_ONLY_CONTEXT
    @app_commands.describe(canal="Canal de texto para receber sugestões")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def set_channel(self, interaction: discord.Interaction, canal: discord.TextChannel):
        gid = str(interaction.guild_id)
        self._config.setdefault(gid, {})["channel_id"] = canal.id
        _save_config(self._config)
        await interaction.response.send_message(
            f"✅ Canal de sugestões definido: {canal.mention}", ephemeral=True
        )
        logger.info(f"[SUGGEST] Canal definido em {interaction.guild}: #{canal.name}")

    # ── /sugerir ───────────────────────────────────────────────────────────────
    @app_commands.command(name="sugerir", description="Envia uma sugestão para votação da comunidade")
    @GUILD_ONLY_INSTALL
    @GUILD_ONLY_CONTEXT
    @app_commands.describe(texto="Sua sugestão (seja específico!)")
    async def suggest(self, interaction: discord.Interaction, texto: str):
        channel_id = self._get_channel_id(interaction.guild_id)
        if not channel_id:
            await interaction.response.send_message(
                "❌ Nenhum canal de sugestões configurado. Um admin deve usar `/sugestao-canal`.",
                ephemeral=True,
            )
            return

        channel = interaction.guild.get_channel(channel_id)
        if not channel:
            await interaction.response.send_message(
                "❌ Canal de sugestões não encontrado. Contate um admin.", ephemeral=True
            )
            return

        sid = self._next_id()
        entry = {
            "text":         texto,
            "author_id":    str(interaction.user.id),
            "author_name":  interaction.user.display_name,
            "author_avatar": str(interaction.user.display_avatar.url),
            "status":       "pending",
            "up":           0,
            "down":         0,
            "voters_up":    [],
            "voters_down":  [],
            "msg_id":       None,
            "channel_id":   channel_id,
            "admin_note":   None,
            "created_at":   datetime.now(timezone.utc).isoformat(),
        }

        embed = _build_embed(entry, sid)
        msg = await channel.send(embed=embed)
        await msg.add_reaction(VOTE_UP)
        await msg.add_reaction(VOTE_DOWN)

        entry["msg_id"] = msg.id
        self._db[sid] = entry
        _save_suggestions(self._db)

        await interaction.response.send_message(
            f"✅ Sua sugestão **#{sid}** foi enviada para {channel.mention}!", ephemeral=True
        )
        logger.info(f"[SUGGEST] #{sid} enviada por {interaction.user}: {texto[:60]}")

    # ── /sugestao-aceitar / negar / revisar ────────────────────────────────────
    suggest_group = app_commands.Group(name="sugestao", description="Gerenciamento de sugestões (admins)")

    @suggest_group.command(name="aceitar", description="Marca uma sugestão como aprovada")
    @GUILD_ONLY_INSTALL
    @GUILD_ONLY_CONTEXT
    @app_commands.describe(id="ID da sugestão", nota="Nota explicativa (opcional)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def approve(self, interaction: discord.Interaction, id: str, nota: str = ""):
        await self._update_status(interaction, id, "approved", nota)

    @suggest_group.command(name="negar", description="Marca uma sugestão como negada")
    @GUILD_ONLY_INSTALL
    @GUILD_ONLY_CONTEXT
    @app_commands.describe(id="ID da sugestão", nota="Motivo da recusa")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def deny(self, interaction: discord.Interaction, id: str, nota: str = ""):
        await self._update_status(interaction, id, "denied", nota)

    @suggest_group.command(name="revisar", description="Coloca uma sugestão em análise")
    @GUILD_ONLY_INSTALL
    @GUILD_ONLY_CONTEXT
    @app_commands.describe(id="ID da sugestão", nota="Nota de revisão (opcional)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def review(self, interaction: discord.Interaction, id: str, nota: str = ""):
        await self._update_status(interaction, id, "review", nota)

    async def _update_status(self, interaction: discord.Interaction, sid: str, status: str, nota: str):
        if sid not in self._db:
            await interaction.response.send_message(f"❌ Sugestão `#{sid}` não encontrada.", ephemeral=True)
            return

        entry = self._db[sid]
        entry["status"] = status
        if nota:
            entry["admin_note"] = nota
        _save_suggestions(self._db)

        # Atualiza o embed no canal
        try:
            ch = self.bot.get_channel(entry["channel_id"])
            if ch:
                msg = await ch.fetch_message(entry["msg_id"])
                await msg.edit(embed=_build_embed(entry, sid))
        except Exception as e:
            logger.warning(f"[SUGGEST] Falha ao atualizar embed #{sid}: {e}")

        await interaction.response.send_message(
            f"✅ Sugestão **#{sid}** marcada como `{STATUS_LABELS.get(status, status)}`.",
            ephemeral=True,
        )
        logger.info(f"[SUGGEST] #{sid} → {status} por {interaction.user}")

    # ── Contagem de reações ────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        await self._handle_vote(payload, adding=True)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        await self._handle_vote(payload, adding=False)

    async def _handle_vote(self, payload: discord.RawReactionActionEvent, adding: bool):
        if payload.user_id == self.bot.user.id:
            return

        emoji = str(payload.emoji)
        if emoji not in (VOTE_UP, VOTE_DOWN):
            return

        # Encontra a sugestão pelo message_id
        entry = None
        sid = None
        for k, v in self._db.items():
            if v.get("msg_id") == payload.message_id:
                entry = v
                sid = k
                break

        if not entry:
            return

        uid = str(payload.user_id)
        field_self  = "voters_up"   if emoji == VOTE_UP else "voters_down"
        field_other = "voters_down" if emoji == VOTE_UP else "voters_up"
        count_self  = "up"          if emoji == VOTE_UP else "down"
        count_other = "down"        if emoji == VOTE_UP else "up"

        voters_self  = entry.setdefault(field_self, [])
        voters_other = entry.setdefault(field_other, [])

        if adding:
            if uid not in voters_self:
                voters_self.append(uid)
                entry[count_self] = len(voters_self)
                # Remove voto oposto se existia
                if uid in voters_other:
                    voters_other.remove(uid)
                    entry[count_other] = len(voters_other)
        else:
            if uid in voters_self:
                voters_self.remove(uid)
                entry[count_self] = len(voters_self)

        _save_suggestions(self._db)

        # Atualiza embed
        try:
            ch = self.bot.get_channel(entry["channel_id"])
            if ch:
                msg = await ch.fetch_message(entry["msg_id"])
                await msg.edit(embed=_build_embed(entry, sid))
        except Exception:
            pass

    # ── Erros de permissão ────────────────────────────────────────────────────
    @set_channel.error
    async def perm_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ Você precisa de **Gerenciar Servidor**.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Suggestions(bot))
    logger.info("[DISCORD] ✅ Cog Suggestions carregada")
