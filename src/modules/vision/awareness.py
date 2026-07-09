"""
Lira Awareness — O "olhar" autônomo da Lira.
Captura a tela em intervalos e descreve o ambiente para a memória de longo prazo.
"""

import time
import threading
import logging
from src.config.config_loader import CONFIG
from src.modules.vision.periodic_vision import VisaoNyra
from src.providers.provider_selector import ProviderSelector

logger = logging.getLogger(__name__)

class LiraAwareness:
    def __init__(self, memory_manager=None):
        # O memory_manager é aceito para compatibilidade de assinatura, mas o RAG é consumido via API
        self.memory = memory_manager
        self.visao = VisaoNyra()
        self._running = False
        self._thread = None
        self.interval = CONFIG.get("AWARENESS_INTERVAL", 300) # 5 minutos padrão

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="LiraAwareness")
        self._thread.start()
        logger.info("[AWARENESS] Sistema de consciência de tela iniciado.")

    def stop(self):
        self._running = False

    def _loop(self):
        while self._running:
            # Espera o intervalo
            time.sleep(self.interval)
            
            if not CONFIG.get("VISAO_ATIVA", False):
                continue
                
            try:
                self._observar_tela()
            except Exception as e:
                logger.error(f"[AWARENESS] Erro ao observar tela: {e}")

    def _observar_tela(self):
        """Captura a tela, descreve via Vision API e salva na memória centralizada."""
        res = self.visao.capturar()
        if not res.get("sucesso"):
            return

        b64 = res["b64"]
        prompt_visao = (
            "Você é a Lira e está dando uma espiada rápida na tela do seu pai. "
            "Descreva de forma muito concisa o que você vê (quais apps estão abertos, o que ele está fazendo). "
            "Isso será guardado na sua memória. "
            "REGRA ESPECIAL DE INTERRUPÇÃO: Se você perceber que ele está procrastinando muito (ex: muito tempo no YouTube, Twitter, etc) "
            "ou fazendo algo muito inusitado, você pode INTERROMPÊ-LO ativamente dando uma bronca sarcástica. "
            "Para fazer isso, inclua no final da sua resposta a tag: <INTERROMPER>Sua fala ácida aqui</INTERROMPER>."
        )

        try:
            import httpx
            payload = {
                "message": prompt_visao,
                "channel": "awareness",
                "image_b64": b64,
                "history": []
            }
            
            descritor = ""
            with httpx.stream("POST", "http://127.0.0.1:8042/api/brain/chat", json=payload, timeout=60.0) as r:
                if r.status_code == 200:
                    for line in r.iter_lines():
                        if not line:
                            continue
                        event = json.loads(line)
                        if event["type"] == "chunk":
                            descritor += event["content"]

            if descritor and len(descritor.strip()) > 10:
                logger.info(f"[AWARENESS] Lira observou: {descritor}")
                
                # Envia a observação de tela para o RAG centralizado na API
                try:
                    httpx.post(
                        "http://127.0.0.1:8042/api/memory/rag",
                        json={
                            "text": f"Observação visual da tela: {descritor}",
                            "metadata": {"source": "awareness", "type": "vision"}
                        },
                        timeout=5.0
                    )
                except Exception as mem_err:
                    logger.error(f"[AWARENESS] Falha ao enviar memória para a API central: {mem_err}")
                
                # Checa se ela decidiu interromper
                import re
                match = re.search(r'<INTERROMPER>(.*?)</INTERROMPER>', descritor, flags=re.IGNORECASE | re.DOTALL)
                if match:
                    fala_interrupcao = match.group(1).strip()
                    logger.info(f"[AWARENESS] Disparando interrupção proativa: {fala_interrupcao}")
                    
                    # Fala a interrupção usando o TTS global
                    try:
                        from src.modules.voice.tts_selector import get_tts
                        tts = get_tts()
                        if CONFIG.get("TTS_ATIVO", True):
                            tts.falar(fala_interrupcao)
                    except Exception as tts_err:
                        logger.error(f"[AWARENESS] Erro ao falar interrupção: {tts_err}")
        except Exception as e:
            logger.warning(f"[AWARENESS] Falha ao descrever tela via API central: {e}")

# Singleton para facilitar acesso
_awareness_instance = None

def start_awareness(memory_manager=None):
    global _awareness_instance
    if _awareness_instance is None:
        _awareness_instance = LiraAwareness(memory_manager)
        _awareness_instance.start()
    return _awareness_instance
