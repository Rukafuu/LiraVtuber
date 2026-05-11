import discord
import logging
import os

# ── DICIONÁRIO DE EMOJIS CUSTOMIZADOS ──────────────────────────
EMOJI = {
    "loading": "<a:loading:1502440131162804294>",
    "think": "<:think:1502526701052362865>",
    "love": "<:animelove:1502526696702742608>",
    "dance": "<:reimudance:1502526715530838097>",
    "dance2": "<:frierendance:1502526676981256312>",
    "coin": "<:lunadoro:1502526680315597000>",
    "what": "<:reimuwhat:1502526722162299032>",
    "help": "<:animehelp:1502526639609876512>",
    "ok": "<:reimuok:1502526713475891300>",
    "smug": "<:nepsmug:1502526670555320462>",
    "cry": "<:marisacry:1502526723189768313>"
}

THINKING_MSG = f"Estou pensando... {EMOJI['loading']}"

# Logger compartilhado
logger = logging.getLogger("LiraDiscordBot")
