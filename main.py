import datetime
import json
import logging
import os
import re
import sys
import warnings

# === SILENCIAR AVISOS E LOGS BARULHENTOS (antes de qualquer import) ===
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"

from dotenv import load_dotenv

logging.basicConfig(level=logging.WARNING, format="%(asctime)s - %(levelname)s - %(message)s")

for _noisy in ["httpx", "httpcore", "chromadb", "sentence_transformers",
               "huggingface_hub", "urllib3", "opentelemetry", "google"]:
    logging.getLogger(_noisy).setLevel(logging.ERROR)

logging.getLogger("src").setLevel(logging.INFO)

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from src.brain.tool_manager import ToolManager
from src.memory.memory_manager import HanaMemoryManager
from src.modules.voice.stt_whisper import MotorSTTWhisper
from src.modules.voice.tts_selector import get_tts
from src.modules.vision.periodic_vision import VisaoNyra
from src.modules.vision.image_gen import HanaImageGen
from src.modules.emotion_engine import EmotionEngine
from src.modules.vts_controller import VTSController
from src.providers.provider_selector import ProviderSelector
from src.utils.text import limpar_texto_tts, ui
from src.utils.sentence_divider import SentenceDivider
from src.config.config_loader import CONFIG


load_dotenv()

_ultimo_provedor = CONFIG.get("LLM_PROVIDER", "groq")

tts = get_tts()
stt_motor = MotorSTTWhisper()
llm_selector = ProviderSelector()
memory_manager = HanaMemoryManager("data/hana_memory.db")
tool_manager = ToolManager(memory_manager=memory_manager)
visao = VisaoNyra()

# === Motor de Emoções ===
emotion_engine = EmotionEngine()

# === Gerador de Imagens ===
image_gen = HanaImageGen()

# === Controlador VTube Studio ===
vts_controller = None
if CONFIG.get("VTUBESTUDIO_ATIVO", False):
    vts_cfg = CONFIG.get("VTUBE_STUDIO", {})
    if isinstance(vts_cfg, dict):
        vts_controller = VTSController(
            host=vts_cfg.get("host", "localhost"),
            port=vts_cfg.get("port", 8001),
            emotion_map=vts_cfg.get("emotion_map", {})
        )
        emotion_engine.registrar_callback_emocao(vts_controller.trigger_emotion)
        vts_controller.start()

# Banner
_llm_model = CONFIG.get("LLM_PROVIDERS", {}).get(_ultimo_provedor, {}).get("modelo", "desconhecido")
ui.set_banner(
    stt_info="GROQ WHISPER",
    tts_info=f"{tts.provedor.upper()} TTS",
    provider_info=llm_selector.provedor_atual.upper(),
    model_info=_llm_model
)

