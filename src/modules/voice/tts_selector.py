"""
Seletor de TTS com suporte a hot-swap e fallback dinâmico baseado no config.
"""

import logging
import threading
import re

from src.config.config_loader import CONFIG

logger = logging.getLogger(__name__)

_swap_lock = threading.Lock()
_play_lock = threading.Lock()
_instancia_ativa = None

class TTSWrapper:
    """Wrapper que prioriza o provider ativo e tenta os outros como fallback."""
    def __init__(self, provider_inicial: str):
        self.provedor = provider_inicial
        self._set_provider_chain(self.provedor)
        
        # Cache de instâncias
        self.instancias = {}
        self._instanciar(self.provedor)

    def _set_provider_chain(self, primario: str):
        # Agora mantemos somente o google, já que edge e azure foram deletados
        self._provider_chain = ["google"]

    def _instanciar(self, prov: str):
        if prov in self.instancias:
            return self.instancias[prov]
            
        nova_instancia = _criar_tts(prov)
        self.instancias[prov] = nova_instancia
        return nova_instancia

    def falar(self, texto: str, tocar_local=True) -> bool:
        if re.search(r'\{.*"acao".*\}', texto, re.DOTALL) or \
           re.search(r'function_call|gerar_ou_editar_imagem|<tool_code>|```', texto):
            return True

        with _play_lock:
            # Tenta a cadeia de fallback na ordem
            for prov in self._provider_chain:
                try:
                    instancia = self._instanciar(prov)
                    # Só tenta falar se a configuração for válida (ex: Azure tem chave)
                    if hasattr(instancia, 'config_valida') and not instancia.config_valida:
                        continue
                        
                    sucesso = instancia.falar(texto, tocar_local)
                    if sucesso:
                        # Se funcionou um fallback, atualiza o provedor principal momentaneamente
                        self.provedor = prov
                        return True
                    logger.warning(f"[TTS WRAPPER] {prov.upper()} falhou. Tentando próximo...")
                except Exception as e:
                    logger.error(f"[TTS WRAPPER] Erro ao usar {prov.upper()}: {e}")
            return False

def get_tts(provedor: str = None):
    global _instancia_ativa
    prov = (provedor or CONFIG.get("TTS_PROVIDER", "google")).lower()
    with _swap_lock:
        if _instancia_ativa is None:
            _instancia_ativa = TTSWrapper(prov)
        else:
            _instancia_ativa.provedor = prov
            _instancia_ativa._set_provider_chain(prov)
            _instancia_ativa._instanciar(prov)
        return _instancia_ativa

def _criar_tts(prov: str):
    if prov == "google":
        try:
            from src.modules.voice.tts_google import MotorTTSGoogle
            return MotorTTSGoogle()
        except Exception: pass
    
    return _DummyTTS()

class _DummyTTS:
    def __init__(self):
        self.config_valida = True
    def falar(self, texto, tocar_local=True):
        print(f"[TTS OFFLINE] {texto}")
        return False
