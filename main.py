import logging
import os
import re
import sys
import threading
import time
import json
import queue
from datetime import datetime

# Importações locais
from src.config.config_loader import CONFIG
from src.core.sentence_divider import SentenceDivider
from src.core.prompt_builder import build_terminal_system_prompt
from src.core.request_profiles import build_request_context
from src.modules.voice.stt_whisper import MotorSTTWhisper
from src.modules.voice.tts_selector import get_tts
from src.modules.voice.vad import VADMonitor
from src.modules.emotion_engine import EmotionEngine
from src.modules.vision.periodic_vision import VisaoNyra
from src.modules.vision.image_gen import LiraImageGen
from src.modules.media.media_downloader import MediaDownloader
from src.memory.memory_manager import LiraMemoryManager
from src.providers.provider_selector import ProviderSelector
from src.brain.tool_manager import ToolManager
from src.modules.tools.pc_control import execute_pc_action
from src.utils.text import limpar_texto_tts
from src.utils.lira_tags import extract_xml_actions, strip_xml_tags
import src.core.signals as signals
from src.gui.terminal_ui import TerminalUI

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("LiraTerminal")

def interruption_monitor():
    """Vigia o sinal de interrupção (VAD ou Manual)."""
    while True:
        if signals.INTERRUPT_REQUESTED:
            logger.info("[MAIN] Interrupção detectada! Limpando fila de fala...")
            tts = get_tts()
            tts.parar_fala()
            while not tts_queue.empty():
                try: tts_queue.get_nowait()
                except: break
            signals.INTERRUPT_REQUESTED = False
        time.sleep(0.1)

