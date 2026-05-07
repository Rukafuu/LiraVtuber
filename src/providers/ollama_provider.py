"""
Provider LLM: Ollama (local)
Usa a API OpenAI-compatível do Ollama em http://localhost:11434/v1
"""

import logging

from openai import OpenAI

from src.brain.base_llm import BaseLLM
from src.config.config_loader import CONFIG

logger = logging.getLogger(__name__)


class OllamaProvider(BaseLLM):
    def __init__(self):
        self.provedor = "ollama"
        prov_cfg = CONFIG.get("LLM_PROVIDERS", {}).get(self.provedor, {})
        self.modelo_chat = prov_cfg.get("modelo_chat", prov_cfg.get("modelo", "llama3.2"))
        self.base_url = prov_cfg.get("base_url", "http://localhost:11434/v1")
        super().__init__()

    def _criar_cliente(self):
        try:
            client = OpenAI(
                base_url=self.base_url,
                api_key="ollama",  # Ollama não requer chave real
            )
            return client
        except Exception as e:
            logger.error("[OLLAMA] Falha ao criar cliente: %s", e)
            return None

    def _prepare_messages(self, modelo, mensagens, image_b64: str = None):
        modelo_exec = modelo
        payload_messages = list(mensagens)
        if image_b64:
            prov_cfg = CONFIG.get("LLM_PROVIDERS", {}).get(self.provedor, {})
            modelo_exec = prov_cfg.get("modelo_vision", modelo)
            ultima_msg = payload_messages[-1]
            payload_messages[-1] = {
                "role": "user",
                "content": [
                    {"type": "text", "text": ultima_msg["content"]},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                ],
            }
        return modelo_exec, payload_messages

    def _chamar_api(
        self,
        modelo,
        mensagens,
        ferramentas=None,
        tool_choice="auto",
        image_b64: str = None,
        arquivos_multimidia: list = None,
        request_context: dict | None = None,
    ):
        modelo_exec, payload_messages = self._prepare_messages(modelo, mensagens, image_b64=image_b64)
        kwargs = {
            "model": modelo_exec,
            "messages": payload_messages,
            "temperature": self.temperatura,
            "stream": False,
        }
        max_output_tokens = (request_context or {}).get("max_output_tokens")
        if max_output_tokens:
            kwargs["max_tokens"] = max_output_tokens
        if ferramentas:
            kwargs["tools"] = ferramentas
            kwargs["tool_choice"] = tool_choice

        self.last_request_meta = {
            "provider": self.provedor,
            "model": modelo_exec,
            "backend": "ollama_local",
            "routed": False,
        }
        return self.cliente.chat.completions.create(**kwargs)

    def _chamar_api_stream(
        self,
        modelo,
        mensagens,
        image_b64: str = None,
        arquivos_multimidia: list = None,
        request_context: dict | None = None,
    ):
        modelo_exec, payload_messages = self._prepare_messages(modelo, mensagens, image_b64=image_b64)
        kwargs = {
            "model": modelo_exec,
            "messages": payload_messages,
            "temperature": self.temperatura,
            "stream": True,
        }
        max_output_tokens = (request_context or {}).get("max_output_tokens")
        if max_output_tokens:
            kwargs["max_tokens"] = max_output_tokens

        self.last_request_meta = {
            "provider": self.provedor,
            "model": modelo_exec,
            "backend": "ollama_local",
            "routed": False,
        }
        stream = self.cliente.chat.completions.create(**kwargs)
        for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                yield delta.content
