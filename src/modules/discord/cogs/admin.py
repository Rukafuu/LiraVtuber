import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import os
from datetime import timedelta
from ..constants import logger

# Banco de dados de avisos (separado do gamification)
ADMIN_DB = "data/admin.db"


def _init_admin_db():
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(ADMIN_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS warnings (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id   TEXT NOT NULL,
            guild_id  TEXT NOT NULL,
            mod_id    TEXT NOT NULL,
            reason    TEXT NOT NULL,
            created   DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def add_warning(user_id: str, guild_id: str, mod_id: str, reason: str) -> int:
    conn = sqlite3.connect(ADMIN_DB)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO warnings (user_id, guild_id, mod_id, reason) VALUES (?, ?, ?, ?)",
        (user_id, guild_id, mod_id, reason)
    )
    conn.commit()
    cursor.execute(
        "SELECT COUNT(*) FROM warnings WHERE user_id = ? AND guild_id = ?",
        (user_id, guild_id)
    )
    total = cursor.fetchone()[0]
    conn.close()
    return total


def get_warnings(user_id: str, guild_id: str) -> list:
    conn = sqlite3.connect(ADMIN_DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM warnings WHERE user_id = ? AND guild_id = ? ORDER BY created DESC",
        (user_id, guild_id)
    )
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def clear_warnings(user_id: str, guild_id: str) -> int:
    conn = sqlite3.connect(ADMIN_DB)
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM warnings WHERE user_id = ? AND guild_id = ?",
        (user_id, guild_id)
    )
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted


def remove_warning(warning_id: int, guild_id: str) -> bool:
    conn = sqlite3.connect(ADMIN_DB)
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM warnings WHERE id = ? AND guild_id = ?",
        (warning_id, guild_id)
    )
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success


# ── Cog Admin ─────────────────────────────────────────────────────────────────

