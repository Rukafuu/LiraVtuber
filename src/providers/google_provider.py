"""
Provider LLM: Google Gemini (SDK novo — google.genai)
"""

import os
import logging
from google import genai
from google.genai import types
from src.brain.base_llm import BaseLLM
from src.config.config_loader import CONFIG

logger = logging.getLogger(__name__)

class GoogleProvider(BaseLLM):
    def __init__(self):
        self.provedor = "google_cloud"
        prov_cfg = CONFIG.get("LLM_PROVIDERS", {}).get(self.provedor, {})
        self.modelo_chat = prov_cfg.get("modelo", "gemini-2.5-flash-preview-04-17")
        super().__init__()

    def _criar_cliente(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.error("[GOOGLE] GEMINI_API_KEY não encontrada.")
            return None
        client = genai.Client(api_key=api_key)
        logger.info(f"[GOOGLE] Cliente inicializado com modelo: {self.modelo_chat}")
        return client

    def _chamar_api(self, modelo, mensagens, ferramentas=None, tool_choice="auto", image_b64: str = None):
        # Determina o modelo (visão ou padrão)
        modelo_exec = modelo
        if image_b64:
            prov_cfg = CONFIG.get("LLM_PROVIDERS", {}).get(self.provedor, {})
            modelo_exec = prov_cfg.get("modelo_vision", modelo)

        # Monta o histórico no formato do novo SDK
        contents = []
        system_instruction = None

        for msg in mensagens:
            role = msg["role"]
            content_text = msg["content"]

            if role == "system":
                system_instruction = content_text
                continue

            gemini_role = "user" if role == "user" else "model"
            contents.append(
                types.Content(
                    role=gemini_role,
                    parts=[types.Part.from_text(text=content_text)]
                )
            )

        # Se houver imagem, adiciona ao último conteúdo do user
        if image_b64 and contents:
            import base64
            img_bytes = base64.b64decode(image_b64)
            image_part = types.Part.from_bytes(data=img_bytes, mime_type="image/png")
            # Adiciona a imagem ao último content do user
            contents[-1].parts.append(image_part)

        # Configuração de geração
        gen_config = types.GenerateContentConfig(
            temperature=self.temperatura,
            system_instruction=system_instruction,
        )

        # Chamada à API
        response = self.cliente.models.generate_content(
            model=modelo_exec,
            contents=contents,
            config=gen_config,
        )

        # Adapta para o formato MockResponse esperado pelo BaseLLM
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

    def _chamar_api_stream(self, modelo, mensagens, image_b64: str = None):
        """Stream de tokens via Google GenAI SDK."""
        modelo_exec = modelo
        if image_b64:
            prov_cfg = CONFIG.get("LLM_PROVIDERS", {}).get(self.provedor, {})
            modelo_exec = prov_cfg.get("modelo_vision", modelo)

        contents = []
        system_instruction = None
        for msg in mensagens:
            role = msg["role"]
            content_text = msg["content"]
            if role == "system":
                system_instruction = content_text
                continue
            gemini_role = "user" if role == "user" else "model"
            contents.append(
                types.Content(role=gemini_role, parts=[types.Part.from_text(text=content_text)])
            )

        if image_b64 and contents:
            import base64
            img_bytes = base64.b64decode(image_b64)
            image_part = types.Part.from_bytes(data=img_bytes, mime_type="image/png")
            contents[-1].parts.append(image_part)

        gen_config = types.GenerateContentConfig(
            temperature=self.temperatura,
            system_instruction=system_instruction,
        )

        # Usa stream
        for chunk in self.cliente.models.generate_content_stream(
            model=modelo_exec,
            contents=contents,
            config=gen_config,
        ):
            if chunk.text:
                yield chunk.text

