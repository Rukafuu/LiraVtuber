"""
Registro canonico de ferramentas da Lira (XML / executar_tool).

Nao usa schema OpenAI function-calling — apenas IDs estaveis e tags XML.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolSpec:
    tool_id: str
    xml_tags: tuple[str, ...]
    description: str
    prompt_hint: str = ""

    @property
    def primary_xml_tag(self) -> str | None:
        return self.xml_tags[0] if self.xml_tags else None


TOOL_REGISTRY: dict[str, ToolSpec] = {
    "anotar_fato": ToolSpec(
        tool_id="anotar_fato",
        xml_tags=(),
        description="Grava fato permanente no grafo de conhecimento (sujeito, relacao, objeto).",
        prompt_hint="Use via memoria estruturada quando o usuario pedir para lembrar um fato com sujeito/relacao/objeto.",
    ),
    "pesquisa_web": ToolSpec(
        tool_id="pesquisa_web",
        xml_tags=("ferramenta_web",),
        description="Busca na internet em tempo real (Tavily legado ou MCP).",
        prompt_hint=(
            "<ferramenta_web>termo</ferramenta_web> OU "
            "<mcp>tavily/search\\ntermo de busca</mcp> (preferido com MCP Gateway ligado)."
        ),
    ),
    "mcp": ToolSpec(
        tool_id="mcp",
        xml_tags=("mcp",),
        description="Ferramentas MCP externas via gateway (Tavily, GitHub, etc.).",
        prompt_hint=(
            "<mcp>servidor/tool</mcp> na primeira linha; na segunda linha o argumento (texto ou JSON). "
            "Ex.: <mcp>tavily/search\\nprecos RTX 5090</mcp>"
        ),
    ),
    "ler_tela_ocr": ToolSpec(
        tool_id="ler_tela_ocr",
        xml_tags=("ler_tela_ocr", "ocr_tela"),
        description="Captura a tela e extrai texto visivel (OCR).",
        prompt_hint="<ler_tela_ocr></ler_tela_ocr> quando o usuario pedir para ler o que esta na tela.",
    ),
    "gerar_imagem": ToolSpec(
        tool_id="gerar_imagem",
        xml_tags=(),
        description="Gera imagem via Pollinations/FLUX (executor interno; tag <gerar_imagem> pode usar handler do app).",
        prompt_hint="<gerar_imagem>prompt em ingles</gerar_imagem> no app VTuber usa o gerador local preferido.",
    ),
    "analisar_youtube": ToolSpec(
        tool_id="analisar_youtube",
        xml_tags=("analisar_youtube",),
        description="Baixa transcricao de video do YouTube e injeta no contexto.",
        prompt_hint="<analisar_youtube>URL completa do video</analisar_youtube>",
    ),
}

# Tag XML -> tool_id (primeira tag de cada spec + aliases)
XML_TAG_TO_TOOL_ID: dict[str, str] = {}
for spec in TOOL_REGISTRY.values():
    for tag in spec.xml_tags:
        XML_TAG_TO_TOOL_ID[tag.lower()] = spec.tool_id

# Nomes alternativos aceitos em executar_tool(nome, args)
TOOL_ALIASES: dict[str, str] = {
    "ferramenta_web": "pesquisa_web",
    "ocr_tela": "ler_tela_ocr",
    "pesquisa_web": "pesquisa_web",
    "web": "pesquisa_web",
    "youtube": "analisar_youtube",
}


def resolve_tool_id(name: str) -> str:
    key = (name or "").strip().lower()
    if key in TOOL_REGISTRY:
        return key
    return TOOL_ALIASES.get(key, key)


def tool_ids_for_xml_tags() -> tuple[str, ...]:
    """Tags XML que disparam executar_tool via registry."""
    return tuple(sorted(XML_TAG_TO_TOOL_ID.keys()))


def prompt_lines_for_tools(*, include_ocr: bool = True) -> str:
    lines = []
    for spec in TOOL_REGISTRY.values():
        if spec.prompt_hint:
            if not include_ocr and spec.tool_id == "ler_tela_ocr":
                continue
            lines.append(spec.prompt_hint)
    return "\n".join(lines)