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
    def __init__(self, memory_manager):
        self.memory = memory_manager
        self.visao = VisaoNyra()
        self.llm_selector = ProviderSelector()
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
        """Captura a tela, descreve via Vision API e salva na memória."""
        res = self.visao.capturar()
        if not res.get("sucesso"):
            return

        b64 = res["b64"]
        llm = self.llm_selector.get_provider()
        
        prompt_visao = (
            "Você é a Lira e está dando uma espiada rápida na tela do seu pai. "
            "Descreva de forma muito concisa (1 ou 2 frases sarcásticas) o que você vê: "
            "quais apps estão abertos, o que ele está fazendo, ou qualquer detalhe curioso. "
            "Isso será guardado na sua memória para que você possa comentar depois se fizer sentido."
        )

        try:
            # Usa o método gerar_resposta para obter a descrição concisa
            descritor = llm.gerar_resposta(
                chat_history=[],
                sistema_prompt="Você é a Lira. Seja concisa e sarcástica.",
                user_message=prompt_visao,
                image_b64=b64,
                request_context={"allow_terminal_output": False, "routed": True}
            )
            
            if descritor and len(descritor.strip()) > 10:
                logger.info(f"[AWARENESS] Lira observou: {descritor}")
                # Salva no RAG
                self.memory.rag.add_memory(
                    f"Observação visual da tela: {descritor}", 
                    metadata={"source": "awareness", "type": "vision"}
                )
        except Exception as e:
            logger.warning(f"[AWARENESS] Falha ao descrever tela: {e}")

# Singleton para facilitar acesso
_awareness_instance = None

def start_awareness(memory_manager):
    global _awareness_instance
    if _awareness_instance is None:
        _awareness_instance = LiraAwareness(memory_manager)
        _awareness_instance.start()
    return _awareness_instance
