"""Lira VTuber terminal runtime (voz, STT, TTS, VTS, XML tools)."""
from pathlib import Path
import datetime
import json
import logging
import os
import re
import sys
import threading
import time
import warnings

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# === SILENCIAR AVISOS E LOGS BARULHENTOS (antes de qualquer import) ===
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"

from dotenv import load_dotenv

load_dotenv(ROOT / ".env", encoding="utf-8-sig")

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

from lira_core.tools import XmlActionHandlers, default_terminal_action_tags, process_xml_actions
from lira_core.tools.tool_manager import ToolManager
from src.memory.memory_manager import LiraMemoryManager
from src.modules.voice.stt_whisper import MotorSTTWhisper
from src.modules.voice.tts_selector import get_tts
from src.modules.voice.audio_control import poll_external_stop, register_stop_callback, request_global_stop
from src.modules.vision.periodic_vision import VisaoNyra
from src.modules.vision.awareness import start_awareness
from src.modules.vision.image_gen import LiraImageGen
from src.modules.media import LiraMusicGen, get_media_settings
from src.modules.emotion_engine import EmotionEngine
from src.modules.tools.pc_control import execute_pc_action
from src.modules.vts_controller import VTSController
from src.core.prompt_builder import build_terminal_system_prompt
from src.providers.provider_selector import ProviderSelector
from src.core.request_profiles import build_request_context
from src.utils.lira_tags import extract_xml_actions
from src.utils.text import limpar_texto_tts, ui
from lira_core.utils import terminal_ui as _lira_terminal_ui

_lira_terminal_ui.bind_terminal_ui(ui)
from src.utils.sentence_divider import SentenceDivider
from src.config.config_loader import CONFIG
from src.core.runtime_capabilities import get_stop_hotkey_settings

try:
    import keyboard
except Exception:
    keyboard = None


# === Sinais de Estado (Neuro style) ===
class LiraSignals:
    def __init__(self):
        self.LIRA_SPEAKING = False
        self.STT_ACTIVE = True

signals = LiraSignals()

tts = get_tts()

# --- MOTOR DE FALA EM FILA (AUDIO STREAMING / CHUNKING) ---
import queue
tts_queue = queue.Queue()

def speaker_worker():
    """Thread dedicada para processar falas em sequência sem travar o stream do terminal."""
    while True:
        try:
            chunk_text = tts_queue.get()
            if chunk_text is None:
                break
            
            if CONFIG.get("TTS_ATIVO", True):
                signals.LIRA_SPEAKING = True
                # O tts.falar bloqueia até terminar a frase, o que é perfeito para a fila.
                tts.falar(chunk_text)
                signals.LIRA_SPEAKING = False
            
            tts_queue.task_done()
        except Exception as e:
            logging.error(f"[SPEAKER] Erro no processamento de fala: {e}")

threading.Thread(target=speaker_worker, daemon=True, name="LiraSpeakerWorker").start()

def interruption_monitor():
    """Monitora o microfone para interrupção natural (duplex)."""
    from src.modules.voice.vad_silero import get_vad
    import pyaudio
    import time

    vad = get_vad()
    pa = pyaudio.PyAudio()
    chunk = 1024
    rate = CONFIG.get("TAXA_AMOSTRAGEM", 44100)
    
    try:
        stream = pa.open(format=pyaudio.paInt16, channels=1, rate=rate, input=True, frames_per_buffer=chunk)
        while True:
            # Só monitora se ela estiver falando E não for modo PTT (opcional)
            if signals.LIRA_SPEAKING:
                data = stream.read(chunk, exception_on_overflow=False)
                if vad.is_speech(data, threshold=0.6):
                    logging.info("[MAIN] Usuário interrompeu a Lira. Parando áudio.")
                    _handle_runtime_global_stop()
                    time.sleep(1.0) # Debounce
            else:
                time.sleep(0.1)
    except Exception as e:
        logging.debug(f"[MAIN] Monitor de interrupção falhou ou mic ocupado: {e}")

threading.Thread(target=interruption_monitor, daemon=True, name="LiraInterruptionMonitor").start()

