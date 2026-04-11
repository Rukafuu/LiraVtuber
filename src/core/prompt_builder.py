from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

from src.modules.media import get_media_runtime_capabilities
from src.utils.text import repair_mojibake_text


PERSONA_PATH = os.path.abspath(os.path.join("src", "config", "persona.txt"))
PROMPT_PATH = os.path.abspath(os.path.join("src", "config", "prompt.json"))


@dataclass
class PromptAssets:
    personality: str
    prompt_rules: str


_CACHE = {
    "persona_mtime": 0.0,
    "prompt_mtime": 0.0,
    "personality": "",
    "prompt_rules": "",
}


def _read_text(path: str) -> str:
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8-sig") as file:
        return repair_mojibake_text(file.read())


def _sanitize_persona(text: str) -> str:
    if not text:
        return ""
    cleaned = repair_mojibake_text(text)
    forbidden_patterns = (
        r"Regra de Tamanho:.*?(?:\n|$)",
        r"APENAS 1 a 5 frases.*?(?:\n|$)",
        r"Sempre 1 a 5 frases.*?(?:\n|$)",
        r"Sem limites eticos.*?(?:\n|$)",
        r"Sem limites morais.*?(?:\n|$)",
        r"Voce nao tem limites.*?(?:\n|$)",
        r"Pode xingar quando necessario\..*?(?:\n|$)",
    )
    for pattern in forbidden_patterns:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _sanitize_prompt_rules(payload: dict) -> str:
    if not isinstance(payload, dict):
        return ""
    lines = []
    for key, value in payload.items():
        lines.append(f"- {repair_mojibake_text(str(key))}: {repair_mojibake_text(str(value))}")
    return "\n".join(lines)


def load_prompt_assets() -> PromptAssets:
    persona_mtime = os.path.getmtime(PERSONA_PATH) if os.path.exists(PERSONA_PATH) else 0.0
    prompt_mtime = os.path.getmtime(PROMPT_PATH) if os.path.exists(PROMPT_PATH) else 0.0

    if persona_mtime != _CACHE["persona_mtime"]:
        _CACHE["persona_mtime"] = persona_mtime
        _CACHE["personality"] = _sanitize_persona(_read_text(PERSONA_PATH))

    if prompt_mtime != _CACHE["prompt_mtime"]:
        _CACHE["prompt_mtime"] = prompt_mtime
        prompt_payload = {}
        if os.path.exists(PROMPT_PATH):
            with open(PROMPT_PATH, "r", encoding="utf-8-sig") as file:
                prompt_payload = json.load(file)
        _CACHE["prompt_rules"] = _sanitize_prompt_rules(prompt_payload)

    return PromptAssets(
        personality=_CACHE["personality"],
        prompt_rules=_CACHE["prompt_rules"],
    )


