"""
╔══════════════════════════════════════════════════════════════╗
║  LiraVT · Cog: Notepad (Bloco de Notas pessoal)             ║
║  Todos os subcomandos sob /nota — conta como 1 no limite    ║
╚══════════════════════════════════════════════════════════════╝
"""
import discord
from discord.ext import commands
from discord import app_commands
import json, os
from datetime import datetime, timezone
from ..slash_meta import GUILD_ONLY_CONTEXT, GUILD_ONLY_INSTALL, GuildOnlyCog
from ..constants import logger, EMOJI

NOTEPAD_FILE  = os.path.join("data", "notepad.json")
MAX_NOTES     = 20
MAX_NOTE_LEN  = 1000
MAX_TITLE_LEN = 60


def _load() -> dict:
    if os.path.exists(NOTEPAD_FILE):
        try:
            with open(NOTEPAD_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save(data: dict):
    os.makedirs("data", exist_ok=True)
    with open(NOTEPAD_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _user_notes(db: dict, uid: str) -> list:
    return db.setdefault(uid, [])


class ConfirmClearView(discord.ui.View):
    def __init__(self, user: discord.User):
        super().__init__(timeout=30)
        self.user = user
        self.confirmed = False

    @discord.ui.button(label="Sim, deletar tudo", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ Não é sua confirmação!", ephemeral=True)
            return
        self.confirmed = True
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            return
        self.confirmed = False
        self.stop()
        await interaction.response.defer()


class Notepad(GuildOnlyCog):
    """Bloco de notas pessoal e privado por usuário."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._db: dict = _load()

    # ── Grupo /nota ───────────────────────────────────────────────────────────
    nota_group = app_commands.Group(
        name="nota",
        description="Seu bloco de notas pessoal e privado 📝",
    )

    # /nota criar
    @nota_group.command(name="criar", description="Cria uma nova nota pessoal")
    @GUILD_ONLY_INSTALL
    @GUILD_ONLY_CONTEXT
    @app_commands.describe(titulo="Título da nota", conteudo="Conteúdo da nota")
    async def nota_criar(self, interaction: discord.Interaction, titulo: str, conteudo: str):
        uid = str(interaction.user.id)
        notes = _user_notes(self._db, uid)

        if len(notes) >= MAX_NOTES:
            await interaction.response.send_message(
                f"❌ Você já tem {MAX_NOTES} notas! Delete alguma antes.", ephemeral=True
            )
            return
        if len(titulo) > MAX_TITLE_LEN:
            await interaction.response.send_message(
                f"❌ Título muito longo! Máx: {MAX_TITLE_LEN} chars.", ephemeral=True
            )
            return
        if len(conteudo) > MAX_NOTE_LEN:
            await interaction.response.send_message(
                f"❌ Conteúdo muito longo! Máx: {MAX_NOTE_LEN} chars.", ephemeral=True
            )
            return

        note_id = (max(n["id"] for n in notes) + 1) if notes else 1
        note = {
            "id":         note_id,
            "title":      titulo,
            "content":    conteudo,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        notes.append(note)
        _save(self._db)

        embed = discord.Embed(
            title=f"📝 Nota #{note_id} criada!",
            description=f"**{titulo}**\n\n{conteudo}",
            color=0x7dd8a0,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_footer(text="Apenas você pode ver suas notas")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        logger.info(f"[NOTEPAD] {interaction.user} criou nota #{note_id}")

    # /nota listar
    @nota_group.command(name="listar", description="Lista todas as suas notas")
    @GUILD_ONLY_INSTALL
    @GUILD_ONLY_CONTEXT
    async def nota_listar(self, interaction: discord.Interaction):
        uid = str(interaction.user.id)
        notes = _user_notes(self._db, uid)

        if not notes:
            await interaction.response.send_message(
                "📓 Você não tem notas. Use `/nota criar`!", ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"📓 Suas notas ({len(notes)}/{MAX_NOTES})",
            color=0x5865F2,
        )
        for note in sorted(notes, key=lambda n: n["id"]):
            preview = note["content"][:80] + ("..." if len(note["content"]) > 80 else "")
            ts = datetime.fromisoformat(note["created_at"])
            embed.add_field(
                name=f"#{note['id']} — {note['title']}",
                value=f"{preview}\n*<t:{int(ts.timestamp())}:d>*",
                inline=False,
            )
        embed.set_footer(text="Use /nota ver <id> para ver completa")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # /nota ver
    @nota_group.command(name="ver", description="Vê o conteúdo completo de uma nota")
    @GUILD_ONLY_INSTALL
    @GUILD_ONLY_CONTEXT
    @app_commands.describe(id="ID da nota")
    async def nota_ver(self, interaction: discord.Interaction, id: int):
        uid = str(interaction.user.id)
        note = next((n for n in _user_notes(self._db, uid) if n["id"] == id), None)
        if not note:
            await interaction.response.send_message(f"❌ Nota #{id} não encontrada.", ephemeral=True)
            return

        ts = datetime.fromisoformat(note["created_at"])
        embed = discord.Embed(
            title=f"📝 #{note['id']} — {note['title']}",
            description=note["content"],
            color=0x5865F2,
            timestamp=ts,
        )
        embed.set_footer(text="Criada em")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # /nota editar
    @nota_group.command(name="editar", description="Edita título e/ou conteúdo de uma nota")
    @GUILD_ONLY_INSTALL
    @GUILD_ONLY_CONTEXT
    @app_commands.describe(
        id="ID da nota",
        titulo="Novo título (vazio = manter)",
        conteudo="Novo conteúdo (vazio = manter)",
    )
    async def nota_editar(
        self,
        interaction: discord.Interaction,
        id: int,
        titulo: str = "",
        conteudo: str = "",
    ):
        uid = str(interaction.user.id)
        note = next((n for n in _user_notes(self._db, uid) if n["id"] == id), None)
        if not note:
            await interaction.response.send_message(f"❌ Nota #{id} não encontrada.", ephemeral=True)
            return
        if not titulo and not conteudo:
            await interaction.response.send_message(
                "⚠️ Informe pelo menos um campo para editar.", ephemeral=True
            )
            return
        if titulo:
            if len(titulo) > MAX_TITLE_LEN:
                await interaction.response.send_message(
                    f"❌ Título muito longo! Máx: {MAX_TITLE_LEN} chars.", ephemeral=True
                )
                return
            note["title"] = titulo
        if conteudo:
            if len(conteudo) > MAX_NOTE_LEN:
                await interaction.response.send_message(
                    f"❌ Conteúdo muito longo! Máx: {MAX_NOTE_LEN} chars.", ephemeral=True
                )
                return
            note["content"] = conteudo
        note["updated_at"] = datetime.now(timezone.utc).isoformat()
        _save(self._db)
        await interaction.response.send_message(f"✅ Nota **#{id}** atualizada!", ephemeral=True)
        logger.info(f"[NOTEPAD] {interaction.user} editou nota #{id}")

    # /nota deletar
    @nota_group.command(name="deletar", description="Deleta uma nota permanentemente")
    @GUILD_ONLY_INSTALL
    @GUILD_ONLY_CONTEXT
    @app_commands.describe(id="ID da nota")
    async def nota_deletar(self, interaction: discord.Interaction, id: int):
        uid = str(interaction.user.id)
        notes = _user_notes(self._db, uid)
        before = len(notes)
        self._db[uid] = [n for n in notes if n["id"] != id]
        _save(self._db)

        if len(self._db[uid]) == before:
            await interaction.response.send_message(f"❌ Nota #{id} não encontrada.", ephemeral=True)
            return
        await interaction.response.send_message(f"🗑️ Nota **#{id}** deletada.", ephemeral=True)
        logger.info(f"[NOTEPAD] {interaction.user} deletou nota #{id}")

    # /nota limpar
    @nota_group.command(name="limpar", description="Deleta TODAS as suas notas (pede confirmação)")
    @GUILD_ONLY_INSTALL
    @GUILD_ONLY_CONTEXT
    async def nota_limpar(self, interaction: discord.Interaction):
        uid = str(interaction.user.id)
        count = len(self._db.get(uid, []))
        if count == 0:
            await interaction.response.send_message("📓 Você não tem notas.", ephemeral=True)
            return

        view = ConfirmClearView(interaction.user)
        await interaction.response.send_message(
            f"⚠️ Tem certeza que quer deletar **{count} nota(s)**? Isso é irreversível!",
            view=view,
            ephemeral=True,
        )
        await view.wait()

        if view.confirmed:
            self._db[uid] = []
            _save(self._db)
            await interaction.edit_original_response(
                content=f"🗑️ Todas as {count} notas foram deletadas.", view=None
            )
        else:
            await interaction.edit_original_response(content="✅ Cancelado.", view=None)


async def setup(bot: commands.Bot):
    await bot.add_cog(Notepad(bot))
    logger.info("[DISCORD] ✅ Cog Notepad carregada")