stt_motor = MotorSTTWhisper()
start_awareness() # Inicia a consciência de tela em segundo plano
visao = VisaoNyra()

# === Motor de Emoções ===
emotion_engine = EmotionEngine()

def _trigger_vts_emotion(emotion: str):
    global vts_controller
    if vts_controller is not None:
        vts_controller.trigger_emotion(emotion)

emotion_engine.registrar_callback_emocao(_trigger_vts_emotion)

# === Gerador de Mídia ===
image_gen = LiraImageGen()
music_gen = LiraMusicGen()


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
            ui.print_info_livre(f"Lira: {kind_label.capitalize()} pronto em {output_path}")
            if get_media_settings().get("auto_open_terminal_outputs"):
                try:
                    os.startfile(output_path)
                except Exception as e:
                    logging.warning("[MEDIA] Falha ao abrir saída automaticamente: %s", e)
            return

        if state == "cancelled":
            ui.print_info_livre(f"Lira: Geração de {kind_label} cancelada.")
            return

        ui.print_info_livre(f"Lira: Falha ao gerar {kind_label}: {status.get('error') or 'erro desconhecido'}")
        return


def _handle_acao_pc_terminal(payload: str):
    resultado = execute_pc_action(payload)
    logging.info("[XML] acao_pc => %s", resultado.get("summary") or resultado.get("message"))
    texto_resultado = resultado.get("message")
    if resultado.get("content"):
        texto_resultado = f"{texto_resultado}\n{str(resultado['content'])[:2000]}"
    if resultado.get("stdout"):
        texto_resultado = f"{texto_resultado}\n[stdout]\n{str(resultado['stdout'])[:1000]}"
    if texto_resultado:
        ui.print_info_livre(texto_resultado)


def _start_terminal_media_job(kind: str, prompt: str):
    generator = music_gen
    kind_label = "música"
    try:
        job_id = generator.submit(prompt, origin="terminal_voice", request_meta=_build_media_request_meta(kind))
    except Exception as e:
        ui.print_info_livre(f"Lira: Falha ao iniciar geração de {kind_label}: {e}")
        return

    ui.print_executando(f"gerar_{kind}")
    ui.print_info_livre(f"Lira: Gerando {kind_label} em segundo plano. Eu te aviso quando terminar.")
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
_ultimo_provedor = CONFIG.get("LLM_PROVIDER", "ollama")


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
    stt_info="WHISPER LOCAL",
    tts_info=f"{tts.provedor.upper()} TTS",
    provider_info=_ultimo_provedor.upper(),
    model_info=_llm_model
)


def _handle_runtime_global_stop(*_args, **_kwargs):
    try:
        # 1. Limpar falas pendentes na fila
        while not tts_queue.empty():
            try:
                tts_queue.get_nowait()
                tts_queue.task_done()
            except:
                break
        
        # 2. Parar o que estiver tocando agora
        tts.parar()
        signals.LIRA_SPEAKING = False
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
    name="LiraRuntimeStopWatchdog",
).start()

