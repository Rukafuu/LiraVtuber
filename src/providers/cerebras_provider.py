"""
Provider LLM: Cerebras
"""

import os

from dotenv import load_dotenv

from src.brain.base_llm import BaseLLM
from src.config.config_loader import CONFIG


class CerebrasProvider(BaseLLM):
    def __init__(self):
        self.provedor = "cerebras"
        prov_cfg = CONFIG.get("LLM_PROVIDERS", {}).get(self.provedor, {})
        self.modelo_chat = prov_cfg.get("modelo", "llama3.1-70b")
        super().__init__()

    def _criar_cliente(self):
        try:
            from cerebras.cloud.sdk import Cerebras
        except ImportError:
            print("[ERRO LLM CEREBRAS] SDK não instalado. Rode: pip install cerebras_cloud_sdk")
            return None

        try:
            load_dotenv()
            api_key = os.getenv("CEREBRAS_API_KEY")
            if api_key:
                return Cerebras(api_key=api_key)
            print("[ERRO LLM CEREBRAS] CEREBRAS_API_KEY ausente no .env")
            return None
        except Exception as e:
            print(f"[ERRO LLM CEREBRAS] {e}")
            return None

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
        kwargs = {
            "model": modelo,
            "messages": mensagens,
            "temperature": self.temperatura,
        }
        max_output_tokens = (request_context or {}).get("max_output_tokens")
        if max_output_tokens:
            kwargs["max_tokens"] = max_output_tokens
        if ferramentas:
            kwargs["tools"] = ferramentas

        self.last_request_meta = {
            "provider": self.provedor,
            "model": modelo,
            "backend": "cerebras_api",
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
        kwargs = {
            "model": modelo,
            "messages": mensagens,
            "temperature": self.temperatura,
            "stream": True,
        }
        max_output_tokens = (request_context or {}).get("max_output_tokens")
        if max_output_tokens:
            kwargs["max_tokens"] = max_output_tokens
        self.last_request_meta = {
            "provider": self.provedor,
            "model": modelo,
            "backend": "cerebras_api",
            "routed": False,
        }
        stream = self.cliente.chat.completions.create(**kwargs)
        for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                yield delta.content