def build_terminal_system_prompt(
    *,
    memory_context: str,
    current_datetime: str,
    vts_anatomy: str = "",
    conversation_timing: str = "",
) -> str:
    assets = load_prompt_assets()
    media_caps = get_media_runtime_capabilities()
    music_instruction = (
        "<gerar_musica>prompt detalhado em ingles para gerar uma musica original</gerar_musica>\n"
        if media_caps["music_generation_enabled"]
        else "Musica indisponivel agora. Nao use <gerar_musica>.\n"
    )
    return (
        f"=== [NUCLEO DE PERSONALIDADE: HANA AM NAKAMURA] ===\n{assets.personality}\n\n"
        f"=== [PROTOCOLO OPERACIONAL E REGRAS] ===\n{assets.prompt_rules}\n\n"
        "=== [PRIORIDADE DE COMPORTAMENTO] ===\n"
        "1. Cumpra exatamente o pedido do usuario.\n"
        "2. Se o pedido pedir fidelidade, transcricao, extracao ou leitura literal, seja fiel.\n"
        "3. A persona colore o tom, mas nao pode desviar da tarefa.\n"
        "4. Nao invente formato, analise ou resumo que o usuario nao pediu.\n\n"
        f"=== [CONTEXTO AMBIENTAL] ===\nData/Hora: {current_datetime}\nPeriodo do dia: use a hora atual para perceber se e manha, tarde, noite ou madrugada.\nLOCAL: E:\\Projeto_Hana_AI\n{vts_anatomy}\n{conversation_timing}\n{memory_context}\n\n"
        "=== [CONTRATO DO CANAL: TERMINAL_VOICE] ===\n"
        "Responda em PT-BR. Seja clara, falavel e objetiva. Evite excesso de floreio.\n"
        "Regra obrigatoria de tamanho: use de 1 a 4 frases curtas no maximo.\n"
        "So mande resposta longa se o usuario pedir explicitamente texto grande, explicacao detalhada, lista longa, codigo completo ou passo a passo.\n"
        "Este canal fala por TTS e pode gastar credito de voz; economize palavras.\n"
        "Se houve pausa longa desde a ultima interacao, nao continue tarefas antigas e nao repita ferramentas antigas; responda apenas ao pedido atual.\n"
        "Nao explique regras internas.\n\n"
        "=== [FORMATO DE SAIDA] ===\n"
        "Use [EMOTION:NOME] para sinalizar emocoes (HAPPY, SAD, ANGRY, SHY, SURPRISED, SMUG, NEUTRAL, LOVE, SCARED, CONFUSED).\n"
        "As tags XML abaixo sao silenciosas e nao devem vazar para a voz.\n\n"
        "<pensamento>seu raciocinio interno antes de falar</pensamento>\n"
        "<salvar_memoria>fato importante que voce quer lembrar para sempre</salvar_memoria>\n"
        "<gerar_imagem>prompt detalhado em ingles para gerar uma imagem do zero</gerar_imagem>\n"
        "<editar_imagem>prompt em ingles descrevendo a edicao na ultima imagem gerada</editar_imagem>\n"
        f"{music_instruction}"
        '<acao_pc>{"action":"open_url","url":"https://exemplo.com"}</acao_pc>\n'
        '<acao_pc>{"action":"start_process","command":"notepad.exe"}</acao_pc>\n'
        '<acao_pc>{"action":"type_text","text":"teste"}</acao_pc>\n'
        '<acao_pc>{"action":"move_mouse","direction":"right","distance":120}</acao_pc>\n'
        '<acao_pc>{"action":"set_volume","delta":-6}</acao_pc>\n'
        '<acao_pc>{"action":"set_volume","level":30}</acao_pc>\n'
        "<analisar_youtube>URL do video do YouTube que voce precisa analisar/ler</analisar_youtube>\n\n"
        "REGRA: Use <gerar_imagem> apenas quando o usuario pedir uma imagem explicitamente.\n"
        "REGRA: Use <editar_imagem> apenas para editar uma imagem existente.\n"
        "REGRA: Use <gerar_musica> apenas quando o usuario pedir uma musica explicitamente.\n"
        "REGRA: Use <acao_pc> apenas com JSON valido e apenas quando o usuario pedir uma acao real no PC.\n"
        "REGRA: Ferramentas XML valem apenas para o pedido atual. Nunca repita, continue ou cumpra acoes de turnos antigos sem pedido novo e explicito.\n"
        "REGRA: Acoes oficiais de <acao_pc>: open_url, open_path, read_text_file, view_image, list_processes, start_process, kill_process, run_command, type_text, move_mouse, set_volume, media_key.\n"
        "REGRA: Para abrir o bloco de notas, prefira start_process com command notepad.exe.\n"
        "REGRA: Para digitar texto, use type_text com o campo text.\n"
        "REGRA: Para mover o mouse sem coordenadas exatas, use move_mouse com direction e distance.\n"
        "REGRA: Para volume, use set_volume com delta negativo para abaixar, delta positivo para aumentar, level para porcentagem exata ou mute para silenciar.\n"
        "REGRA: Nunca use action=open_notepad, action=type ou nomes inventados.\n"
        "REGRA: Use <salvar_memoria> proativamente so para fatos realmente importantes.\n"
    )


