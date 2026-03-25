"""
Gerenciador dinâmico de provedores LLM.
Permite trocar entre Groq e Gemini Cloud dinamicamente baseado na configuração.
"""

import logging
from src.config.config_loader import CONFIG

logger = logging.getLogger(__name__)

class ProviderSelector:
    def __init__(self):
        self.provedor_atual = CONFIG.get("LLM_PROVIDER", "groq")
        self.instancias = {}
        logger.info(f"[PROVIDER SELECTOR] Provedor LLM primário: {self.provedor_atual}")

    def get_provider(self):
        """Retorna a instância do provedor atual. Lazy load para evitar init desnecessário."""
        prov = self.provedor_atual.lower()
        
        if prov in self.instancias:
            return self.instancias[prov]
            
        try:
            if prov == "groq":
                from src.providers.groq_provider import GroqProvider
                self.instancias[prov] = GroqProvider()
            elif prov == "google_cloud":
                from src.providers.google_provider import GoogleProvider
                self.instancias[prov] = GoogleProvider()
            else:
                logger.error(f"[PROVIDER SELECTOR] Provedor '{prov}' não suportado. Fallback para Groq.")
                from src.providers.groq_provider import GroqProvider
                self.instancias["groq"] = GroqProvider()
                return self.instancias["groq"]
                
            return self.instancias[prov]
            
        except ImportError as e:
            logger.error(f"[PROVIDER SELECTOR] Erro ao carregar provedor {prov}: {e}")
            return None
        except Exception as e:
            logger.error(f"[PROVIDER SELECTOR] Erro de inicialização do provedor {prov}: {e}")
            return None
