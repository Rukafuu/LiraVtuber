import datetime
import json
import logging
import re
import sys

from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from src.brain.tool_manager import ToolManager
from src.memory import memory
from src.modules.voice.stt_whisper import MotorSTTWhisper
from src.modules.voice.tts_selector import get_tts
from src.modules.vision.periodic_vision import VisaoNyra
from src.providers.provider_selector import ProviderSelector
from src.utils.text import limpar_texto_tts, ui
from src.config.config_loader import CONFIG

WEB_TRIGGER_TERMS = (
    "pesquisa",
    "pesquisar",
    "pesquise",
    "buscar",
    "busca",
    "busque",
    "procure",
    "procurar",
    "olha na web",
    "olha na internet",
    "na web",
    "na internet",
    "na net",
    "online",
    "google",
)

WEB_CONFIRM_YES = (
    "sim",
    "pode",
    "pode pesquisar",
    "pesquisa",
    "pesquise",
    "procura",
    "procure",
    "busca",
    "busque",
    "ok",
    "claro",
)

WEB_CONFIRM_NO = (
    "nao",
    "não",
    "nao precisa",
    "não precisa",
    "deixa",
    "deixa pra la",
    "deixa pra lá",
    "sem pesquisar",
    "sem pesquisa",
)


def _normalize_text(texto: str) -> str:
    return (texto or "").strip().lower()


def usuario_pediu_pesquisa(texto: str) -> bool:
    texto_normalizado = _normalize_text(texto)
    return any(trigger in texto_normalizado for trigger in WEB_TRIGGER_TERMS)


def resposta_confirma_pesquisa(texto: str) -> bool:
    texto_normalizado = _normalize_text(texto)
    return any(
        texto_normalizado == item or texto_normalizado.startswith(f"{item} ")
        for item in WEB_CONFIRM_YES
    )


def resposta_recusa_pesquisa(texto: str) -> bool:
    texto_normalizado = _normalize_text(texto)
    return any(
        texto_normalizado == item or texto_normalizado.startswith(f"{item} ")
        for item in WEB_CONFIRM_NO
    )


load_dotenv()

# Persona e prompt são lidos dentro do loop para hot-reload da GUI
_ultimo_provedor = CONFIG.get("LLM_PROVIDER", "groq")

db = memory("data/hana_memory.db")
tts = get_tts()
stt_motor = MotorSTTWhisper()
llm_selector = ProviderSelector()
tool_manager = ToolManager()
visao = VisaoNyra()
pesquisa_pendente = None

ui.set_banner(llm_selector.provedor_atual.upper(), f"{tts.provedor.upper()} TTS")

