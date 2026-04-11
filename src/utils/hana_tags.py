"""
Tags XML oficiais e helpers de parsing da Hana.
"""

from __future__ import annotations

import re

THOUGHT_TAGS = ("pensamento", "thought", "think")
LEGACY_IGNORED_XML_TAGS = ("gerar_video",)
SILENT_XML_TAGS = (
    "salvar_memoria",
    "gerar_imagem",
    "editar_imagem",
    "gerar_musica",
    "acao_pc",
    "analisar_youtube",
    "usar_inbox",
    "analisar_inbox",
    "bypass",
    "resumo_imagem",
    "ferramenta_web",
)
DISPLAY_XML_TAGS = THOUGHT_TAGS + SILENT_XML_TAGS + LEGACY_IGNORED_XML_TAGS
MEDIA_XML_TAGS = (
    "gerar_imagem",
    "editar_imagem",
    "gerar_musica",
)
ASSISTANT_HISTORY_ROLES = {"hana", "assistant", "model", "ai"}


def extract_xml_actions(texto: str, tag_names: tuple[str, ...] | list[str] | None = None) -> dict[str, list[str]]:
    if not texto:
        return {}

    names = tuple(tag_names or SILENT_XML_TAGS)
    actions: dict[str, list[str]] = {}
    for tag_name in names:
        pattern = rf"<{tag_name}>(.*?)</{tag_name}>"
        actions[tag_name] = [
            item.strip()
            for item in re.findall(pattern, texto, re.DOTALL | re.IGNORECASE)
            if item and item.strip()
        ]
    return actions


def strip_xml_tags(texto: str, tag_names: tuple[str, ...] | list[str] | None = None) -> str:
    if not texto:
        return ""

    names = tuple(tag_names or DISPLAY_XML_TAGS)
    resultado = texto
    for tag_name in names:
        resultado = re.sub(
            rf"<{tag_name}>.*?</{tag_name}>",
            "",
            resultado,
            flags=re.DOTALL | re.IGNORECASE,
        )
    return resultado


def sanitize_history_message(role: str, content: str, *, empty_placeholder: str = "") -> str:
    texto = str(content or "")
    normalized_role = str(role or "").strip().lower()
    if normalized_role in ASSISTANT_HISTORY_ROLES:
        texto = strip_xml_tags(texto, DISPLAY_XML_TAGS)
        texto = re.sub(r"\n{3,}", "\n\n", texto)
        texto = "\n".join(line.rstrip() for line in texto.splitlines())
    texto = texto.strip()
    if texto:
        return texto
    if normalized_role in ASSISTANT_HISTORY_ROLES:
        return str(empty_placeholder or "").strip()
    return texto
