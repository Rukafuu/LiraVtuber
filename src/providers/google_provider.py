"""
Provider LLM: Google Gemini
"""

import os
import google.generativeai as genai
from src.brain.base_llm import BaseLLM
from src.config.config_loader import CONFIG

class GoogleProvider(BaseLLM):
    def __init__(self):
        self.provedor = "google_cloud"
        prov_cfg = CONFIG.get("LLM_PROVIDERS", {}).get(self.provedor, {})
        self.modelo_chat = prov_cfg.get("modelo", "gemini-1.5-pro")
        super().__init__()

    def _criar_cliente(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return None
        genai.configure(api_key=api_key)
        return genai.GenerativeModel(self.modelo_chat)

    def _chamar_api(self, modelo, mensagens, ferramentas=None, tool_choice="auto", image_b64: str = None):
        # Gemini tem formato diferente de mensagens
        modelo_exec = modelo
        if image_b64:
            prov_cfg = CONFIG.get("LLM_PROVIDERS", {}).get(self.provedor, {})
            modelo_exec = prov_cfg.get("modelo_vision", modelo)
        
        google_history = []
        user_msg_content = mensagens[-1]["content"]
        
        # Converter histórico
        for msg in mensagens[:-1]:
            role = "user" if msg["role"] == "user" else "model"
            google_history.append({"role": role, "parts": [msg["content"]]})

        # Se houver imagem, o conteúdo do usuário é uma lista [texto, imagem]
        full_user_content = [user_msg_content]
        if image_b64:
            import base64
            from io import BytesIO
            from PIL import Image
            img_data = base64.b64decode(image_b64)
            img_pil = Image.open(BytesIO(img_data))
            full_user_content.append(img_pil)

        chat = self.cliente.start_chat(history=google_history)
        
        # Recriar o modelo com o ID de visão se necessário
        if image_b64 and modelo_exec != modelo:
            model_vision = genai.GenerativeModel(modelo_exec)
            response = model_vision.generate_content([user_msg_content, img_pil])
        else:
            response = chat.send_message(full_user_content)
        
        class MockResponse:
            class MockChoice:
                class MockMessage:
                    def __init__(self, content):
                        self.content = content
                        self.tool_calls = None
                def __init__(self, content):
                    self.message = self.MockMessage(content)
            def __init__(self, text):
                self.choices = [self.MockChoice(text)]
        
        return MockResponse(response.text)