class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        _init_admin_db()

    # ── Moderação ──────────────────────────────────────────────────────────────

    @app_commands.command(name="banir", description="[ADM] Bane um usuário do servidor 🔨")
    @app_commands.describe(usuario="Usuário a banir", motivo="Motivo do banimento", deletar_dias="Dias de mensagens para deletar (0-7)")
    @app_commands.default_permissions(ban_members=True)
    async def banir(self, interaction: discord.Interaction, usuario: discord.Member,
                    motivo: str = "Sem motivo informado", deletar_dias: int = 0):
        if usuario.top_role >= interaction.user.top_role:
            return await interaction.response.send_message("❌ Você não pode banir alguém com cargo igual ou superior ao seu!", ephemeral=True)

        deletar_dias = max(0, min(7, deletar_dias))
        await usuario.ban(reason=f"{interaction.user} | {motivo}", delete_message_days=deletar_dias)

        embed = discord.Embed(title="🔨 Usuário Banido", color=0xff0000)
        embed.add_field(name="Usuário", value=f"{usuario.mention} ({usuario})", inline=True)
        embed.add_field(name="Moderador", value=interaction.user.mention, inline=True)
        embed.add_field(name="Motivo", value=motivo, inline=False)
        logger.info(f"[ADM] {interaction.user} baniu {usuario} | Motivo: {motivo}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="expulsar", description="[ADM] Expulsa um usuário do servidor 👟")
    @app_commands.describe(usuario="Usuário a expulsar", motivo="Motivo da expulsão")
    @app_commands.default_permissions(kick_members=True)
    async def expulsar(self, interaction: discord.Interaction, usuario: discord.Member,
                       motivo: str = "Sem motivo informado"):
        if usuario.top_role >= interaction.user.top_role:
            return await interaction.response.send_message("❌ Você não pode expulsar alguém com cargo igual ou superior!", ephemeral=True)

        await usuario.kick(reason=f"{interaction.user} | {motivo}")

        embed = discord.Embed(title="👟 Usuário Expulso", color=0xff6600)
        embed.add_field(name="Usuário", value=f"{usuario.mention} ({usuario})", inline=True)
        embed.add_field(name="Moderador", value=interaction.user.mention, inline=True)
        embed.add_field(name="Motivo", value=motivo, inline=False)
        logger.info(f"[ADM] {interaction.user} expulsou {usuario} | Motivo: {motivo}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="silenciar", description="[ADM] Silencia um usuário por um tempo ⏱️")
    @app_commands.describe(
        usuario="Usuário a silenciar",
        minutos="Duração em minutos (máx: 40320 = 28 dias)",
        motivo="Motivo do silenciamento"
    )
    @app_commands.default_permissions(moderate_members=True)
    async def silenciar(self, interaction: discord.Interaction, usuario: discord.Member,
                        minutos: int = 10, motivo: str = "Sem motivo informado"):
        if usuario.top_role >= interaction.user.top_role:
            return await interaction.response.send_message("❌ Você não pode silenciar alguém com cargo igual ou superior!", ephemeral=True)

        minutos = max(1, min(40320, minutos))
        duracao = timedelta(minutes=minutos)
        await usuario.timeout(duracao, reason=f"{interaction.user} | {motivo}")

        horas = minutos // 60
        mins = minutos % 60
        tempo_str = f"{horas}h{mins:02d}min" if horas else f"{minutos} min"

        embed = discord.Embed(title="🔇 Usuário Silenciado", color=0xffa500)
        embed.add_field(name="Usuário", value=f"{usuario.mention}", inline=True)
        embed.add_field(name="Duração", value=tempo_str, inline=True)
        embed.add_field(name="Moderador", value=interaction.user.mention, inline=True)
        embed.add_field(name="Motivo", value=motivo, inline=False)
        logger.info(f"[ADM] {interaction.user} silenciou {usuario} por {tempo_str} | Motivo: {motivo}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="dessilenciar", description="[ADM] Remove o silêncio de um usuário 🔊")
    @app_commands.describe(usuario="Usuário para dessilenciar")
    @app_commands.default_permissions(moderate_members=True)
    async def dessilenciar(self, interaction: discord.Interaction, usuario: discord.Member):
        await usuario.timeout(None)
        embed = discord.Embed(title="🔊 Silêncio Removido", color=0x00ff88)
        embed.add_field(name="Usuário", value=usuario.mention, inline=True)
        embed.add_field(name="Moderador", value=interaction.user.mention, inline=True)
        await interaction.response.send_message(embed=embed)

    # ── Sistema de Avisos ──────────────────────────────────────────────────────

    @app_commands.command(name="advertir", description="[ADM] Emite um aviso para um usuário ⚠️")
    @app_commands.describe(usuario="Usuário a advertir", motivo="Motivo do aviso")
    @app_commands.default_permissions(moderate_members=True)
    async def advertir(self, interaction: discord.Interaction, usuario: discord.Member,
                       motivo: str = "Comportamento inadequado"):
        if usuario.bot:
            return await interaction.response.send_message("Não dá pra advertir um bot!", ephemeral=True)

        total = add_warning(str(usuario.id), str(interaction.guild_id), str(interaction.user.id), motivo)

        embed = discord.Embed(title="⚠️ Aviso Emitido", color=0xffcc00)
        embed.add_field(name="Usuário", value=f"{usuario.mention}", inline=True)
        embed.add_field(name="Total de Avisos", value=f"`{total}`", inline=True)
        embed.add_field(name="Moderador", value=interaction.user.mention, inline=True)
        embed.add_field(name="Motivo", value=motivo, inline=False)

        # Alerta automático ao acumular muitos avisos
        if total >= 3:
            embed.add_field(
                name="⚠️ Atenção",
                value=f"{usuario.mention} acumulou **{total} avisos**! Considere ação mais severa.",
                inline=False
            )

        logger.info(f"[ADM] {interaction.user} advertiu {usuario} (total: {total}) | Motivo: {motivo}")
        await interaction.response.send_message(embed=embed)

        # Tenta notificar o usuário por DM
        try:
            dm_embed = discord.Embed(
                title=f"⚠️ Você recebeu um aviso em **{interaction.guild.name}**",
                description=f"**Motivo:** {motivo}\n**Aviso #{total}**",
                color=0xffcc00
            )
            await usuario.send(embed=dm_embed)
        except Exception:
            pass  # DMs fechadas

    @app_commands.command(name="avisos", description="[ADM] Veja os avisos de um usuário 📋")
    @app_commands.describe(usuario="Usuário para verificar")
    @app_commands.default_permissions(moderate_members=True)
    async def avisos(self, interaction: discord.Interaction, usuario: discord.Member):
        warns = get_warnings(str(usuario.id), str(interaction.guild_id))

        embed = discord.Embed(
            title=f"📋 Avisos de {usuario.display_name}",
            color=0xffcc00 if warns else 0x00ff88
        )
        embed.set_thumbnail(url=usuario.display_avatar.url)

        if not warns:
            embed.description = "✅ Este usuário não tem nenhum aviso!"
        else:
            embed.description = f"Total: **{len(warns)} aviso(s)**"
            for w in warns[:10]:  # mostra até 10 avisos
                embed.add_field(
                    name=f"#{w['id']} — {w['created'][:10]}",
                    value=f"{w['reason']}",
                    inline=False
                )
            if len(warns) > 10:
                embed.set_footer(text=f"Mostrando 10 de {len(warns)} avisos.")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="remover_aviso", description="[ADM] Remove um aviso específico por ID 🗑️")
    @app_commands.describe(id_aviso="ID do aviso (veja com /avisos)")
    @app_commands.default_permissions(moderate_members=True)
    async def remover_aviso(self, interaction: discord.Interaction, id_aviso: int):
        success = remove_warning(id_aviso, str(interaction.guild_id))
        if success:
            await interaction.response.send_message(f"✅ Aviso `#{id_aviso}` removido com sucesso!", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Aviso `#{id_aviso}` não encontrado neste servidor.", ephemeral=True)

    @app_commands.command(name="limpar_avisos", description="[ADM] Remove TODOS os avisos de um usuário 🗑️")
    @app_commands.describe(usuario="Usuário para limpar avisos")
    @app_commands.default_permissions(administrator=True)
    async def limpar_avisos(self, interaction: discord.Interaction, usuario: discord.Member):
        deleted = clear_warnings(str(usuario.id), str(interaction.guild_id))
        await interaction.response.send_message(
            f"🗑️ **{deleted}** aviso(s) de {usuario.mention} foram removidos.",
            ephemeral=True
        )

    # ── Limpeza de Mensagens ───────────────────────────────────────────────────

    @app_commands.command(name="limpar", description="[ADM] Limpa mensagens do canal 🧹")
    @app_commands.describe(
        quantidade="Quantidade de mensagens (1–200)",
        usuario="Filtrar por usuário específico (opcional)"
    )
    @app_commands.default_permissions(manage_messages=True)
    async def limpar(self, interaction: discord.Interaction,
                     quantidade: int, usuario: discord.Member = None):
        quantidade = max(1, min(200, quantidade))
        await interaction.response.defer(ephemeral=True)

        def check(msg):
            return usuario is None or msg.author == usuario

        deleted = await interaction.channel.purge(limit=quantidade, check=check)
        alvo = f" de {usuario.mention}" if usuario else ""
        await interaction.followup.send(
            f"🧹 **{len(deleted)}** mensagem(ns){alvo} deletada(s)!",
            ephemeral=True
        )
        logger.info(f"[ADM] {interaction.user} limpou {len(deleted)} msgs em #{interaction.channel.name}")

    # ── Canal ──────────────────────────────────────────────────────────────────

    @app_commands.command(name="trancar", description="[ADM] Trava o canal para membros 🔒")
    @app_commands.describe(motivo="Motivo do travamento")
    @app_commands.default_permissions(manage_channels=True)
    async def trancar(self, interaction: discord.Interaction, motivo: str = "Manutenção"):
        overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = False
        await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)

        embed = discord.Embed(
            title="🔒 Canal Travado",
            description=f"**Motivo:** {motivo}\n**Por:** {interaction.user.mention}",
            color=0xff4444
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="destrancar", description="[ADM] Destrava o canal 🔓")
    @app_commands.default_permissions(manage_channels=True)
    async def destrancar(self, interaction: discord.Interaction):
        overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = None  # reset para padrão
        await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)

        embed = discord.Embed(
            title="🔓 Canal Destravado",
            description=f"**Por:** {interaction.user.mention}",
            color=0x00ff88
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="lento", description="[ADM] Define o modo lento do canal 🐢")
    @app_commands.describe(segundos="Segundos entre mensagens (0 = desativar)")
    @app_commands.default_permissions(manage_channels=True)
    async def lento(self, interaction: discord.Interaction, segundos: int = 0):
        segundos = max(0, min(21600, segundos))
        await interaction.channel.edit(slowmode_delay=segundos)
        if segundos == 0:
            await interaction.response.send_message("🐇 Modo lento **desativado**!")
        else:
            await interaction.response.send_message(f"🐢 Modo lento definido para **{segundos}s** entre mensagens!")

    # ── Comunicados ────────────────────────────────────────────────────────────

    @app_commands.command(name="anunciar", description="[ADM] Envia um anúncio em embed 📢")
    @app_commands.describe(
        titulo="Título do anúncio",
        mensagem="Conteúdo do anúncio",
        canal="Canal de destino (padrão: canal atual)",
        cor="Cor em hex, ex: ff69b4 (padrão: rosa)"
    )
    @app_commands.default_permissions(administrator=True)
    async def anunciar(self, interaction: discord.Interaction,
                       titulo: str, mensagem: str,
                       canal: discord.TextChannel = None,
                       cor: str = "ff69b4"):
        canal = canal or interaction.channel
        try:
            color = int(cor.replace("#", ""), 16)
        except ValueError:
            color = 0xff69b4

        embed = discord.Embed(title=f"📢 {titulo}", description=mensagem, color=color)
        embed.set_footer(text=f"Anúncio por {interaction.user.display_name} • {interaction.guild.name}")

        await canal.send(embed=embed)
        await interaction.response.send_message(
            f"✅ Anúncio enviado em {canal.mention}!", ephemeral=True
        )

    @app_commands.command(name="info_usuario", description="[ADM] Informações detalhadas de um usuário 🔍")
    @app_commands.describe(usuario="Usuário para inspecionar")
    @app_commands.default_permissions(moderate_members=True)
    async def info_usuario(self, interaction: discord.Interaction, usuario: discord.Member):
        warns = get_warnings(str(usuario.id), str(interaction.guild_id))

        embed = discord.Embed(
            title=f"🔍 Info: {usuario.display_name}",
            color=usuario.color if usuario.color.value else 0xff69b4
        )
        embed.set_thumbnail(url=usuario.display_avatar.url)
        embed.add_field(name="🆔 ID", value=f"`{usuario.id}`", inline=True)
        embed.add_field(name="📅 Conta criada", value=f"<t:{int(usuario.created_at.timestamp())}:R>", inline=True)
        embed.add_field(name="📥 Entrou no servidor", value=f"<t:{int(usuario.joined_at.timestamp())}:R>", inline=True)
        embed.add_field(name="🤖 Bot?", value="Sim" if usuario.bot else "Não", inline=True)
        embed.add_field(name="⚠️ Avisos", value=str(len(warns)), inline=True)

        top_role = usuario.top_role
        embed.add_field(name="🏅 Cargo mais alto", value=top_role.mention if top_role != interaction.guild.default_role else "Nenhum", inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(AdminCog(bot))
