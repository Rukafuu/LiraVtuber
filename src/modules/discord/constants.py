import discord
import logging
import os
import re

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


def _build_emoji_lookup() -> dict[str, str]:
    """Mapeia :nome: e :764053nome: para o formato <:nome:id> do Discord."""
    lookup: dict[str, str] = {}
    for key, val in EMOJI.items():
        lookup[key.lower()] = val
        match = re.match(r"<a?:([^:>]+):\d+>", val)
        if match:
            discord_name = match.group(1).lower()
            lookup[discord_name] = val
            bare = re.sub(r"^\d+", "", discord_name)
            if bare:
                lookup[bare] = val
    return lookup


EMOJI_LOOKUP = _build_emoji_lookup()


def substitute_discord_emojis(text: str) -> str:
    """Converte :mahitolaugh:, :764053mahitolaugh: ou :7111pancakeflipfail: em emojis custom do servidor."""
    if not text:
        return text

    def _replace(match: re.Match) -> str:
        token = match.group(1).lower()

        # 1. Tenta direto (chave curta como 'mahitolaugh')
        if token in EMOJI_LOOKUP:
            return EMOJI_LOOKUP[token]

        # 2. Remove prefixo numérico do início (ex: '764053mahitolaugh' → 'mahitolaugh')
        bare = re.sub(r"^\d+", "", token)
        if bare and bare in EMOJI_LOOKUP:
            return EMOJI_LOOKUP[bare]

        # 3. Tenta o nome completo com números no meio (ex: '7111pancakeflipfail')
        #    procura em todos os valores do EMOJI pelo nome interno do Discord
        for key, val in EMOJI.items():
            inner_match = re.match(r"<a?:([^:>]+):\d+>", val)
            if inner_match and inner_match.group(1).lower() == token:
                return val

        # 4. Não encontrou — mantém como está (não quebra texto normal)
        return match.group(0)

    # Aceita :mahitolaugh:, :764053mahitolaugh:, :7111pancakeflipfail:
    # Não confunde com <:nome:id> já convertido
    return re.sub(r"(?<!<):([0-9]*[a-zA-Z][a-zA-Z0-9_]*):(?!\d+>)", _replace, text)


# Logger compartilhado
logger = logging.getLogger("LiraDiscordBot")
