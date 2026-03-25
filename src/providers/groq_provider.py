"""
Provider LLM: Groq
"""

import os
from groq import Groq
from src.brain.base_llm import BaseLLM
from src.config.config_loader import CONFIG

class GroqProvider(BaseLLM):
    def __init__(self):
        self.provedor = "groq"
        prov_cfg = CONFIG.get("LLM_PROVIDERS", {}).get(self.provedor, {})
        self.modelo_chat = prov_cfg.get("modelo", "llama-3.3-70b-versatile")
        super().__init__()

    def _criar_cliente(self):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            return None
        return Groq(api_key=api_key)

    def _chamar_api(self, modelo, mensagens, ferramentas=None, tool_choice="auto", image_b64: str = None):
        # Se houver imagem, tentamos usar o modelo de visão do config
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
            "stream": False,
        }
        if ferramentas:
            kwargs["tools"] = ferramentas
            kwargs["tool_choice"] = tool_choice
            
        return self.cliente.chat.completions.create(**kwargs)