while True:
    try:
        # Hot-reload: recarrega config.json se a GUI alterou algo
        if CONFIG.reload():
            # Hot-swap de provedor LLM se mudou
            novo_prov = CONFIG.get("LLM_PROVIDER", "groq")
            if novo_prov != _ultimo_provedor:
                llm_selector = ProviderSelector()
                _ultimo_provedor = novo_prov
                logging.info(f"[MAIN] Provedor LLM trocado para: {novo_prov}")

        ui.novo_turno()

        # Verifica toggle STT
        if not CONFIG.get("STT_ATIVO", True):
            import time
            time.sleep(1)
            continue

        user_message = stt_motor.transcrever()

        if not user_message or user_message.strip() == "":
            continue

        ui.print_info_livre(f"Você: {user_message}")

        if "desligar sistema" in user_message.lower():
            ui.print_info_livre("Hana: Desligando... Até logo Nakamura-sama!")
            break

        if pesquisa_pendente:
            if resposta_confirma_pesquisa(user_message):
                user_message = (
                    f"{pesquisa_pendente['mensagem_original']}\n\n"
                    f"[USUARIO AUTORIZOU PESQUISA NA WEB]\n"
                    f"Consulta sugerida: {pesquisa_pendente['query']}"
                )
                pesquisa_pendente = None
            elif resposta_recusa_pesquisa(user_message):
                ai_response_falada = "Certo. Vou responder sem pesquisar na web."
                pesquisa_pendente = None

                texto_limpo_tts = limpar_texto_tts(ai_response_falada)
                if texto_limpo_tts.strip():
                    ui.print_falando(tts.provedor)
                    tts.falar(texto_limpo_tts)

                db.add_message("Nakamura", user_message)
                db.add_message("Hana", ai_response_falada)
                continue

        raw_history = db.get_messages(limit=100)

        # Lê persona e prompt a cada turno (hot-reload da GUI)
        try:
            with open("src/config/persona.txt", "r", encoding="utf-8") as f:
                personality = f.read()
        except Exception:
            personality = ""

        try:
            with open("src/config/prompt.json", "r", encoding="utf-8") as f:
                prompt = json.load(f)
        except Exception:
            prompt = {}

        current_datetime = datetime.datetime.now().strftime("%A, %d de %B de %Y, %H:%M")
        
        prompt_rules = "\n".join([f"- {k}: {v}" for k,v in prompt.items()])
        
        sistema_prompt = (
            f"=== [NÚCLEO DE PERSONALIDADE: HANA AM NAKAMURA] ===\n{personality}\n\n"
            f"=== [PROTOCOLO OPERACIONAL E REGRAS] ===\n{prompt_rules}\n\n"
            f"=== [CONTEXTO AMBIENTAL] ===\n"
            f"Data/Hora: {current_datetime}\n"
            f"LOCAL: E:\\Projeto_Hana_AI\n\n"
            "⚠️ LEMBRETE CRÍTICO: Você é a HANA. Fale como ela, sinta como ela. "
            "Nunca aja como uma IA, nunca se descreva como modelo de linguagem. "
            "Seja imersiva, sarcástica, fofa e use suas gírias naturalmente."
        )

        llm = llm_selector.get_provider()
        if not llm:
            ui.print_info_livre("Erro: O provedor LLM não conseguiu ser inicializado.")
            continue

        max_turnos = 3
        turno_atual = 0
        ai_response_falada = ""
        mensagem_usuario_interna = user_message
        
        # --- VISÃO SOB DEMANDA ---
        image_b64 = None
        if CONFIG.get("VISAO_ATIVA", False):
            try:
                res_vision = visao.capturar()
                if res_vision.get("sucesso"):
                    image_b64 = res_vision["b64"]
                    # Opacional: logging para debug
                    # logging.info("[VISÃO] Tela capturada para contexto.")
            except Exception as e:
                logging.error(f"[VISÃO] Erro ao capturar tela: {e}")

        while turno_atual < max_turnos:
            turno_atual += 1

            ai_response_full = llm.gerar_resposta(
                chat_history=raw_history,
                sistema_prompt=sistema_prompt,
                user_message=mensagem_usuario_interna,
                tools=tool_manager.ferramentas,
                image_b64=image_b64
            )

            if not ai_response_full:
                break

            tool_name = None
            tool_args = {}
            texto_sujo = ai_response_full

            try:
                if ai_response_full.strip().startswith("{") and '"acao": "tool_call"' in ai_response_full:
                    dados = json.loads(ai_response_full)
                    if dados.get("tools"):
                        primeira_tool = dados["tools"][0]
                        tool_name = primeira_tool["function"]["name"]
                        tool_args = json.loads(primeira_tool["function"]["arguments"] or "{}")
                        texto_sujo = dados.get("texto", "")
            except Exception as e:
                logging.warning(f"[MAIN] Falha ao interpretar tool_call em JSON: {e}")

            if not tool_name:
                match_call = re.search(
                    r'<execute_tool\s+name=["\'](\w+)["\'](.*?)/>',
                    texto_sujo,
                    re.DOTALL | re.IGNORECASE,
                )
                if match_call:
                    tool_name = match_call.group(1)
                    resto = match_call.group(2)
                    for m in re.finditer(r'([a-zA-Z_0-9]+)\s*=\s*["\'](.*?)["\']', resto):
                        tool_args[m.group(1)] = m.group(2)
                    texto_sujo = texto_sujo[: match_call.start()] + texto_sujo[match_call.end() :]
                else:
                    match_func = re.search(
                        r"<function=(\w+)>(.*?)</function>",
                        texto_sujo,
                        re.DOTALL | re.IGNORECASE,
                    )
                    if match_func:
                        tool_name = match_func.group(1)
                        try:
                            tool_args = json.loads(match_func.group(2).strip())
                        except Exception as e:
                            logging.warning(
                                f"[MAIN] Falha ao interpretar argumentos da tool em tag <function>: {e}"
                            )
                        texto_sujo = texto_sujo[: match_func.start()] + texto_sujo[match_func.end() :]

            if tool_name:
                if tool_name == "pesquisar_na_web" and not usuario_pediu_pesquisa(user_message):
                    pesquisa_pendente = {
                        "mensagem_original": user_message,
                        "query": tool_args.get("query", ""),
                    }
                    ai_response_falada = (
                        "Posso pesquisar na web para confirmar isso, mas prefiro sua permissão antes. "
                        "Se quiser, diga 'pode pesquisar'. Se preferir, eu sigo sem pesquisar."
                    )
                    break

                ui.print_executando(tool_name)
                resultado_sis, resumo_tts = tool_manager.executar_tool(tool_name, tool_args)

                if resumo_tts and turno_atual == 1:
                    ui.print_falando(tts.provedor)
                    tts.falar(limpar_texto_tts(resumo_tts))

                mensagem_usuario_interna = (
                    f"{mensagem_usuario_interna}\n\n"
                    f"[FERRAMENTA {tool_name} EXECUTADA - RESULTADO]:\n{resultado_sis}"
                )
                continue

            ai_response_falada = texto_sujo
            break

        if not ai_response_falada:
            continue

        # Verifica toggle TTS antes de falar
        if CONFIG.get("TTS_ATIVO", True):
            texto_limpo_tts = limpar_texto_tts(ai_response_falada)
            if texto_limpo_tts.strip():
                ui.print_falando(tts.provedor)
                tts.falar(texto_limpo_tts)

        base_user_msg = mensagem_usuario_interna.split("\n\n[FERRAMENTA")[0]
        db.add_message("Nakamura", base_user_msg)
        db.add_message("Hana", ai_response_falada)

    except KeyboardInterrupt:
        print("\n")
        ui.print_info_livre("Desligamento solicitado por KeyboardInterrupt.")
        break
    except Exception as e:
        logging.exception("[MAIN] Erro no loop principal")
        ui.print_info_livre(f"Ops, ocorreu um erro no loop principal: {e}")
        continue
