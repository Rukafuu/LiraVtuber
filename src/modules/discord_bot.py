import os
import sys

# Logging antes de qualquer import do discord/projeto
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.modules.discord.logging_setup import configure_discord_bot_logging

configure_discord_bot_logging()

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from src.modules.discord.bot import run_bot

if __name__ == "__main__":
    run_bot()