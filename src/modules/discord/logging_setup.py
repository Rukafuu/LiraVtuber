import logging

logger = logging.getLogger(__name__)


def configure_discord_bot_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - [%(levelname)s] - %(message)s",
    )
    # Silencia logs excessivos da biblioteca discord.py
    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("discord.http").setLevel(logging.WARNING)


def dedupe_discord_loggers():
    # Remove handlers duplicados para evitar logar em dobro no terminal
    discord_logger = logging.getLogger("discord")
    if len(discord_logger.handlers) > 1:
        discord_logger.handlers = [discord_logger.handlers[0]]