while True:
    try:
        # Hot-reload
        if CONFIG.reload():
            novo_prov = CONFIG.get("LLM_PROVIDER", "groq")
            if novo_prov != _ultimo_provedor:
                llm_selector = ProviderSelector()
                _ultimo_provedor = novo_prov
                logging.info(f"[MAIN] Provedor LLM trocado para: {novo_prov}")

            # Hot-reload VTube Studio
            if CONFIG.get("VTUBESTUDIO_ATIVO", False) and vts_controller is None:
                vts_cfg = CONFIG.get("VTUBE_STUDIO", {})
                if isinstance(vts_cfg, dict):
                    vts_controller = VTSController(
                        host=vts_cfg.get("host", "localhost"),
                        port=vts_cfg.get("port", 8001),
                        emotion_map=vts_cfg.get("emotion_map", {})
                    )
                    emotion_engine.registrar_callback_emocao(vts_controller.trigger_emotion)
                    vts_controller.start()
            elif not CONFIG.get("VTUBESTUDIO_ATIVO", False) and vts_controller is not None:
                vts_controller.stop()
                vts_controller = None

        ui.novo_turno()
        emotion_engine.novo_turno()

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

        # --- MEMÓRIA HÍBRIDA ---
        mem_context = memory_manager.get_context(user_message)
        raw_history = memory_manager.get_messages(limit=100)

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
        prompt_rules = "\n".join([f"- {k}: {v}" for k, v in prompt.items()])

        # --- FERRAMENTAS DE IMAGEM (NOVO) ---
        # Novo técnica de XML que roubei do Evertson
        # <pensamento>seu raciocínio interno antes de falar</pensamento>
        # <salvar_memoria>fato importante que você quer lembrar para sempre</salvar_memoria>
        # <gerar_imagem>prompt detalhado em inglês para gerar uma imagem DO ZERO</gerar_imagem>
        # <editar_imagem>prompt em inglês descrevendo a edição na ÚLTIMA imagem gerada</editar_imagem>
        # <ferramenta_web>consulta em inglês para pesquisar na internet</ferramenta_web>
        
        sistema_prompt = (
            f"=== [NÚCLEO DE PERSONALIDADE: HANA AM NAKAMURA] ===\n{personality}\n\n"
            f"=== [PROTOCOLO OPERACIONAL E REGRAS] ===\n{prompt_rules}\n\n"
            f"=== [CONTEXTO AMBIENTAL] ===\n"
            f"Data/Hora: {current_datetime}\n"
            f"LOCAL: E:\\Projeto_Hana_AI\n"
            f"{mem_context}\n\n"
            "⚠️ LEMBRETE CRÍTICO: Você é a HANA. Fale como ela, sinta como ela. "
            "Nunca aja como uma IA, nunca se descreva como modelo de linguagem. "
            "Seja imersiva, sarcástica, fofa e use suas gírias naturalmente.\n\n"
            "=== [FORMATO DE SAÍDA] ===\n"
            "Use [EMOTION:NOME] para sinalizar suas emoções (HAPPY, SAD, ANGRY, SHY, SURPRISED, SMUG, NEUTRAL, LOVE, SCARED, CONFUSED).\n\n"
            "=== [HABILIDADES ESPECIAIS: TAGS XML] ===\n"
            "Você pode executar ações silenciosas usando tags XML. Elas NÃO serão lidas em voz alta.\n"
            "IMPORTANTE: Coloque as tags SEPARADAS do texto falado, de preferência no final da resposta.\n\n"
            "Tags disponíveis:\n"
            "<pensamento>seu raciocínio interno antes de falar</pensamento>\n"
            "<salvar_memoria>fato importante que você quer lembrar para sempre</salvar_memoria>\n"
            "<gerar_imagem>prompt detalhado em inglês para gerar uma imagem DO ZERO</gerar_imagem>\n"
            "<editar_imagem>prompt em inglês descrevendo a edição na ÚLTIMA imagem gerada</editar_imagem>\n"
            "<analisar_youtube>URL do vídeo do YouTube que você precisa analisar/ler</analisar_youtube>\n\n"
            "Exemplo de resposta com geração:\n"
            "<pensamento>O mestre quer que eu decore o nome do gato dele</pensamento>\n"
            "[EMOTION:HAPPY] Anotado, mestre! Já gravei no meu cérebro que seu gato se chama Mimi, fufu.\n"
            "<salvar_memoria>O gato do Nakamura se chama Mimi</salvar_memoria>\n\n"
            "Exemplo de edição (SOMENTE após já ter uma imagem gerada):\n"
            "[EMOTION:HAPPY] Pronto, editei a imagem como você pediu!\n"
            "<editar_imagem>change the background to a beautiful sunset with orange sky</editar_imagem>\n\n"
            "REGRA: Só use <gerar_imagem> quando o mestre PEDIR uma imagem explicitamente.\n"
            "REGRA: Só use <editar_imagem> quando o mestre pedir para ALTERAR/EDITAR uma imagem já existente.\n"
            "REGRA: Use <salvar_memoria> PROATIVAMENTE quando o mestre contar algo pessoal importante."
        )

        llm = llm_selector.get_provider()
        if not llm:
            ui.print_info_livre("Erro: O provedor LLM não conseguiu ser inicializado.")
            continue

        # --- VISÃO SOB DEMANDA ---
        image_b64 = None
        if CONFIG.get("VISAO_ATIVA", False):
            try:
                res_vision = visao.capturar()
                if res_vision.get("sucesso"):
                    image_b64 = res_vision["b64"]
            except Exception as e:
                logging.error(f"[VISÃO] Erro ao capturar tela: {e}")

        # ==============================================================
        # STREAMING DIRETO — Uma única chamada à LLM
        # O stream aparece no terminal em tempo real (visual rápido).
        # A voz sai INTEIRA no final — sem cortes.
        # ==============================================================
        ui.print_pensando(llm.provedor.upper())

        full_raw_response = []
        full_tts_text = []  # Acumula TUDO para falar uma vez só
        divider = SentenceDivider(faster_first_response=True)

        token_stream = llm.gerar_resposta_stream(
            chat_history=raw_history,
            sistema_prompt=sistema_prompt,
            user_message=user_message,
            image_b64=image_b64
        )

        for chunk in divider.process_stream(token_stream):
            if chunk.is_thought:
                # Pensamento interno — NÃO fala, mostra na GUI
                emotion_engine.processar_pensamento(chunk.thought)
                full_raw_response.append(chunk.raw)
            else:
                # Processar emoções (dispara VTS em tempo real)
                for emo in chunk.emotions:
                    emotion_engine.processar_emocao(emo)

                # Imprimir no terminal em tempo real (visual rápido)
                print(f"{ui.C_NYRA}[HANA]{ui.C_RST}: {chunk.text}")
                full_raw_response.append(chunk.raw)

                # Acumular texto limpo para TTS
                texto_tts = limpar_texto_tts(chunk.text)
                if texto_tts.strip():
                    full_tts_text.append(texto_tts.strip())

        # ── FALA ÚNICA: Junta tudo e fala uma vez só ──
        texto_final_tts = " ".join(full_tts_text)
        if texto_final_tts.strip() and CONFIG.get("TTS_ATIVO", True):
            ui.print_falando(tts.provedor)
            tts.falar(texto_final_tts)

        ai_response_falada = " ".join(full_raw_response)

        # ==============================================================
        # PÓS-PROCESSAMENTO: Parser XML de ações silenciosas
        # Processa tags embutidas na resposta da Hana.
        # ==============================================================

        # 1. <salvar_memoria>conteúdo</salvar_memoria>
        for match in re.finditer(r'<salvar_memoria>(.*?)</salvar_memoria>', ai_response_falada, re.DOTALL):
            conteudo = match.group(1).strip()
            if conteudo:
                try:
                    memory_manager.rag.add_memory(conteudo, metadata={"role": "hana", "source": "xml_tag"})
                    memory_manager.graph.add_fact("hana_nota", "deve_lembrar", conteudo[:200])
                    logging.info(f"[XML] 💾 Memória salva: {conteudo[:80]}...")
                except Exception as e:
                    logging.error(f"[XML] Erro ao salvar memória: {e}")

        # 2. <gerar_imagem>prompt</gerar_imagem>
        for match in re.finditer(r'<gerar_imagem>(.*?)</gerar_imagem>', ai_response_falada, re.DOTALL):
            prompt_img = match.group(1).strip()
            if prompt_img:
                logging.info(f"[XML] 🎨 Gerando imagem: {prompt_img[:80]}...")
                image_gen.generate_and_show(prompt_img)

        # 3. <editar_imagem>prompt de edição</editar_imagem>
        for match in re.finditer(r'<editar_imagem>(.*?)</editar_imagem>', ai_response_falada, re.DOTALL):
            prompt_edit = match.group(1).strip()
            if prompt_edit:
                logging.info(f"[XML] ✏️ Editando imagem: {prompt_edit[:80]}...")
                image_gen.edit_and_show(prompt_edit)

        # 4. <analisar_youtube>url</analisar_youtube>
        for match in re.finditer(r'<analisar_youtube>(.*?)</analisar_youtube>', ai_response_falada, re.DOTALL):
            url = match.group(1).strip()
            if url:
                ui.print_executando("analisar_youtube")
                resultado_sis, resumo_tts = tool_manager.executar_tool("analisar_youtube", {"url": url})
                if resumo_tts:
                    ui.print_falando(tts.provedor)
                    tts.falar(limpar_texto_tts(resumo_tts))
                if resultado_sis:
                    # Injeta a legenda gigante no banco / contexto
                    memory_manager.add_interaction("System", resultado_sis)

        if not ai_response_falada:
            continue

        # Salva na memória
        memory_manager.add_interaction("Nakamura", user_message)
        memory_manager.add_interaction("Hana", ai_response_falada)

    except KeyboardInterrupt:
        print("\n")
        ui.print_info_livre("Desligamento solicitado por KeyboardInterrupt.")
        break
    except Exception as e:
        logging.exception("[MAIN] Erro no loop principal")
        ui.print_info_livre(f"Ops, ocorreu um erro no loop principal: {e}")
        continue
