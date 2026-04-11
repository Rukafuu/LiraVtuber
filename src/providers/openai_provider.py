"""
Provider LLM: OpenAI
"""

from __future__ import annotations

import os

from openai import OpenAI

from src.brain.base_llm import BaseLLM
from src.config.config_loader import CONFIG


class OpenAIProvider(BaseLLM):
    def __init__(self):
        self.provedor = "openai"
        prov_cfg = CONFIG.get("LLM_PROVIDERS", {}).get(self.provedor, {})
        self.modelo_chat = prov_cfg.get("modelo", prov_cfg.get("modelo_chat", "gpt-4.1-mini"))
        self.modelo_vision = prov_cfg.get("modelo_vision", "gpt-4o")
        super().__init__()

    def _criar_cliente(self):
        api_key = os.getenv("OPENAI_API_KEY") or CONFIG.get("OPENAI_API_KEY")
        if not api_key:
            return None
        return OpenAI(api_key=api_key)

    def _prepare_messages(self, modelo, mensagens, image_b64: str = None):
        modelo_exec = modelo
        payload_messages = list(mensagens)
        if image_b64:
            modelo_exec = self.modelo_vision or modelo
            ultima_msg = payload_messages[-1]
            payload_messages[-1] = {
                "role": "user",
                "content": [
                    {"type": "text", "text": ultima_msg["content"]},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                ],
            }
        return modelo_exec, payload_messages

    @staticmethod
    def _is_reasoning_model(modelo_exec: str) -> bool:
        model_key = str(modelo_exec or "").lower()
        return model_key.startswith("o3") or model_key.startswith("o4")

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
        }
        max_tokens = (request_context or {}).get("max_output_tokens", 8192)
        if self._is_reasoning_model(modelo_exec):
            kwargs["max_completion_tokens"] = max_tokens
        else:
            kwargs["temperature"] = self.temperatura
            kwargs["max_tokens"] = max_tokens
        if ferramentas:
            kwargs["tools"] = ferramentas
            kwargs["tool_choice"] = tool_choice

        self.last_request_meta = {
            "provider": self.provedor,
            "model": modelo_exec,
            "backend": "openai_api",
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
            "stream": True,
        }
        max_tokens = (request_context or {}).get("max_output_tokens",)
        if self._is_reasoning_model(modelo_exec):
            kwargs["max_completion_tokens"] = max_tokens
        else:
            kwargs["temperature"] = self.temperatura
            kwargs["max_tokens"] = max_tokens
        self.last_request_meta = {
            "provider": self.provedor,
            "model": modelo_exec,
            "backend": "openai_api",
            "routed": False,
        }
        stream = self.cliente.chat.completions.create(**kwargs)
        for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                yield delta.content
