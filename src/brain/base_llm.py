import json
import logging
from abc import ABC, abstractmethod

from src.config.config_loader import CONFIG
from src.core.request_profiles import build_request_context
from src.core.runtime_capabilities import get_provider_capabilities, resolve_llm_temperature
from src.utils.text import ui

logger = logging.getLogger(__name__)


class BaseLLM(ABC):
    provedor = "desconhecido"
    modelo_chat = "desconhecido"

    def __init__(self):
        self.config_valida = False
        self._runtime_scope = None
        self.temperatura = 0.85
        self.last_request_meta = {}
        self.capabilities = get_provider_capabilities(self.provedor, self.modelo_chat)
        self.cliente = self._criar_cliente()
        if self.cliente:
            self.config_valida = True
        self.refresh_runtime_settings()

    @abstractmethod
    def _criar_cliente(self):
        """Retorna a instância da biblioteca do provedor."""
        raise NotImplementedError

    @abstractmethod
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
        """Executa a chamada real à API (OpenAI style ou similar)."""
        raise NotImplementedError

    def _chamar_api_stream(
        self,
        modelo,
        mensagens,
        image_b64: str = None,
        arquivos_multimidia: list = None,
        request_context: dict | None = None,
    ):
        """
        Executa a chamada à API em modo stream.
        Retorna um iterável que emite deltas de texto.
        """
        return None

    @staticmethod
    def _merge_consecutive_roles(messages: list) -> list:
        if not messages:
            return messages

        merged = [messages[0]]
        for msg in messages[1:]:
            if msg["role"] == merged[-1]["role"] and msg["role"] != "system":
                merged[-1] = {
                    "role": merged[-1]["role"],
                    "content": merged[-1]["content"] + "\n\n" + msg["content"],
                }
            else:
                merged.append(msg)
        return merged

    def _build_messages(self, chat_history: list, sistema_prompt: str, user_message: str):
        messages = [{"role": "system", "content": sistema_prompt}]
        for msg in chat_history:
            api_message = self._history_message_to_api(msg)
            if api_message:
                messages.append(api_message)
        messages.append({"role": "user", "content": user_message})
        return self._merge_consecutive_roles(messages)

    def _history_message_to_api(self, message: dict):
        role_raw = str(message.get("role", "")).strip().lower()
        content = message.get("content", "")

        if role_raw == "nakamura":
            return {"role": "user", "content": content}
        if role_raw == "system":
            return {"role": "user", "content": f"[CONTEXTO DO SISTEMA]\n{content}"}
        return {"role": "assistant", "content": content}

    def _sync_models_from_config(self):
        prov_cfg = CONFIG.get("LLM_PROVIDERS", {}).get(self.provedor, {})
        if not isinstance(prov_cfg, dict):
            return

        modelo_chat = prov_cfg.get("modelo_chat", prov_cfg.get("modelo"))
        if modelo_chat:
            self.modelo_chat = modelo_chat

        if hasattr(self, "modelo_vision"):
            self.modelo_vision = prov_cfg.get("modelo_vision", getattr(self, "modelo_vision", self.modelo_chat))

    def refresh_runtime_settings(self, scope: str | None = None, sync_model_from_config: bool = True):
        if scope is not None:
            self._runtime_scope = scope

        if sync_model_from_config:
            self._sync_models_from_config()

        self.temperatura = resolve_llm_temperature(self._runtime_scope)
        self.capabilities = get_provider_capabilities(
            self.provedor,
            self.modelo_chat,
            vision_enabled=CONFIG.get("VISAO_ATIVA", False),
        )
        return self

    def _should_print_terminal(self, request_context: dict | None) -> bool:
        return bool((request_context or {}).get("allow_terminal_output", True))

    def _reset_request_meta(self):
        self.last_request_meta = {
            "provider": self.provedor,
            "model": self.modelo_chat,
            "backend": "default",
            "routed": False,
        }

    def gerar_resposta_stream(
        self,
        chat_history: list,
        sistema_prompt: str,
        user_message: str,
        image_b64: str = None,
        arquivos_multimidia: list = None,
        request_context: dict | None = None,
    ):
        if not self.config_valida:
            return

        request_context = request_context or build_request_context()
        self._reset_request_meta()
        messages = self._build_messages(chat_history, sistema_prompt, user_message)

        try:
            if self._should_print_terminal(request_context):
                ui.print_pensando(self.provedor.upper())

            stream = self._chamar_api_stream(
                modelo=self.modelo_chat,
                mensagens=messages,
                image_b64=image_b64,
                arquivos_multimidia=arquivos_multimidia,
                request_context=request_context,
            )

            if stream is not None:
                for token in stream:
                    if token:
                        yield token
                return

            response = self._chamar_api(
                modelo=self.modelo_chat,
                mensagens=messages,
                image_b64=image_b64,
                arquivos_multimidia=arquivos_multimidia,
                request_context=request_context,
            )
            content = ""
            if hasattr(response, "choices"):
                content = response.choices[0].message.content or ""
            elif hasattr(response, "text"):
                content = response.text
            if content:
                yield content

        except Exception as e:
            logger.error(f"[{self.provedor.upper()}] Erro no stream: {e}")
            return

    def gerar_resposta(
        self,
        chat_history: list,
        sistema_prompt: str,
        user_message: str,
        tools: list = None,
        image_b64: str = None,
        arquivos_multimidia: list = None,
        request_context: dict | None = None,
    ) -> str:
        if not self.config_valida:
            return None

        request_context = request_context or build_request_context()
        self._reset_request_meta()
        messages = self._build_messages(chat_history, sistema_prompt, user_message)

        try:
            if self._should_print_terminal(request_context):
                ui.print_pensando(self.provedor.upper())

            response = self._chamar_api(
                modelo=self.modelo_chat,
                mensagens=messages,
                ferramentas=tools,
                image_b64=image_b64,
                arquivos_multimidia=arquivos_multimidia,
                request_context=request_context,
            )

            if hasattr(response.choices[0], "message") and getattr(response.choices[0].message, "tool_calls", None):
                tool_calls = response.choices[0].message.tool_calls
                tools_list = []
                for tc in tool_calls:
                    tools_list.append(
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                        }
                    )
                return json.dumps(
                    {
                        "acao": "tool_call",
                        "tools": tools_list,
                        "texto": response.choices[0].message.content or "",
                    },
                    ensure_ascii=False,
                )

            content = ""
            if hasattr(response, "choices"):
                content = response.choices[0].message.content or ""
            elif hasattr(response, "text"):
                content = response.text

            if (
                content
                and self._should_print_terminal(request_context)
                and not content.startswith("{")
                and '"acao": "tool_call"' not in content
            ):
                print(f"{ui.C_NYRA}[HANA]{ui.C_RST}: {content}")

            return content

        except Exception as e:
            logger.error(f"[{self.provedor.upper()}] Erro de API: {e}")
            return f"(ERRO API: {e})"
