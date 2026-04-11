import datetime
import json
import logging
import os
import re
import sys
import threading
import time
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
from src.modules.voice.audio_control import poll_external_stop, register_stop_callback, request_global_stop
from src.modules.voice.tts_selector import get_tts
from src.modules.vision.periodic_vision import VisaoNyra
from src.modules.vision.image_gen import HanaImageGen
from src.modules.media import HanaMusicGen, get_media_settings
from src.modules.emotion_engine import EmotionEngine
from src.modules.tools.pc_control import execute_pc_action
from src.modules.vts_controller import VTSController
from src.core.prompt_builder import build_terminal_system_prompt
from src.providers.provider_selector import ProviderSelector
from src.core.request_profiles import build_request_context
from src.utils.hana_tags import extract_xml_actions
from src.utils.text import limpar_texto_tts, ui
from src.utils.sentence_divider import SentenceDivider
from src.config.config_loader import CONFIG
from src.core.runtime_capabilities import get_stop_hotkey_settings

try:
    import keyboard
except Exception:
    keyboard = None


# === Sinais de Estado (Neuro style) ===
class HanaSignals:
    def __init__(self):
        self.HANA_SPEAKING = False
        self.STT_ACTIVE = True

signals = HanaSignals()

tts = get_tts()
stt_motor = MotorSTTWhisper()
llm_selector = ProviderSelector()
memory_manager = HanaMemoryManager("data/hana_memory.db")
tool_manager = ToolManager(memory_manager=memory_manager)
visao = VisaoNyra()

# === Motor de Emoções ===
emotion_engine = EmotionEngine()

def _trigger_vts_emotion(emotion: str):
    global vts_controller
    if vts_controller is not None:
        vts_controller.trigger_emotion(emotion)

emotion_engine.registrar_callback_emocao(_trigger_vts_emotion)

# === Gerador de Mídia ===
image_gen = HanaImageGen()
music_gen = HanaMusicGen()


def _classify_terminal_task(user_message: str) -> str:
    lowered = (user_message or "").strip().lower()
    if re.search(r"\b(gera|cria|criar|faz|fa[cç]a|comp[oô]e|compoe|componha).*(m[uú]sica|musica|trilha|beat|can[cç][aã]o|cancao|song)\b", lowered):
        return "music_action"
    if re.search(r"\b(gera|cria|criar|faz|fa[cç]a).*(imagem|foto|arte)\b", lowered):
        return "image_action"
    return "chat_normal"


def _build_media_request_meta(kind: str) -> dict:
    settings = get_media_settings()
    media_cfg = settings["music"]
    return {
        "provider": "google_cloud",
        "backend": media_cfg.get("backend"),
        "model": media_cfg.get("model"),
        "routed": True,
    }


def _monitor_terminal_media_job(kind: str, job_id: str):
    generator = music_gen
    kind_label = "música"

    while True:
        status = generator.get_status(job_id)
        state = status.get("state")
        if state in {"queued", "running"}:
            time.sleep(2.0)
            continue

        if state == "completed":
            output_path = status.get("output_path")
            ui.print_info_livre(f"Hana: {kind_label.capitalize()} pronto em {output_path}")
            if get_media_settings().get("auto_open_terminal_outputs"):
                try:
                    os.startfile(output_path)
                except Exception as e:
                    logging.warning("[MEDIA] Falha ao abrir saída automaticamente: %s", e)
            return

        if state == "cancelled":
            ui.print_info_livre(f"Hana: Geração de {kind_label} cancelada.")
            return

        ui.print_info_livre(f"Hana: Falha ao gerar {kind_label}: {status.get('error') or 'erro desconhecido'}")
        return


