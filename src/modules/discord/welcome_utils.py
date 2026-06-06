"""Utilitários de boas-vindas/despedidas (mensagens e GIFs aleatórios)."""
from __future__ import annotations

import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import discord

DEFAULT_WELCOME_MESSAGES: list[str] = [
    "Eiii {user}! Bem-vindo(a) ao **{server}**~ Agora somos **{count}**! 🌸",
    "Olá {user}! A **{server}** ficou mais bonita com você aqui. Somos {count}! ✨",
    "{user} acabou de pousar na **{server}**! Membro nº {count} — seja muito bem-vindo(a)! 💜",
    "Yatta~ {user} entrou! **{server}** te recebe de braços abertos ({count} membros)! 🎉",
    "Shh... ouvi chegada nova: {user}! Bem-vindo(a) à **{server}** ({count})! 🌙",
]

DEFAULT_LEAVE_MESSAGES: list[str] = [
    "Poxa, **{user}** saiu da **{server}**... Volta logo! 😢",
    "**{user}** partiu da **{server}**. A gente sente sua falta! 💔",
    "Bye bye {user}~ A **{server}** não será a mesma sem você.",
    "{user} escapou da **{server}**... Até a próxima, ok?",
]

DEFAULT_WELCOME_GIF_CATEGORIES: list[str] = [
    "wave", "happy", "hug", "dance", "blush",
]

DEFAULT_LEAVE_GIF_CATEGORIES: list[str] = [
    "cry", "wave", "pout",
]


def format_template(template: str, member: "discord.Member") -> str:
    return (
        template.replace("{user}", member.mention)
        .replace("{server}", member.guild.name)
        .replace("{count}", str(member.guild.member_count))
        .replace("{name}", member.display_name)
    )


def format_leave_template(template: str, member: "discord.Member") -> str:
    return (
        template.replace("{user}", member.display_name)
        .replace("{name}", member.display_name)
        .replace("{server}", member.guild.name)
    )


def migrate_guild_config(cfg: dict) -> dict:
    """Compatível com welcome.json antigo (welcome_msg / leave_msg)."""
    if cfg.get("welcome_msg") and not cfg.get("welcome_messages"):
        cfg["welcome_messages"] = [cfg["welcome_msg"]]
    if cfg.get("leave_msg") and not cfg.get("leave_messages"):
        cfg["leave_messages"] = [cfg["leave_msg"]]

    cfg.setdefault("welcome_messages", [])
    cfg.setdefault("leave_messages", [])
    cfg.setdefault("welcome_random_msg", True)
    cfg.setdefault("welcome_random_gif", True)
    cfg.setdefault("leave_random_msg", True)
    cfg.setdefault("leave_random_gif", False)
    cfg.setdefault("welcome_gif_categories", list(DEFAULT_WELCOME_GIF_CATEGORIES))
    cfg.setdefault("leave_gif_categories", list(DEFAULT_LEAVE_GIF_CATEGORIES))
    return cfg


def pick_message(cfg: dict, member: "discord.Member", *, leaving: bool = False) -> str:
    if leaving:
        pool = list(cfg.get("leave_messages") or [])
        defaults = DEFAULT_LEAVE_MESSAGES
        random_on = cfg.get("leave_random_msg", True)
        formatter = format_leave_template
    else:
        pool = list(cfg.get("welcome_messages") or [])
        defaults = DEFAULT_WELCOME_MESSAGES
        random_on = cfg.get("welcome_random_msg", True)
        formatter = format_template

    if not pool:
        pool = list(defaults)
    elif random_on:
        pool = pool + defaults

    if not random_on:
        template = (cfg.get("leave_messages") or cfg.get("welcome_messages") or [defaults[0]])[0]
        if leaving and cfg.get("leave_msg"):
            template = cfg["leave_msg"]
        elif not leaving and cfg.get("welcome_msg"):
            template = cfg["welcome_msg"]
        return formatter(template, member)

    return formatter(random.choice(pool), member)


def pick_gif_category(cfg: dict, *, leaving: bool = False) -> str | None:
    if leaving:
        if not cfg.get("leave_random_gif", False):
            return None
        cats = cfg.get("leave_gif_categories") or DEFAULT_LEAVE_GIF_CATEGORIES
    else:
        if not cfg.get("welcome_random_gif", True):
            return None
        cats = cfg.get("welcome_gif_categories") or DEFAULT_WELCOME_GIF_CATEGORIES
    return random.choice(cats) if cats else None