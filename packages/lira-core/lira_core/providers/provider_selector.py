"""
Gerenciador dinâmico de provedores LLM.
Permite trocar entre provedores suportados com lazy load.
"""

import logging

from lira_core.config.config_loader import CONFIG

logger = logging.getLogger(__name__)


class ProviderSelector:
    def __init__(self):
        self.provedor_atual = CONFIG.get("LLM_PROVIDER", "ollama")
        self.instancias = {}
        logger.info("[PROVIDER SELECTOR] Provedor LLM primário: %s", self.provedor_atual)

    def get_provider(self, provider: str | None = None):
        """Retorna a instancia do provedor solicitado ou atual, com lazy load."""
        if provider is None:
            self.provedor_atual = CONFIG.get("LLM_PROVIDER", self.provedor_atual)
        prov = str(provider or self.provedor_atual or "ollama").lower()

        if prov in self.instancias:
            return self.instancias[prov].refresh_runtime_settings()

        try:
            if prov == "groq":
                from lira_core.providers.groq_provider import GroqProvider

                self.instancias[prov] = GroqProvider()
            elif prov == "google_cloud":
                from lira_core.providers.google_provider import GoogleProvider

                self.instancias[prov] = GoogleProvider()
            elif prov == "cerebras":
                from lira_core.providers.cerebras_provider import CerebrasProvider

                self.instancias[prov] = CerebrasProvider()
            elif prov == "openrouter":
                from lira_core.providers.openrouter_provider import OpenRouterProvider

                self.instancias[prov] = OpenRouterProvider()
            elif prov == "claude":
                from lira_core.providers.claude_provider import ClaudeProvider

                self.instancias[prov] = ClaudeProvider()
            elif prov == "openai":
                from lira_core.providers.openai_provider import OpenAIProvider

                self.instancias[prov] = OpenAIProvider()
            elif prov == "ollama":
                from lira_core.providers.ollama_provider import OllamaProvider

                self.instancias[prov] = OllamaProvider()
            else:
                logger.error("[PROVIDER SELECTOR] Provedor '%s' não suportado. Fallback para Ollama.", prov)
                from lira_core.providers.ollama_provider import OllamaProvider

                self.instancias["ollama"] = OllamaProvider()
                return self.instancias["ollama"]

            return self.instancias[prov].refresh_runtime_settings()

        except ImportError as e:
            logger.error("[PROVIDER SELECTOR] Erro ao carregar provedor %s: %s", prov, e)
            return None
        except Exception as e:
            logger.error("[PROVIDER SELECTOR] Erro de inicialização do provedor %s: %s", prov, e)
            return None