def scheduler_monitor():
    """Monitora agendamentos pendentes e avisa quando chegar a hora."""
    agenda_path = os.path.abspath("data/scheduler.jsonl")
    while True:
        if os.path.exists(agenda_path):
            try:
                with open(agenda_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                
                remaining = []
                now = time.time()
                triggered = []
                
                for line in lines:
                    if not line.strip(): continue
                    data = json.loads(line)
                    if data.get("status") == "pending" and now >= data["target_timestamp"]:
                        triggered.append(data)
                        data["status"] = "triggered"
                    remaining.append(data)
                
                if triggered:
                    with open(agenda_path, "w", encoding="utf-8") as f:
                        for r in remaining: f.write(json.dumps(r) + "\n")
                    
                    for item in triggered:
                        logger.info(f"[SCHEDULER] Disparando aviso: {item['message']}")
                        msg_aviso = f"Lira (Lembrete): {item['message']}"
                        ui.print_info_livre(f"🔔 {msg_aviso}")
                        if CONFIG.get("TTS_ATIVO", True):
                            ui.print_falando(get_tts().provedor)
                            get_tts().falar(limpar_texto_tts(f"Ei! Você pediu pra eu te avisar sobre: {item['message']}"))
            except Exception as e:
                logger.error(f"[SCHEDULER] Erro no monitor: {e}")
        time.sleep(5)

# Inicialização global
tts_queue = queue.Queue()
ui = TerminalUI()
tts = get_tts()
stt_motor = MotorSTTWhisper()
llm_selector = ProviderSelector()
memory_manager = LiraMemoryManager("data/lira_memory.db")
tool_manager = ToolManager(memory_manager)
emotion_engine = EmotionEngine()
visao = VisaoNyra()
image_gen = LiraImageGen()
downloader = MediaDownloader()

threading.Thread(target=interruption_monitor, daemon=True, name="LiraInterruptionMonitor").start()
threading.Thread(target=scheduler_monitor, daemon=True, name="LiraSchedulerMonitor").start()

def main_loop():
    ui.print_welcome("LIRA AM AMARINTH - TERMINAL INTERFACE v2.0")
    
    # Tenta carregar o controlador do VTube Studio
    vts_controller = None
    try:
        from src.modules.vts_bridge import VTubeStudioController
        vts_controller = VTubeStudioController()
        if vts_controller.connect(): logger.info("[VTS] Conectado com sucesso.")
    except Exception as e:
        logger.warning(f"[VTS] Não foi possível conectar ao VTS: {e}")

    # Monitor de VAD para interrupção por voz
    vad = VADMonitor(on_speech_detected=lambda: setattr(signals, 'INTERRUPT_REQUESTED', True))
    if CONFIG.get("VAD_ATIVO", True):
        threading.Thread(target=vad.start, daemon=True, name="LiraVAD").start()

    # Thread para processar a fila de fala sem travar o loop de chat
    def speech_worker():
        while True:
            text = tts_queue.get()
            if text:
                signals.LIRA_SPEAKING = True
                tts.falar(text)
                signals.LIRA_SPEAKING = False
            tts_queue.task_done()

    threading.Thread(target=speech_worker, daemon=True, name="LiraSpeechWorker").start()

    while True:
        try:
            # 1. Entrada de voz (STT)
            ui.print_ouvindo()
            user_message = stt_motor.ouvir()
            
            if not user_message or user_message.strip() == "":
                continue
                
            ui.print_usuario(user_message)
            
            # 2. Contexto e Prompt
            raw_history = memory_manager.get_chat_history(limit=10)
            sistema_prompt = build_terminal_system_prompt(
                memory_context=memory_manager.get_context(user_message),
                current_datetime=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )

            # --- VISÃO SOB DEMANDA ---
            image_b64 = None
            if CONFIG.get("VISAO_ATIVA", False):
                res_vision = visao.capturar()
                if res_vision.get("sucesso"): image_b64 = res_vision["b64"]

            # ==============================================================
            # AGÊNCIA AUTÔNOMA: Loop de Pensamento e Ação (ReAct)
            # ==============================================================
            steps = 0
            max_steps = 3
            current_lira_input = user_message
            final_ai_response = ""
            llm = llm_selector.get_provider()
            terminal_task_type = "chat_normal"
            
            while steps < max_steps:
                steps += 1
                if steps > 1:
                    ui.print_pensando(f"{llm.provedor.upper()} (PASSO {steps})")
                else:
                    ui.print_pensando(llm.provedor.upper())

                full_raw_response = []
                divider = SentenceDivider(faster_first_response=(steps == 1))
                displayed_lira_prefix = False

                # Coletamos arquivos de mídia se houver (ex: frames de vídeo)
                arquivos_loop = []
                if steps > 1:
                    # Tenta encontrar tags de imagem nos resultados das ferramentas
                    image_tags = re.findall(r"\[IMAGE_DATA:(.*?)\]", current_lira_input)
                    for img_path in image_tags:
                        if os.path.exists(img_path):
                            arquivos_loop.append(img_path)

                token_stream = llm.gerar_resposta_stream(
                    chat_history=raw_history,
                    sistema_prompt=sistema_prompt,
                    user_message=current_lira_input,
                    image_b64=image_b64 if steps == 1 else None,
                    arquivos_multimidia=arquivos_loop if arquivos_loop else None,
                    request_context=build_request_context(channel="terminal_voice", task_type=terminal_task_type),
                )

                for chunk in divider.process_stream(token_stream):
                    if chunk.is_thought:
                        emotion_engine.processar_pensamento(chunk.thought)
                        full_raw_response.append(chunk.raw)
                    else:
                        for emo in chunk.emotions: emotion_engine.processar_emocao(emo)
                        
                        if chunk.text.strip():
                            ui.print_lira_text(chunk.text, first_chunk=(not displayed_lira_prefix and steps == 1))
                            displayed_lira_prefix = True
                        full_raw_response.append(chunk.raw)

                        texto_chunk_tts = limpar_texto_tts(chunk.text)
                        if texto_chunk_tts.strip() and CONFIG.get("TTS_ATIVO", True):
                            tts_queue.put(texto_chunk_tts.strip())

                ai_response_step = divider.complete_response or "".join(full_raw_response)
                final_ai_response += ai_response_step + "\n"
                
                actions = extract_xml_actions(
                    ai_response_step,
                    ("salvar_memoria", "gerar_imagem", "editar_imagem", "gerar_musica", "acao_pc", "analisar_youtube", "ferramenta_web", "agendar_aviso", "analisar_video"),
                )

                active_tool_results = []

                # 1. Passivas
                for conteudo in actions.get("salvar_memoria", []):
                    if conteudo: memory_manager.rag.add_memory(conteudo)
                for p in actions.get("gerar_imagem", []):
                    if p: image_gen.generate_and_show(p)
                for p in actions.get("agendar_aviso", []):
                    if p:
                        res_sis, res_tts = tool_manager.executar_tool("agendar_aviso", p)
                        ui.print_info_livre(f"📅 {res_tts}")
                        if res_tts: tts_queue.put(limpar_texto_tts(res_tts))

                # 2. Ativas
                for url in actions.get("analisar_youtube", []):
                    if url:
                        ui.print_executando("analisar_youtube")
                        res_sis, res_tts = tool_manager.executar_tool("analisar_youtube", {"url": url})
                        active_tool_results.append(f"[RESULTADO YOUTUBE]: {res_sis}")
                        if res_tts: tts_queue.put(limpar_texto_tts(res_tts))

                for query in actions.get("ferramenta_web", []):
                    if query:
                        ui.print_executando("pesquisa_web")
                        res_sis, res_tts = tool_manager.executar_tool("pesquisa_web", {"query": query})
                        active_tool_results.append(f"[RESULTADO WEB]: {res_sis}")
                        if res_tts: tts_queue.put(limpar_texto_tts(res_tts))

                for url in actions.get("analisar_video", []):
                    if url:
                        ui.print_executando("analisar_video")
                        res_sis, res_tts = tool_manager.executar_tool("analisar_video", {"url": url})
                        active_tool_results.append(f"[RESULTADO VÍDEO]: {res_sis}")
                        if res_tts: tts_queue.put(limpar_texto_tts(res_tts))

                for payload in actions.get("acao_pc", []):
                    if payload:
                        ui.print_executando("acao_pc")
                        res = execute_pc_action(payload)
                        content = res.get("content") or res.get("stdout")
                        if content: active_tool_results.append(f"[PC]: {res.get('message')}\n{str(content)[:2000]}")
                        else: ui.print_info_livre(res.get("message", "Ação concluída."))

                if not active_tool_results: break
                
                raw_history.append({"role": "user", "content": current_lira_input})
                raw_history.append({"role": "assistant", "content": ai_response_step})
                current_lira_input = "[SISTEMA]: Resultados:\n" + "\n".join(active_tool_results)
                current_lira_input += "\n\nFinalize sua resposta."

            memory_manager.add_interaction("Amarinth", user_message)
            memory_manager.add_interaction("Lira", final_ai_response.strip())

        except Exception as e:
            logger.exception("[MAIN] Erro")
            ui.print_info_livre(f"Erro: {e}")

if __name__ == "__main__":
    main_loop()
