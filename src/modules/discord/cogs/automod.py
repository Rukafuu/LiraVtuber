"""
╔══════════════════════════════════════════════════════════════╗
║  LiraVT · Cog: Automod & Filtros de IA                      ║
║  Intercepta mensagens, verifica blacklist e usa IA          ║
╚══════════════════════════════════════════════════════════════╝
"""
import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import re
import asyncio
from datetime import timedelta
from ..slash_meta import GUILD_ONLY_CONTEXT, GUILD_ONLY_INSTALL, GuildOnlyCog
from ..constants import logger, EMOJI
from src.providers.openrouter_provider import OpenRouterProvider
from src.config.config_loader import CONFIG

AUTOMOD_FILE = os.path.join("data", "automod.json")

def _load() -> dict:
    if os.path.exists(AUTOMOD_FILE):
        try:
            with open(AUTOMOD_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    # default structure
    return {"blacklist": [], "ai_enabled": True}

def _save(data: dict):
    os.makedirs("data", exist_ok=True)
    with open(AUTOMOD_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

class Automod(GuildOnlyCog):
    """Sistema de moderação automática (Filtros locais e Inteligência Artificial)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._db: dict = _load()
        self.ai_provider = OpenRouterProvider()

    automod_group = app_commands.Group(
        name="automod",
        description="Configurações do filtro de palavras e IA de moderação",
        default_permissions=discord.Permissions(manage_guild=True)
    )

    @automod_group.command(name="blacklist-add", description="Adiciona uma palavra proibida")
    @GUILD_ONLY_INSTALL
    @GUILD_ONLY_CONTEXT
    @app_commands.describe(palavra="Palavra que será deletada instantaneamente")
    async def blacklist_add(self, interaction: discord.Interaction, palavra: str):
        p = palavra.lower().strip()
        if p not in self._db.setdefault("blacklist", []):
            self._db["blacklist"].append(p)
            _save(self._db)
            await interaction.response.send_message(f"✅ A palavra ||{p}|| foi adicionada à blacklist local.", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ Essa palavra já está na blacklist.", ephemeral=True)

    @automod_group.command(name="blacklist-remove", description="Remove uma palavra proibida")
    @GUILD_ONLY_INSTALL
    @GUILD_ONLY_CONTEXT
    async def blacklist_rem(self, interaction: discord.Interaction, palavra: str):
        p = palavra.lower().strip()
        bl = self._db.setdefault("blacklist", [])
        if p in bl:
            bl.remove(p)
            _save(self._db)
            await interaction.response.send_message(f"✅ A palavra ||{p}|| foi removida.", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ Essa palavra não estava na blacklist.", ephemeral=True)

    @automod_group.command(name="ia-toggle", description="Liga/Desliga o Automod por Inteligência Artificial")
    @GUILD_ONLY_INSTALL
    @GUILD_ONLY_CONTEXT
    async def ia_toggle(self, interaction: discord.Interaction):
        curr = self._db.get("ai_enabled", True)
        self._db["ai_enabled"] = not curr
        _save(self._db)
        status = "LIGADO ✅" if not curr else "DESLIGADO ❌"
        await interaction.response.send_message(f"🤖 Automod via Inteligência Artificial agora está **{status}**.", ephemeral=True)

    async def _check_ai_toxicity(self, content: str) -> bool:
        """
        Consulta a IA de forma estrita para saber se é ofensa grave/preconceito/spam.
        Retorna True se for tóxico.
        """
        sys_prompt = (
            "Você é um moderador automático de chat implacável.\n"
            "Analise a mensagem do usuário e determine se ela contém:\n"
            "- Discurso de ódio, racismo, homofobia ou preconceito grave\n"
            "- Assédio severo ou ofensas diretas pesadas\n"
            "- Spam malicioso evidente\n\n"
            "Responda APENAS com a palavra 'SIM' se a mensagem for tóxica e inaceitável, ou 'NAO' se for uma mensagem aceitável (mesmo que contenha pequenos palavrões casuais ou gírias do dia-a-dia).\n"
            "Mantenha a resposta restrita a SIM ou NAO."
        )
        try:
            resp = await self.bot.loop.run_in_executor(
                None,
                self.ai_provider.gerar_resposta,
                [], # chat_history
                sys_prompt, # sistema_prompt
                content # user_message
            )
            if not resp:
                return False
            return "SIM" in resp.strip().upper()
        except Exception as e:
            logger.error(f"[AUTOMOD] Falha na verificação de IA: {e}")
            return False

    async def _punish_user(self, message: discord.Message, reason: str):
        """Aplica punição: Timeout de 10 minutos (se possível) e deleta a mensagem."""
        try:
            await message.delete()
        except Exception:
            pass

        # Tenta aplicar timeout (10 min)
        try:
            duration = timedelta(minutes=10)
            await message.author.timeout(duration, reason=reason)
            logger.info(f"[AUTOMOD] {message.author} recebeu timeout por: {reason}")
        except discord.Forbidden:
            logger.warning(f"[AUTOMOD] Sem permissão para aplicar timeout em {message.author}.")
        except Exception as e:
            logger.error(f"[AUTOMOD] Erro ao aplicar timeout: {e}")

        # Busca canal de logs ( Sala do trono -> 📜-logs-usuarios ou mod-chat )
        guild = message.guild
        log_channel = discord.utils.get(guild.text_channels, name="📜-logs-usuarios") or discord.utils.get(guild.text_channels, name="🛡️-staff-chat")
        
        if log_channel:
            embed = discord.Embed(
                title="🚨 Automod Action",
                color=discord.Color.red(),
                description=f"**Usuário:** {message.author.mention} (`{message.author.id}`)\n"
                            f"**Canal:** {message.channel.mention}\n"
                            f"**Motivo:** {reason}\n\n"
                            f"**Mensagem bloqueada:**\n```{message.content[:1000]}```"
            )
            try:
                await log_channel.send(embed=embed)
            except Exception:
                pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        # Se for administrador/mod, ignora o automod
        if message.author.guild_permissions.manage_messages:
            return

        content_lower = message.content.lower()

        # 1. Checagem de Blacklist Local (Imediata)
        blacklist = self._db.get("blacklist", [])
        for word in blacklist:
            # Checa palavra inteira ou substring
            pattern = r'\b' + re.escape(word) + r'\b'
            if re.search(pattern, content_lower) or (word in content_lower and len(word) >= 4):
                await self._punish_user(message, f"Palavra bloqueada pela Blacklist: {word}")
                return # Interrompe, pois já foi deletada

        # 2. Checagem por IA (Assíncrona)
        if self._db.get("ai_enabled", True) and len(message.content) > 5:
            # Não bloqueia o event loop, joga pra task em background
            self.bot.loop.create_task(self._process_ai_automod(message))

    async def _process_ai_automod(self, message: discord.Message):
        is_toxic = await self._check_ai_toxicity(message.content)
        if is_toxic:
            await self._punish_user(message, "Detectado como Ofensa Grave / Toxicidade pela IA Automod.")
            # Podemos tentar dar timeout / cargo do bobo da corte. A função _punish_user já dá timeout.

async def setup(bot: commands.Bot):
    await bot.add_cog(Automod(bot))
    logger.info("[DISCORD] ✅ Cog Automod carregada")
