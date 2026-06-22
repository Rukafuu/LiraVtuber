import discord
from discord.ext import commands
from discord import app_commands
import os
import logging
from dotenv import load_dotenv
from .constants import logger, EMOJI
from .app_errors import handle_tree_error

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
        from .logging_setup import dedupe_discord_loggers

        dedupe_discord_loggers()

    async def setup_hook(self):
        from .logging_setup import dedupe_discord_loggers

        dedupe_discord_loggers()
        self.tree.on_error = handle_tree_error
        initial_extensions = [
            'src.modules.discord.cogs.chat',
            'src.modules.discord.cogs.economy',
            'src.modules.discord.cogs.social',
            'src.modules.discord.cogs.events',
            'src.modules.discord.cogs.help',
            'src.modules.discord.cogs.admin',
            # ── Sprint 1: Quick wins ──────────────────────────────
            'src.modules.discord.cogs.afk',           # /afk /voltei
            'src.modules.discord.cogs.sticky',         # /sticky-set /sticky-remove
            'src.modules.discord.cogs.suggestions',    # /sugerir /sugestao aceitar|negar|revisar
            'src.modules.discord.cogs.serverstats',    # /stats-add /stats-remove
            # ── Sprint 2: Engajamento ─────────────────────────────
            'src.modules.discord.cogs.birthdays',      # /aniversario /aniversario-canal
            'src.modules.discord.cogs.giveaway',       # /giveaway /giveaway-reroll
            'src.modules.discord.cogs.reaction_roles', # /rr-add /rr-remove /rr-list
            'src.modules.discord.cogs.notepad',        # /nota /notas /nota-ver /nota-editar
            'src.modules.discord.cogs.welcome',        # /boas-vindas (GIF/frases aleatórias)
            'src.modules.discord.cogs.updates',        # novidades automáticas no canal
            'src.modules.discord.cogs.setup',          # /setup-servidor
            # ── Sprint 3: Moderação e Suporte ─────────────────────
            'src.modules.discord.cogs.automod',        # /automod blacklist-add/remove/ia-toggle
            'src.modules.discord.cogs.customcmds',     # /custom adicionar/remover/listar
            'src.modules.discord.cogs.tickets',        # /ticket-setup
        ]
        for ext in initial_extensions:
            try:
                await self.load_extension(ext)
                logger.info(f"[DISCORD]  Cog carregada: {ext.split('.')[-1]}")
            except Exception as e:
                logger.error("[DISCORD]  Erro ao carregar %s: %s", ext, e)

    async def _sync_guild(self, guild: discord.Guild):
        """Sincroniza slash só de guild (sem copiar globais — evita /act duplicado)."""
        from .slash_meta import purge_duplicate_guild_commands

        try:
            synced = await self.tree.sync(guild=guild)
            purged = await purge_duplicate_guild_commands(self, guild)
            logger.info(
                f"[DISCORD] {len(synced)} cmds em {guild.name}"
                + (f", {purged} duplicata(s) removida(s)" if purged else "")
            )
        except Exception as e:
            logger.warning(f"[DISCORD] Falha ao sincronizar em {guild.name}: {e}")

    async def on_ready(self):
        logger.info(f'[DISCORD] ✦ Online como {self.user} em {len(self.guilds)} servidor(es) ✦')
        await self.change_presence(
            activity=discord.Activity(type=discord.ActivityType.watching, name="você com carinho 🌸")
        )
        # Sync global consome ~5 PUTs/hora na API do Discord — não rodar a cada reinício.
        if os.getenv("SYNC_GLOBAL_ON_START", "").lower() in ("1", "true", "yes"):
            try:
                synced = await self.tree.sync()
                logger.info(f'[DISCORD]  {len(synced)} comandos sincronizados globalmente.')
            except discord.HTTPException as e:
                if e.status == 429:
                    retry = getattr(e, "retry_after", None)
                    logger.error(
                        f'[DISCORD] ❌ Sync global no startup: 429 (rate limit).'
                        f' Aguarde {retry or "?"}s ou use !sync no servidor de teste.'
                    )
                else:
                    logger.error(f'[DISCORD] Falha ao sincronizar comandos: {e}')
            except Exception as e:
                logger.error(f'[DISCORD]  Falha ao sincronizar comandos: {e}')
        else:
            logger.info(
                '[DISCORD] Sync global no startup desligado. '
                'Novos /cmds (ex.: /imaginar_avancado) precisam de `!sync global` ou SYNC_GLOBAL_ON_START=1.'
            )

    async def on_guild_join(self, guild: discord.Guild):
        """Sincroniza automaticamente quando o bot entra em um novo servidor."""
        logger.info(f"[DISCORD] Entrou no servidor: {guild.name} — sincronizando comandos...")
        await self._sync_guild(guild)

def run_bot():
    bot = LiraBot()
    token = os.getenv("DISCORD_TOKEN")
    if token:
        bot.run(token)
    else:
        logger.error("[DISCORD] DISCORD_TOKEN não encontrado!")

if __name__ == "__main__":
    run_bot()
