"""
Provider LLM: Google Gemini
Conecta-se à API do Google Generative AI.
"""

import os
import logging
from dotenv import load_dotenv
import google.generativeai as genai
from src.brain.base_llm import BaseLLM
from src.utils.text import ui

logger = logging.getLogger(__name__)

class GoogleProvider(BaseLLM):
    def __init__(self):
        super().__init__()
        load_dotenv()
        self.api_key = os.getenv("GEMINI_API_KEY")
        
        # Carrega o modelo de forma dinâmica pelo config.json
        from src.config.config_loader import CONFIG
        self.modelo = CONFIG.get("LLM_SETTINGS", {}).get("google_cloud", {}).get("modelo", "gemini-2.5-pro")
        
        if not self.api_key:
            logger.error("[GOOGLE LLM] GEMINI_API_KEY não encontrada no .env!")
        else:
            genai.configure(api_key=self.api_key)
            self.client = genai.GenerativeModel(self.modelo)
            self.config_valida = True
            logger.info("[GOOGLE LLM] Provider inicializado com sucesso.")

    def gerar_resposta(self, chat_history: list, sistema_prompt: str, user_message: str, tools: list = None) -> str:
        if not self.config_valida:
            return None

        # Montar mensagens no formato do Google Generative AI
        # O Gemini tem regras estritas de histórico "user" e "model"
        google_history = []
        for msg in chat_history:
            role = "user" if msg["role"] == "Nakamura" else "model"
            google_history.append({"role": role, "parts": [msg["content"]]})

        try:
            ui.print_pensando("GEMINI-2.5")
            
            # Inicializa chat com o histórico
            chat = self.client.start_chat(history=google_history)
            
            # Formata o prompt do usuário incluindo o sistema para forçar obediência
            # (No Gemini livre, o system_instruction pode ser passado no construtor)
            self.client = genai.GenerativeModel(
                model_name=self.modelo,
                system_instruction=sistema_prompt
            )
            chat = self.client.start_chat(history=google_history)

            response = chat.send_message(user_message, stream=True)

            print(f"{ui.C_NYRA}[HANA]{ui.C_RST}: ", end="", flush=True)
            ai_response_full = ""
            for chunk in response:
                content = chunk.text
                ai_response_full += content
                print(content, end="", flush=True)
            print()

            return ai_response_full

        except Exception as e:
            logger.error(f"[GOOGLE LLM] Erro de API: {e}")
            ui.print_info_livre("Hana: (Os servidores do Google estão rindo de mim. Falha na conexão...)")
            return None