def _start_terminal_media_job(kind: str, prompt: str):
    generator = music_gen
    kind_label = "música"
    try:
        job_id = generator.submit(prompt, origin="terminal_voice", request_meta=_build_media_request_meta(kind))
    except Exception as e:
        ui.print_info_livre(f"Hana: Falha ao iniciar geração de {kind_label}: {e}")
        return

    ui.print_executando(f"gerar_{kind}")
    ui.print_info_livre(f"Hana: Gerando {kind_label} em segundo plano. Eu te aviso quando terminar.")
    threading.Thread(
        target=_monitor_terminal_media_job,
        args=(kind, job_id),
        daemon=True,
        name=f"TerminalMedia-{kind}-{job_id}",
    ).start()

# === Controlador VTube Studio ===
vts_controller = None
_ultimo_vts_cfg = None
if CONFIG.get("VTUBESTUDIO_ATIVO", False):
    vts_cfg = CONFIG.get("VTUBE_STUDIO", {})
    if isinstance(vts_cfg, dict):
        _ultimo_vts_cfg = {
            "host": vts_cfg.get("host", "localhost"),
            "port": vts_cfg.get("port", 8001),
            "emotion_map": dict(vts_cfg.get("emotion_map", {})),
        }
        vts_controller = VTSController(
            host=_ultimo_vts_cfg["host"],
            port=_ultimo_vts_cfg["port"],
            emotion_map=_ultimo_vts_cfg["emotion_map"],
            signals=signals
        )
        vts_controller.start()

# Banner
_ultimo_provedor = CONFIG.get("LLM_PROVIDER", "groq")


def _snapshot_tts_state():
    provider = str(CONFIG.get("TTS_PROVIDER", "google")).lower()
    settings = CONFIG.get("TTS_SETTINGS", {})
    if not isinstance(settings, dict):
        settings = {}
    provider_block = settings.get(provider, {})
    if not isinstance(provider_block, dict):
        provider_block = {}
    return provider, json.dumps(provider_block, ensure_ascii=False, sort_keys=True)


_ultimo_tts_provider, _ultimo_tts_state = _snapshot_tts_state()
_llm_model = CONFIG.get("LLM_PROVIDERS", {}).get(_ultimo_provedor, {}).get("modelo", "desconhecido")
ui.set_banner(
    stt_info="GROQ WHISPER",
    tts_info=f"{tts.provedor.upper()} TTS",
    provider_info=llm_selector.provedor_atual.upper(),
    model_info=_llm_model
)


def _handle_runtime_global_stop(*_args, **_kwargs):
    try:
        tts.parar()
    except Exception:
        logging.debug("[MAIN] Falha ao parar TTS do runtime.", exc_info=True)


register_stop_callback("runtime_terminal_tts", _handle_runtime_global_stop)

_stop_hotkey_handle = None
_stop_hotkey_signature = None
_stop_watchdog_stop_event = threading.Event()
_last_stop_keypress_at = 0.0


def _sync_runtime_stop_hotkey_binding():
    global _stop_hotkey_handle, _stop_hotkey_signature

    settings = get_stop_hotkey_settings()
    signature = (bool(settings["enabled"]), str(settings["key"]).upper())
    if signature == _stop_hotkey_signature:
        return

    if keyboard is not None and _stop_hotkey_handle is not None:
        try:
            keyboard.remove_hotkey(_stop_hotkey_handle)
        except Exception:
            logging.debug("[MAIN] Nao foi possivel remover hotkey de stop anterior.", exc_info=True)

    _stop_hotkey_handle = None
    _stop_hotkey_signature = signature

    if not settings["enabled"] or keyboard is None:
        return

    try:
        _stop_hotkey_handle = keyboard.add_hotkey(
            settings["key"],
            lambda: request_global_stop("runtime_hotkey"),
            suppress=False,
            trigger_on_release=False,
        )
        logging.info("[MAIN] Hotkey global de stop registrada: %s", settings["key"])
    except Exception as exc:
        logging.warning("[MAIN] Falha ao registrar hotkey global de stop %s: %s", settings["key"], exc)


