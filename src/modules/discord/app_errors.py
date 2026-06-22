"""Respostas rápidas para erros de slash commands (evita 'O aplicativo não respondeu')."""
from __future__ import annotations

import logging

import discord
from discord import app_commands

logger = logging.getLogger("LiraDiscordBot")


async def handle_tree_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    original = error
    if isinstance(error, app_commands.CommandInvokeError) and error.original:
        original = error.original

    msg = "❌ Algo deu errado ao rodar o comando."
    ephemeral = True

    if isinstance(original, app_commands.TransformerError):
        msg = (
            "❌ Não encontrei esse usuário. **Clique no campo e escolha na lista** "
            "(@menção), ou use o parâmetro `usuario_nome` para digitar o apelido."
        )
    elif isinstance(original, app_commands.MissingPermissions):
        msg = "❌ Você não tem permissão para isso neste canal."
    elif isinstance(original, app_commands.BotMissingPermissions):
        msg = "❌ Eu não tenho permissão aqui (enviar mensagens / ver histórico)."
    elif isinstance(original, app_commands.CommandOnCooldown):
        msg = f"⏳ Calma — espera {original.retry_after:.0f}s."
    elif isinstance(original, discord.NotFound):
        msg = "❌ Mensagem ou canal não encontrado (pode ter sido apagado)."
    elif isinstance(original, discord.HTTPException):
        if original.status == 429:
            msg = "⏳ Discord pediu para ir mais devagar (rate limit). Tenta de novo."
        else:
            msg = f"❌ Erro do Discord ({original.status})."
    else:
        logger.error("[DISCORD] Erro no slash command: %s: %s", type(original).__name__, original)
        msg = f"❌ Erro: `{type(original).__name__}` — detalhe no log do bot."

    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=ephemeral)
        else:
            await interaction.response.send_message(msg, ephemeral=ephemeral)
    except discord.HTTPException as send_err:
        logger.warning("[DISCORD] Falha ao enviar mensagem de erro do slash: %s", send_err)