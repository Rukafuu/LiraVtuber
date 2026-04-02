"""
Provider LLM: OpenRouter

Wrapper herdando de BaseLLM para conectar à API da OpenRouter.
Possibilita o acesso a múltiplos modelos (Llama 3 400b, 70b, Mistral, etc.)
com uma única chave.
"""

from openai import OpenAI
from src.config.config_loader import CONFIG
from src.brain.base_llm import BaseLLM
import logging

logger = logging.getLogger(__name__)


class OpenRouterProvider(BaseLLM):
    def __init__(self):
        self.provedor = "openrouter"
        prov_cfg = CONFIG.get("LLM_PROVIDERS", {}).get(self.provedor, {})
        self.modelo_chat = prov_cfg.get("modelo", prov_cfg.get("modelo_chat", "google/gemini-3.1-pro-preview"))
        self.modelo_vision = prov_cfg.get("modelo_vision", "google/gemini-3.1-pro-preview")
        self.modelo_fallback_vision = prov_cfg.get("modelo_vision", "google/gemini-3.1-pro-preview")
        
        super().__init__()

    def _criar_cliente(self):
        try:
            import os
            api_key = os.getenv("OPENROUTER_API_KEY")
            if not api_key:
                logger.error("[OPENROUTER] OPENROUTER_API_KEY não encontrada no .env")
                return None
            
            return OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=api_key,
                default_headers={
                    "HTTP-Referer": "https://github.com/nyra-ai",  # Obrigatório pro OpenRouter
                    "X-Title": "Nyra Assistant", # Opcional pro OpenRouter
                }
            )
        except Exception as e:
            logger.error(f"[OPENROUTER] Erro ao criar cliente: {e}")
            return None

    def _chamar_api(self, modelo, mensagens, ferramentas=None, tool_choice="auto", image_b64: str = None):
        # Se houver imagem, precisamos converter a ÚLTIMA mensagem para multi-modal
        modelo_exec = modelo
        if image_b64:
            prov_cfg = CONFIG.get("LLM_PROVIDERS", {}).get(self.provedor, {})
            modelo_exec = prov_cfg.get("modelo_vision", modelo)
            
            ultima_msg = mensagens[-1]
            mensagens[-1] = {
                "role": "user",
                "content": [
                    {"type": "text", "text": ultima_msg["content"]},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_b64}"
                        }
                    }
                ]
            }

        kwargs = {
            "model": modelo_exec,
            "messages": mensagens,
            "temperature": self.temperatura,
            "max_tokens": 8192,
        }
        if ferramentas:
            kwargs["tools"] = ferramentas
            kwargs["tool_choice"] = tool_choice
            
        return self.cliente.chat.completions.create(**kwargs)

    def _chamar_api_stream(self, modelo, mensagens, image_b64: str = None, arquivos_multimidia: list = None):
        """Stream de tokens via OpenRouter (OpenAI-compatible)."""
        modelo_exec = modelo
        if image_b64:
            prov_cfg = CONFIG.get("LLM_PROVIDERS", {}).get(self.provedor, {})
            modelo_exec = prov_cfg.get("modelo_vision", modelo)
            ultima_msg = mensagens[-1]
            mensagens[-1] = {
                "role": "user",
                "content": [
                    {"type": "text", "text": ultima_msg["content"]},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}}
                ]
            }

        stream = self.cliente.chat.completions.create(
            model=modelo_exec,
            messages=mensagens,
            temperature=self.temperatura,
            max_tokens=8192,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                yield delta.content

