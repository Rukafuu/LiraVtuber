"""
╔══════════════════════════════════════════════════════════════╗
║  LiraVT · Cog: Custom Commands                              ║
║  Permite criar comandos de texto simples (ex: !socials)     ║
╚══════════════════════════════════════════════════════════════╝
"""
import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from ..slash_meta import GUILD_ONLY_CONTEXT, GUILD_ONLY_INSTALL, GuildOnlyCog
from ..constants import logger

CUSTOM_CMDS_FILE = os.path.join("data", "custom_commands.json")

def _load() -> dict:
    if os.path.exists(CUSTOM_CMDS_FILE):
        try:
            with open(CUSTOM_CMDS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def _save(data: dict):
    os.makedirs("data", exist_ok=True)
    with open(CUSTOM_CMDS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

class CustomCommands(GuildOnlyCog):
    """Comandos de texto customizáveis criados pela Staff."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Formato: { "guild_id": { "comando": "resposta" } }
        self._db: dict = _load()

    custom_group = app_commands.Group(
        name="custom",
        description="Gerencia comandos de texto personalizados (ex: !pix, !socials)",
        default_permissions=discord.Permissions(manage_messages=True)
    )

    @custom_group.command(name="adicionar", description="Cria ou edita um comando de texto")
    @GUILD_ONLY_INSTALL
    @GUILD_ONLY_CONTEXT
    @app_commands.describe(
        nome="Nome do comando (sem o !, ex: pix)",
        resposta="A resposta que a Lira vai dar quando alguém digitar o comando"
    )
    async def cmd_add(self, interaction: discord.Interaction, nome: str, resposta: str):
        gid = str(interaction.guild_id)
        config = self._db.setdefault(gid, {})
        
        cmd_nome = nome.lower().strip()
        if cmd_nome.startswith("!"):
            cmd_nome = cmd_nome[1:]

        config[cmd_nome] = resposta
        _save(self._db)

        await interaction.response.send_message(f"✅ Comando `!{cmd_nome}` salvo! Tente digitar no chat.", ephemeral=True)
        logger.info(f"[CUSTOM CMD] {interaction.user} adicionou/editou !{cmd_nome} em {interaction.guild.name}")

    @custom_group.command(name="remover", description="Remove um comando personalizado")
    @GUILD_ONLY_INSTALL
    @GUILD_ONLY_CONTEXT
    async def cmd_remove(self, interaction: discord.Interaction, nome: str):
        gid = str(interaction.guild_id)
        config = self._db.setdefault(gid, {})
        
        cmd_nome = nome.lower().strip()
        if cmd_nome.startswith("!"):
            cmd_nome = cmd_nome[1:]

        if cmd_nome in config:
            del config[cmd_nome]
            _save(self._db)
            await interaction.response.send_message(f"🗑️ Comando `!{cmd_nome}` removido com sucesso.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ O comando `!{cmd_nome}` não existe.", ephemeral=True)

    @custom_group.command(name="listar", description="Lista todos os comandos personalizados do servidor")
    @GUILD_ONLY_INSTALL
    @GUILD_ONLY_CONTEXT
    async def cmd_list(self, interaction: discord.Interaction):
        gid = str(interaction.guild_id)
        config = self._db.get(gid, {})

        if not config:
            await interaction.response.send_message("Nenhum comando personalizado criado ainda.", ephemeral=True)
            return

        cmds = "\n".join([f"`!{k}`" for k in config.keys()])
        embed = discord.Embed(
            title="📜 Comandos Personalizados",
            description=cmds,
            color=0x7dd8a0
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        content = message.content.strip()
        # Verifica se começa com o prefixo padrão "!" ou "/" e é um custom command
        if content.startswith("!") or content.startswith("/"):
            # Pega a primeira palavra (o comando) sem o prefixo
            cmd_invoke = content[1:].split()[0].lower()
            
            gid = str(message.guild.id)
            config = self._db.get(gid, {})
            
            if cmd_invoke in config:
                resposta = config[cmd_invoke]
                await message.reply(resposta)

async def setup(bot: commands.Bot):
    await bot.add_cog(CustomCommands(bot))
    logger.info("[DISCORD] ✅ Cog CustomCommands carregada")
