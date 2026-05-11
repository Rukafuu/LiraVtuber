import discord
from discord.ext import commands
from discord import app_commands
import os
import logging
from dotenv import load_dotenv
from .constants import logger, EMOJI

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

load_dotenv()

class LiraBot(commands.Bot):
    def __init__(self):
        # Garante que a pasta de dados existe antes de carregar as cogs
        os.makedirs("data", exist_ok=True)
        
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True # Para o sistema de economia/social
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        initial_extensions = [
            'src.modules.discord.cogs.chat',
            'src.modules.discord.cogs.economy',
            'src.modules.discord.cogs.social',
            'src.modules.discord.cogs.events',
            'src.modules.discord.cogs.help',
            'src.modules.discord.cogs.admin',
        ]
        for ext in initial_extensions:
            try:
                await self.load_extension(ext)
                logger.info(f"[DISCORD] ✅ Cog: {ext.split('.')[-1]}")
            except Exception as e:
                logger.error(f"[DISCORD] ❌ Falha ao carregar {ext}: {e}")

    async def _sync_guild(self, guild: discord.Guild):
        """Sincroniza os slash commands em um servidor específico."""
        try:
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            logger.info(f"[DISCORD] 🌸 {len(synced)} comandos sincronizados em: {guild.name}")
        except Exception as e:
            logger.warning(f"[DISCORD] Falha ao sincronizar em {guild.name}: {e}")

    async def on_ready(self):
        logger.info(f'[DISCORD] ✦ Online como {self.user} em {len(self.guilds)} servidor(es) ✦')
        # Sincroniza em todos os servidores que o bot já está
        for guild in self.guilds:
            await self._sync_guild(guild)
        
        # Sincronização global extra
        try:
            await self.tree.sync()
            logger.info("[DISCORD] 🌸 Sincronização global concluída!")
        except Exception as e:
            logger.warning(f"[DISCORD] Falha no sync global: {e}")

        await self.change_presence(
            activity=discord.Activity(type=discord.ActivityType.watching, name="você com carinho 🌸")
        )

    async def on_guild_join(self, guild: discord.Guild):
        """Sincroniza automaticamente quando o bot entra em um novo servidor."""
        logger.info(f"[DISCORD] Entrou no servidor: {guild.name} — sincronizando comandos...")
        await self._sync_guild(guild)

    @commands.command(name="sync")
    @commands.is_owner()
    async def force_sync(self, ctx):
        """Re-sincroniza os comandos em todos os servidores manualmente."""
        async with ctx.typing():
            count = 0
            for guild in self.guilds:
                try:
                    self.tree.copy_global_to(guild=guild)
                    synced = await self.tree.sync(guild=guild)
                    count += len(synced)
                except Exception as e:
                    await ctx.send(f"❌ Erro em {guild.name}: {e}")
            await ctx.send(f"✅ {count} comandos sincronizados em {len(self.guilds)} servidor(es)!")

def run_bot():
    bot = LiraBot()
    token = os.getenv("DISCORD_TOKEN")
    if token:
        bot.run(token)
    else:
        logger.error("[DISCORD] DISCORD_TOKEN não encontrado!")

if __name__ == "__main__":
    run_bot()