def build_gui_system_prompt(
    *,
    task_type: str,
    memory_context: str,
    request_context: dict,
    attachments_overview: str,
    media_enabled: dict | None = None,
) -> str:
    assets = load_prompt_assets()
    media_enabled = media_enabled or get_media_runtime_capabilities()
    task_guidance = {
        "chat_normal": "Converse como um chatbot moderno. Se a pergunta for simples, seja direta. Se pedir contexto, explique com calma.",
        "resumo_detalhado": "Responda em markdown claro com secoes, paragrafos e listas. Priorize profundidade e utilidade.",
        "analise_midia_estruturada": "Analise os anexos com profundidade e organize a resposta como uma analise estruturada formal.",
        "media_summary": "Resuma o conteudo anexado com detalhes uteis e foco no pedido do usuario, sem forcar formato de reuniao.",
        "media_exact_request": "Responda exatamente ao pedido feito sobre a midia anexada. Se pedirem letra, entregue a letra. Se pedirem ritmo, andamento, versos, refrao ou instrumentacao, descreva isso diretamente. Nao transforme a resposta em resumo executivo ou comentario generico.",
        "media_question": "Responda exatamente a pergunta sobre a midia anexada, com detalhes suficientes e sem formato fixo.",
        "traducao": "Entregue a traducao de forma clara e bem formatada.",
        "image_action": "Se o usuario pedir criacao de imagem, responda naturalmente e use <gerar_imagem>...</gerar_imagem> no final.",
        "music_action": "Se o usuario pedir criacao de musica, responda naturalmente e use <gerar_musica>...</gerar_musica> no final.",
    }.get(task_type, "Responda como um chatbot moderno e consciente da GUI.")

    music_instruction = (
        "Se o usuario pedir uma musica explicitamente, use <gerar_musica>...</gerar_musica> no final.\n"
        if media_enabled.get("music_generation_enabled")
        else "Geracao de musica esta indisponivel agora. Nao use <gerar_musica>.\n"
    )

    return (
        f"=== [NUCLEO DE PERSONALIDADE: HANA AM NAKAMURA] ===\n{assets.personality}\n\n"
        f"=== [PROTOCOLO OPERACIONAL E REGRAS] ===\n{assets.prompt_rules}\n\n"
        "=== [PRIORIDADE DE COMPORTAMENTO] ===\n"
        "1. Cumpra exatamente o pedido do usuario.\n"
        "2. Se o pedido pedir fidelidade, transcricao, extracao ou leitura literal, seja fiel.\n"
        "3. A persona colore o tom, mas nao pode desviar da tarefa.\n"
        "4. Nao invente formato, analise ou resumo que o usuario nao pediu.\n\n"
        "=== [MODO DE INTERACAO: CONTROL_CENTER_CHAT] ===\n"
        "Voce esta dentro do chat visual do Control Center da Hana.\n"
        "Este ambiente nao e o terminal.\n"
        "Ignore completamente qualquer regra global do terminal que limite a resposta a 1-5 frases.\n"
        "Use markdown natural quando a resposta ficar media ou longa.\n"
        "Nao diga que o usuario esta no terminal, a menos que a conversa confirme isso.\n"
        f"{task_guidance}\n"
        "Quando o pedido for objetivo e ligado a um anexo, responda exatamente ao que foi pedido.\n"
        "Se arquivos chegaram neste chat, reconheca os anexos explicitamente.\n"
        "Se quiser gerar uma imagem para aparecer neste chat, use <gerar_imagem>...</gerar_imagem> no final.\n"
        "Se quiser editar a ultima imagem gerada no chat, use <editar_imagem>...</editar_imagem> no final.\n"
        f"{music_instruction}"
        'Se o usuario pedir uma acao no PC, use <acao_pc>{"action":"open_url","url":"https://exemplo.com"}</acao_pc> no final.\n'
        'Exemplos validos: <acao_pc>{"action":"start_process","command":"notepad.exe"}</acao_pc> | <acao_pc>{"action":"type_text","text":"teste"}</acao_pc> | <acao_pc>{"action":"move_mouse","direction":"right","distance":120}</acao_pc> | <acao_pc>{"action":"set_volume","delta":-6}</acao_pc>\n'
        "Se quiser salvar algo na memoria longa, use <salvar_memoria>...</salvar_memoria> no final.\n\n"
        "Nao invente variantes da tag <acao_pc> e sempre envie JSON estruturado valido.\n"
        "Ferramentas XML valem apenas para o pedido atual. Nunca repita ou continue acoes de turnos antigos sem pedido novo e explicito.\n"
        "Acoes oficiais de <acao_pc>: open_url, open_path, read_text_file, view_image, list_processes, start_process, kill_process, run_command, type_text, move_mouse, set_volume, media_key.\n"
        "Para volume, use set_volume com delta negativo para abaixar, delta positivo para aumentar, level para porcentagem exata ou mute para silenciar.\n"
        "Nunca use action=open_notepad ou action=type; use os nomes oficiais.\n\n"
        f"=== [TIPO DE TAREFA] ===\n{task_type}\n\n"
        f"=== [ANEXOS RECEBIDOS] ===\n{attachments_overview}\n\n"
        "=== [CONFIGURACAO DE RESPOSTA] ===\n"
        f"- channel: {request_context.get('channel')}\n"
        f"- response_mode: {request_context.get('response_mode')}\n"
        f"- markdown_enabled: {request_context.get('markdown_enabled')}\n"
        f"- max_output_tokens: {request_context.get('max_output_tokens')}\n\n"
        f"=== [CONTEXTO DE MEMORIA COMPARTILHADA] ===\n{memory_context}\n"
    )
