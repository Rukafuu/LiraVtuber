"""
Provider LLM: Groq
Conecta-se à API super-rápida da Groq.
"""

import os
import json
import logging
from dotenv import load_dotenv
from groq import Groq
from src.brain.base_llm import BaseLLM
from src.utils.text import ui

logger = logging.getLogger(__name__)

class GroqProvider(BaseLLM):
    def __init__(self):
        super().__init__()
        load_dotenv()
        self.api_key = os.getenv("GROQ_API_KEY")
        
        # Carrega o modelo de forma dinâmica pelo config.json
        from src.config.config_loader import CONFIG
        self.modelo = CONFIG.get("LLM_SETTINGS", {}).get("groq", {}).get("modelo", "llama-3.3-70b-versatile")
        
        if not self.api_key:
            logger.error("[GROQ] GROQ_API_KEY não encontrada no .env!")
        else:
            self.client = Groq(api_key=self.api_key)
            self.config_valida = True
            logger.info("[GROQ] Provider inicializado com sucesso.")

    def gerar_resposta(self, chat_history: list, sistema_prompt: str, user_message: str, tools: list = None) -> str:
        if not self.config_valida:
            return None

        # Montar mensagens
        messages = [
            {"role": "system", "content": sistema_prompt}
        ]
        
        for msg in chat_history:
            role = "user" if msg["role"] == "Nakamura" else "assistant"
            messages.append({"role": role, "content": msg["content"]})
            
        messages.append({"role": "user", "content": user_message})

        try:
            ui.print_pensando("GROQ-LLAMA3")
            kwargs = {
                "model": self.modelo,
                "messages": messages,
                "temperature": 1,
                "max_completion_tokens": 2048,
                "top_p": 1,
                "stream": True,
            }
            if tools:
                kwargs["tools"] = tools

            completion = self.client.chat.completions.create(**kwargs)

            print(f"{ui.C_NYRA}[HANA]{ui.C_RST}: ", end="", flush=True)
            ai_response_full = ""
            tool_calls_buffer = {}

            for chunk in completion:
                delta = chunk.choices[0].delta
                if getattr(delta, 'content', None):
                    ai_response_full += delta.content
                    print(delta.content, end="", flush=True)
                
                if getattr(delta, 'tool_calls', None):
                    for tool_call in delta.tool_calls:
                        idx = tool_call.index
                        if idx not in tool_calls_buffer:
                            tool_calls_buffer[idx] = {
                                "id": tool_call.id,
                                "type": "function",
                                "function": {"name": tool_call.function.name, "arguments": ""}
                            }
                        if tool_call.function.arguments:
                            tool_calls_buffer[idx]["function"]["arguments"] += tool_call.function.arguments

            print() # Nova linha após terminar de falar

            if tool_calls_buffer:
                tools_list = list(tool_calls_buffer.values())
                return json.dumps({"acao": "tool_call", "tools": tools_list, "texto": ai_response_full}, ensure_ascii=False)

            return ai_response_full

        except Exception as e:
            logger.error(f"[GROQ] Erro de API: {e}")
            ui.print_info_livre("Hana: (Tive um pequeno lapso de internet, me dê um segundo!)")
            return None