while True:
    try:
        # Hot-reload
        if CONFIG.reload():
            novo_prov = CONFIG.get("LLM_PROVIDER", "ollama")
            if novo_prov != _ultimo_provedor:
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

        # --- SISTEMA DE WAKE WORD ---
        if CONFIG.get("WAKEWORD_ATIVA", False):
            from src.modules.voice.wakeword import WakeWordDetector
            # Mostra no banner que está esperando a palavra-chave
            ui.set_banner(stt_info="AGUARDANDO 'LIRA'", tts_info=f"{tts.provedor.upper()} TTS")
            
            detector = WakeWordDetector()
            user_message = detector.listen_continuous()
            
            # Restaura info do banner
            ui.set_banner(stt_info="WHISPER LOCAL", tts_info=f"{tts.provedor.upper()} TTS")
        else:
            user_message = stt_motor.transcrever()
    

        if not user_message or user_message.strip() == "":
            continue

        ui.print_info_livre(f"Você: {user_message}")

        if "desligar sistema" in user_message.lower():
            ui.print_info_livre("Lira: Desligando... Até logo, Amarinth-sama!")
            break

        # --- ANATOMIA E VISÃO ---
        vts_anatomy = ""
        if vts_controller and vts_controller.authenticated:
            vts_anatomy = "\n[ANATOMIA DO SEU CORPO DIGITAL (VTube Studio)]:\n"
            vts_anatomy += vts_controller.get_anatomy_detailed()
            vts_anatomy += "\nUse [PARAM:Nome=Valor] para poses. Use os limites informados."

        image_b64 = None
        if CONFIG.get("VISAO_ATIVA", False):
            try:
                res_vision = visao.capturar()
                if res_vision.get("sucesso"):
                    image_b64 = res_vision["b64"]
            except Exception as e:
                logging.error(f"[VISAO] Erro ao capturar tela: {e}")

        # ==============================================================
        # Chamada HTTP Streaming para o cérebro central (Control API)
        # ==============================================================
        ui.print_pensando(_ultimo_provedor.upper())

        import httpx
        try:
            payload = {
                "message": user_message,
                "channel": "terminal",
                "image_b64": image_b64,
                "vts_anatomy": vts_anatomy,
                "history": [],  # A API central busca e monta o histórico/timing
                "provider": _ultimo_provedor,
            }

            def stream_adapter():
                with httpx.stream("POST", "http://127.0.0.1:8042/api/brain/chat", json=payload, timeout=60.0) as r:
                    if r.status_code != 200:
                        logging.error(f"[CLIENT] Central API erro status {r.status_code}")
                        return
                    for line in r.iter_lines():
                        if not line:
                            continue
                        try:
                            event = json.loads(line)
                            if event["type"] == "chunk":
                                yield event["content"]
                            elif event["type"] == "emotions":
                                for emo in event["emotions"]:
                                    emotion_engine.processar_emocao(emo)
                            elif event["type"] == "media_actions":
                                # Executa ações de imagem/música locais
                                actions = event["actions"]
                                for img in actions.get("gerar_imagem", []):
                                    logging.info("[XML Client] Gerando imagem...")
                                    image_gen.generate_and_show(img)
                                for img_adv in actions.get("gerar_imagem_personagem", []) or actions.get("gerar_imagem_avancada", []):
                                    logging.info("[XML Client] Gerando imagem avançada...")
                                    image_gen.generate_advanced_and_show(img_adv)
                                for img_edit in actions.get("editar_imagem", []):
                                    logging.info("[XML Client] Editando imagem...")
                                    image_gen.edit_and_show(img_edit)
                                for music in actions.get("gerar_musica", []):
                                    logging.info("[XML Client] Gerando música...")
                                    _start_terminal_media_job("music", music)
                        except Exception as e:
                            logging.debug(f"[STREAM] Erro parsing chunk: {e}")

            full_raw_response = []
            divider = SentenceDivider(faster_first_response=True)
            displayed_lira_prefix = False

            for chunk in divider.process_stream(stream_adapter()):
                if chunk.is_thought:
                    emotion_engine.processar_pensamento(chunk.thought)
                    full_raw_response.append(chunk.raw)
                else:
                    for emo in chunk.emotions:
                        emotion_engine.processar_emocao(emo)

                    if vts_controller and chunk.params:
                        for p_str in chunk.params:
                            if "=" in p_str:
                                p_name, p_val = p_str.split("=", 1)
                                try:
                                    vts_controller.set_parameter(p_name.strip(), float(p_val.strip()))
                                except: pass

                    if chunk.text.strip():
                        ui.print_lira_text(chunk.text, first_chunk=not displayed_lira_prefix)
                        displayed_lira_prefix = True
                    full_raw_response.append(chunk.raw)

                    texto_chunk_tts = limpar_texto_tts(chunk.text)
                    if texto_chunk_tts.strip() and CONFIG.get("TTS_ATIVO", True):
                        if not signals.LIRA_SPEAKING and tts_queue.empty():
                            ui.print_falando(tts.provedor)
                        tts_queue.put(texto_chunk_tts.strip())
        except Exception as api_err:
            logging.error("[API CLIENT] Falha de comunicação com a API de Controle: %s", api_err)
            ui.print_info_livre(f"Desculpe, Amarinth-sama. Não consegui me conectar ao meu núcleo (API) na porta 8042.")

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
