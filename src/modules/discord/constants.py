import discord
import logging
import os

# ── DICIONÁRIO DE EMOJIS CUSTOMIZADOS ──────────────────────────
EMOJI = {
    # Antigos/Básicos
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
    "cry": "<:marisacry:1502526723189768313>",

    # Novos Emojis (Adicionados em 11/05/2026)
    "misathumb": "<:995589misathumb:1503232558023053354>",
    "kaorukonom": "<:823637kaorukonom:1503232557116952606>",
    "mahitolaugh": "<:764053mahitolaugh:1503232555737153677>",
    "bombasticsideeye": "<:745171bombasticsideeye:1503232554420011088>",
    "kannayay": "<:736079kannayay:1503232552960393306>",
    "ohduck": "<:666059ohduck:1503232551232209038>",
    "kaorukosleep": "<:597974kaorukosleep:1503232549835636786>",
    "sleep_new": "<:582800sleep:1503232548157784064>",
    "kaorukoyay": "<:371208kaorukoyay:1503232543779065966>",
    "kaorukoheh": "<:363284kaorukoheh:1503232542164390010>",
    "eleggsqueeze": "<:357161eleggsqueeze:1503232531170852906>",
    "kannaamazed": "<:325237kannaamazed2:1503232521838526504>",
    "nobaraexcited": "<:313775nobaraexcited:1503232519422873702>",
    "kaorukodisgust": "<:227860kaorukodisgust:1503232517556404387>",
    "dazaishook": "<:145487dazaishook:1503232516235202691>",
    "konatapeace": "<:112183konatapeace:1503232505120034826>",
    "processando": "<a:107395processando:1503232503916527717>",
    "kannaeat": "<:84609kannaeat:1503232493221052557>",
    "pancakefail": "<:7111pancakeflipfail:1503232491148935198>"
}

THINKING_MSG = f"Estou processando... {EMOJI['processando']}"

# Logger compartilhado
logger = logging.getLogger("LiraDiscordBot")