def _runtime_stop_watchdog_loop():
    global _last_stop_keypress_at

    last_pressed = False
    while not _stop_watchdog_stop_event.is_set():
        try:
            poll_external_stop()
        except Exception:
            logging.debug("[MAIN] Falha ao verificar sinal externo de stop.", exc_info=True)

        try:
            settings = get_stop_hotkey_settings()
            key = str(settings.get("key") or "F8")
            enabled = bool(settings.get("enabled", True))
            pressed = bool(enabled and keyboard is not None and keyboard.is_pressed(key))
            now = time.monotonic()
            if pressed and not last_pressed and now - _last_stop_keypress_at >= 0.6:
                _last_stop_keypress_at = now
                request_global_stop("runtime_hotkey_poll")
            last_pressed = pressed
        except Exception:
            last_pressed = False

        _stop_watchdog_stop_event.wait(0.1)


_sync_runtime_stop_hotkey_binding()
threading.Thread(
    target=_runtime_stop_watchdog_loop,
    daemon=True,
    name="HanaRuntimeStopWatchdog",
).start()

while True:
    try:
        # Hot-reload
        if CONFIG.reload():
            novo_prov = CONFIG.get("LLM_PROVIDER", "groq")
            if novo_prov != _ultimo_provedor:
                llm_selector = ProviderSelector()
                _ultimo_provedor = novo_prov
                logging.info(f"[MAIN] Provedor LLM trocado para: {novo_prov}")

            novo_tts, novo_tts_state = _snapshot_tts_state()
            if novo_tts != _ultimo_tts_provider or novo_tts_state != _ultimo_tts_state:
                tts = get_tts(novo_tts, force_reload=True)
                _ultimo_tts_provider = novo_tts
                _ultimo_tts_state = novo_tts_state
                logging.info("[MAIN] Configuração TTS recarregada: %s", novo_tts)

            _sync_runtime_stop_hotkey_binding()

            # Hot-reload VTube Studio
            if CONFIG.get("VTUBESTUDIO_ATIVO", False) and vts_controller is None:
                vts_cfg = CONFIG.get("VTUBE_STUDIO", {})
                if isinstance(vts_cfg, dict):
                    _ultimo_vts_cfg = {
                        "host": vts_cfg.get("host", "localhost"),
                        "port": vts_cfg.get("port", 8001),
                        "emotion_map": dict(vts_cfg.get("emotion_map", {})),
                    }
                    vts_controller = VTSController(
                        host=_ultimo_vts_cfg["host"],
                        port=_ultimo_vts_cfg["port"],
                        emotion_map=_ultimo_vts_cfg["emotion_map"],
                        signals=signals
                    )
                    vts_controller.start()
            elif CONFIG.get("VTUBESTUDIO_ATIVO", False) and vts_controller is not None:
                vts_cfg = CONFIG.get("VTUBE_STUDIO", {})
                desired_cfg = None
                if isinstance(vts_cfg, dict):
                    desired_cfg = {
                        "host": vts_cfg.get("host", "localhost"),
                        "port": vts_cfg.get("port", 8001),
                        "emotion_map": dict(vts_cfg.get("emotion_map", {})),
                    }
                if desired_cfg and desired_cfg != _ultimo_vts_cfg:
                    vts_controller.stop()
                    vts_controller = VTSController(
                        host=desired_cfg["host"],
                        port=desired_cfg["port"],
                        emotion_map=desired_cfg["emotion_map"],
                        signals=signals
                    )
                    vts_controller.start()
                    _ultimo_vts_cfg = desired_cfg
            elif not CONFIG.get("VTUBESTUDIO_ATIVO", False) and vts_controller is not None:
                vts_controller.stop()
                vts_controller = None
                _ultimo_vts_cfg = None

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
            ui.print_info_livre("Hana: Desligando... Até logo, Nakamura-sama!")
            break

        # --- MEMÓRIA HÍBRIDA ---
        mem_context = memory_manager.get_context(user_message)
        terminal_state = memory_manager.get_terminal_context_state(history_limit=30, stale_after_minutes=45)
        raw_history = terminal_state["history"]

        current_datetime = datetime.datetime.now().strftime("%A, %d de %B de %Y, %H:%M")
        terminal_task_type = _classify_terminal_task(user_message)
        
        vts_anatomy = ""
        if vts_controller and vts_controller.authenticated:
            vts_anatomy = "\n[ANATOMIA DO SEU CORPO DIGITAL (VTube Studio)]:\n"
            vts_anatomy += vts_controller.get_anatomy_detailed()
            vts_anatomy += "\nUse [PARAM:Nome=Valor] para poses. Use os limites informados."

        sistema_prompt = build_terminal_system_prompt(
            memory_context=mem_context,
            current_datetime=current_datetime,
            vts_anatomy=vts_anatomy,
            conversation_timing=terminal_state["timing_text"],
        )

        llm = llm_selector.get_provider()
        if not llm:
            ui.print_info_livre("Erro: o provedor LLM não conseguiu ser inicializado.")
            continue

        # --- VISÃO SOB DEMANDA ---
        image_b64 = None
        if CONFIG.get("VISAO_ATIVA", False):
            try:
                res_vision = visao.capturar()
                if res_vision.get("sucesso"):
                    image_b64 = res_vision["b64"]
            except Exception as e:
                logging.error(f"[VISAO] Erro ao capturar tela: {e}")

        # ==============================================================
        # STREAMING DIRETO: uma única chamada à LLM.
        # O stream aparece no terminal em tempo real.
        # A voz sai inteira no final, sem cortes.
        # ==============================================================
        ui.print_pensando(llm.provedor.upper())

        full_raw_response = []
        full_tts_text = []  # Acumula tudo para falar uma vez só.
        divider = SentenceDivider(faster_first_response=True)
        displayed_hana_prefix = False

        token_stream = llm.gerar_resposta_stream(
            chat_history=raw_history,
            sistema_prompt=sistema_prompt,
            user_message=user_message,
            image_b64=image_b64,
            request_context=build_request_context(channel="terminal_voice", task_type=terminal_task_type),
        )

        for chunk in divider.process_stream(token_stream):
            if chunk.is_thought:
                # Pensamento interno: não fala, só serve para parser/GUI.
                emotion_engine.processar_pensamento(chunk.thought)
                full_raw_response.append(chunk.raw)
            else:
                # Processar emoções e parâmetros do VTS em tempo real.
                for emo in chunk.emotions:
                    emotion_engine.processar_emocao(emo)
                
                if vts_controller and chunk.params:
                    for p_str in chunk.params:
                        if "=" in p_str:
                            p_name, p_val = p_str.split("=", 1)
                            try:
                                vts_controller.set_parameter(p_name.strip(), float(p_val.strip()))
                            except: pass

                # Imprimir no terminal em tempo real.
                if chunk.text.strip():
                    ui.print_hana_text(chunk.text, first_chunk=not displayed_hana_prefix)
                    displayed_hana_prefix = True
                full_raw_response.append(chunk.raw)

                # Acumular texto limpo para TTS
                texto_tts = limpar_texto_tts(chunk.text)
                if texto_tts.strip():
                    full_tts_text.append(texto_tts.strip())

        # FALA ÚNICA: junta tudo e fala uma vez só.
        texto_final_tts = " ".join(full_tts_text)
        if texto_final_tts.strip() and CONFIG.get("TTS_ATIVO", True):
            ui.print_falando(tts.provedor)
            signals.HANA_SPEAKING = True
            tts.falar(texto_final_tts)
            signals.HANA_SPEAKING = False

        ai_response_falada = divider.complete_response or "".join(full_raw_response)
        actions = extract_xml_actions(
            ai_response_falada,
            (
                "salvar_memoria",
                "gerar_imagem",
                "editar_imagem",
                "gerar_musica",
                "acao_pc",
                "analisar_youtube",
                "ferramenta_web",
            ),
        )

        # ==============================================================
        # PÓS-PROCESSAMENTO: parser XML de ações silenciosas.
        # Processa tags embutidas na resposta da Hana.
        # ==============================================================

        # 1. <salvar_memoria>conteúdo</salvar_memoria>
        for conteudo in actions.get("salvar_memoria", []):
            if conteudo:
                try:
                    memory_manager.rag.add_memory(conteudo, metadata={"role": "hana", "source": "xml_tag"})
                    memory_manager.graph.add_fact("hana_nota", "deve_lembrar", conteudo[:200])
                    logging.info(f"[XML] Memoria salva: {conteudo[:80]}...")
                except Exception as e:
                    logging.error(f"[XML] Erro ao salvar memoria: {e}")

        # 2. <gerar_imagem>prompt</gerar_imagem>
        for prompt_img in actions.get("gerar_imagem", []):
            if prompt_img:
                logging.info(f"[XML] Gerando imagem: {prompt_img[:80]}...")
                image_gen.generate_and_show(prompt_img)

        # 3. <editar_imagem>prompt de edição</editar_imagem>
        for prompt_edit in actions.get("editar_imagem", []):
            if prompt_edit:
                logging.info(f"[XML] Editando imagem: {prompt_edit[:80]}...")
                image_gen.edit_and_show(prompt_edit)

        # 4. <gerar_musica>prompt</gerar_musica>
        for prompt_music in actions.get("gerar_musica", []):
            if prompt_music:
                logging.info(f"[XML] Gerando musica: {prompt_music[:80]}...")
                _start_terminal_media_job("music", prompt_music)

        # 5. <analisar_youtube>url</analisar_youtube>
        for url in actions.get("analisar_youtube", []):
            if url:
                ui.print_executando("analisar_youtube")
                resultado_sis, resumo_tts = tool_manager.executar_tool("analisar_youtube", {"url": url})
                if resumo_tts:
                    ui.print_falando(tts.provedor)
                    tts.falar(limpar_texto_tts(resumo_tts))
                if resultado_sis:
                    # Injeta a legenda gigante no banco / contexto
                    memory_manager.add_interaction("System", resultado_sis)

        # 6. <ferramenta_web>query</ferramenta_web>
        for query in actions.get("ferramenta_web", []):
            if query:
                ui.print_executando("pesquisa_web")
                resultado_sis, resumo_tts = tool_manager.executar_tool("pesquisa_web", {"query": query})
                if resumo_tts:
                    ui.print_falando(tts.provedor)
                    tts.falar(limpar_texto_tts(resumo_tts))
                if resultado_sis:
                    memory_manager.add_interaction("System", resultado_sis)

        # 7. <acao_pc>{...json...}</acao_pc>
        for payload in actions.get("acao_pc", []):
            if payload:
                ui.print_executando("acao_pc")
                resultado = execute_pc_action(payload)
                logging.info("[XML] acao_pc => %s", resultado.get("summary") or resultado.get("message"))
                texto_resultado = resultado.get("message")
                if resultado.get("content"):
                    texto_resultado = f"{texto_resultado}\n{str(resultado['content'])[:2000]}"
                if resultado.get("stdout"):
                    texto_resultado = f"{texto_resultado}\n[stdout]\n{str(resultado['stdout'])[:1000]}"
                if texto_resultado:
                    ui.print_info_livre(texto_resultado)

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

_stop_watchdog_stop_event.set()

if keyboard is not None and _stop_hotkey_handle is not None:
    try:
        keyboard.remove_hotkey(_stop_hotkey_handle)
    except Exception:
        logging.debug("[MAIN] Falha ao remover hotkey global de stop no encerramento.", exc_info=True)
