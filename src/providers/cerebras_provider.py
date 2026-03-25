"""
Provider LLM: Cerebras

Wrapper fino herdando de BaseLLM. Todo o pipeline vem da base.
Cerebras não tem modelo de visão — usa o fallback Groq da BaseLLM automaticamente.
"""

import os 
from src.config.config_loader import CONFIG
from src.brain.base_llm import BaseLLM
from dotenv import load_dotenv


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
            else:
                print("[ERRO LLM CEREBRAS] CEREBRAS_API_KEY ausente no .env")
                return None
        except Exception as e:
            print(f"[ERRO LLM CEREBRAS] {e}")
            return None

    def _chamar_api(self, modelo, mensagens, ferramentas=None, tool_choice="auto", image_b64: str = None):
        kwargs = {
            "model": modelo,
            "messages": mensagens,
            "temperature": self.temperatura,
        }
        if ferramentas:
            kwargs["tools"] = ferramentas
            # Cerebras pode não suportar tool_choice em todos os modelos
        return self.cliente.chat.completions.create(**kwargs)
