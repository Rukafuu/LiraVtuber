import logging
import json
import re
from abc import ABC, abstractmethod
from src.utils.text import ui

logger = logging.getLogger(__name__)

class BaseLLM(ABC):
    provedor = "desconhecido"
    modelo_chat = "desconhecido"

    def __init__(self):
        self.config_valida = False
        self.temperatura = 1.0
        self.cliente = self._criar_cliente()
        if self.cliente:
            self.config_valida = True

    @abstractmethod
    def _criar_cliente(self):
        """Retorna a instância da biblioteca do provedor."""
        pass

    @abstractmethod
    def _chamar_api(self, modelo, mensagens, ferramentas=None, tool_choice="auto", image_b64: str = None):
        """Executa a chamada real à API (OpenAI style ou similar)."""
        pass

    def gerar_resposta(self, chat_history: list, sistema_prompt: str, user_message: str, tools: list = None, image_b64: str = None) -> str:
        if not self.config_valida:
            return None

        # Montar mensagens
        messages = [{"role": "system", "content": sistema_prompt}]
        for msg in chat_history:
            role = "user" if msg["role"] == "Nakamura" else "assistant"
            messages.append({"role": role, "content": msg["content"]})
        
        # A mensagem atual pode conter a imagem (multi-modal)
        messages.append({"role": "user", "content": user_message})

        try:
            ui.print_pensando(self.provedor.upper())
            
            # Chama a implementação específica do provedor
            response = self._chamar_api(
                modelo=self.modelo_chat,
                mensagens=messages,
                ferramentas=tools,
                image_b64=image_b64
            )

            # --- Tratamento de Tool Calls Nativas ---
            # Se for formato OpenAI (OpenRouter, Groq nativo, etc)
            if hasattr(response.choices[0], 'message') and getattr(response.choices[0].message, 'tool_calls', None):
                tool_calls = response.choices[0].message.tool_calls
                tools_list = []
                for tc in tool_calls:
                    tools_list.append({
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                    })
                return json.dumps({
                    "acao": "tool_call",
                    "tools": tools_list,
                    "texto": response.choices[0].message.content or ""
                }, ensure_ascii=False)

            # Caso contrário, retorna o conteúdo direto
            content = ""
            if hasattr(response, 'choices'):
                content = response.choices[0].message.content or ""
            elif hasattr(response, 'text'):
                content = response.text
            
            # --- Auto-Stream (Opcional, se não estiver usando generator) ---
            # No terminal ele já vai aparecer via print se o provider fizer stream
            # Para providers síncronos, apenas imprimimos o resultado se não for tool_call
            if content and not content.startswith("{") and '"acao": "tool_call"' not in content:
                print(f"{ui.C_NYRA}[HANA]{ui.C_RST}: {content}")

            return content

        except Exception as e:
            logger.error(f"[{self.provedor.upper()}] Erro de API: {e}")
            return None
