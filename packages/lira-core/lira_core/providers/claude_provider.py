"""
Provider LLM: Anthropic Claude
"""

from __future__ import annotations

import logging
import os
from typing import Any

from lira_core.brain.base_llm import BaseLLM
from lira_core.config.config_loader import CONFIG

logger = logging.getLogger(__name__)

# Cadeia de modelos Claude por custo/qualidade
_CLAUDE_MODELS = [
    "claude-sonnet-4-5",
    "claude-haiku-4-5",
    "claude-3-5-sonnet-20241022",
    "claude-3-5-haiku-20241022",
    "claude-3-haiku-20240307",
]


class ClaudeProvider(BaseLLM):
    def __init__(self):
        self.provedor = "claude"
        prov_cfg = CONFIG.get("LLM_PROVIDERS", {}).get(self.provedor, {})
        self.modelo_chat = prov_cfg.get("modelo", prov_cfg.get("modelo_chat", "claude-haiku-4-5"))
        self.modelo_vision = prov_cfg.get("modelo_vision", self.modelo_chat)
        super().__init__()

    def _criar_cliente(self):
        try:
            import anthropic
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                logger.error("[CLAUDE] ANTHROPIC_API_KEY não encontrada no .env")
                return None
            client = anthropic.Anthropic(api_key=api_key)
            logger.info("[CLAUDE] Cliente Anthropic inicializado | modelo=%s", self.modelo_chat)
            return client
        except ImportError:
            logger.error("[CLAUDE] SDK anthropic não instalado. Execute: pip install anthropic")
            return None
        except Exception as e:
            logger.error("[CLAUDE] Erro ao criar cliente: %s", e)
            return None

    def _is_quota_error(self, exc: Exception) -> bool:
        msg = str(exc).lower()
        return "429" in msg or "rate_limit" in msg or "overloaded" in msg or "quota" in msg

    def _messages_to_anthropic(self, mensagens: list) -> tuple[str, list]:
        """Converte mensagens OpenAI-style → formato Anthropic (system separado)."""
        system_parts = []
        messages = []

        for msg in mensagens:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                system_parts.append(content)
            elif role in ("user", "human"):
                messages.append({"role": "user", "content": content})
            else:
                messages.append({"role": "assistant", "content": content})

        # Anthropic exige que comece com "user"
        if messages and messages[0]["role"] != "user":
            messages.insert(0, {"role": "user", "content": "[início da conversa]"})

        # Mescla consecutivos do mesmo role
        merged = []
        for msg in messages:
            if merged and merged[-1]["role"] == msg["role"]:
                merged[-1]["content"] += "\n\n" + msg["content"]
            else:
                merged.append(msg)

        system_text = "\n\n".join(system_parts) if system_parts else None
        return system_text, merged

    def _mock_response(self, text: str):
        """Wrapa resposta no formato BaseLLM espera."""
        class MockMsg:
            def __init__(self, c):
                self.content = c
                self.tool_calls = None

        class MockChoice:
            def __init__(self, c):
                self.message = MockMsg(c)

        class MockResp:
            def __init__(self, c):
                self.choices = [MockChoice(c)]
                self.text = c

        return MockResp(text)

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
        system_text, ant_messages = self._messages_to_anthropic(mensagens)
        max_tokens = (request_context or {}).get("max_output_tokens", 4096)

        # Monta lista de tentativas: modelo pedido + cadeia de fallback
        prov_cfg = CONFIG.get("LLM_PROVIDERS", {}).get(self.provedor, {})
        extra_fallbacks = prov_cfg.get("modelos_fallback", [])
        tentativas = [modelo] + [m for m in _CLAUDE_MODELS + extra_fallbacks if m != modelo]
        ultimo_erro = None

        for m in tentativas:
            try:
                logger.info("[CLAUDE] Chamando '%s'", m)
                self.last_request_meta = {
                    "provider": self.provedor,
                    "model": m,
                    "backend": "anthropic_api",
                    "routed": False,
                }
                kwargs: dict[str, Any] = {
                    "model": m,
                    "max_tokens": max_tokens,
                    "messages": ant_messages,
                    "temperature": self.temperatura,
                }
                if system_text:
                    kwargs["system"] = system_text

                response = self.cliente.messages.create(**kwargs)
                text = response.content[0].text if response.content else ""
                logger.info("[CLAUDE] Resposta obtida via '%s' (%d chars)", m, len(text))
                return self._mock_response(text)

            except Exception as e:
                if self._is_quota_error(e):
                    logger.warning("[CLAUDE] Rate limit em '%s'. Próximo...", m)
                    ultimo_erro = e
                    continue
                raise

        raise RuntimeError(
            f"[CLAUDE] Quota/rate limit em todos os modelos Claude disponíveis."
        ) from ultimo_erro

    def _chamar_api_stream(
        self,
        modelo,
        mensagens,
        image_b64: str = None,
        arquivos_multimidia: list = None,
        request_context: dict | None = None,
    ):
        system_text, ant_messages = self._messages_to_anthropic(mensagens)
        max_tokens = (request_context or {}).get("max_output_tokens", 4096)

        prov_cfg = CONFIG.get("LLM_PROVIDERS", {}).get(self.provedor, {})
        extra_fallbacks = prov_cfg.get("modelos_fallback", [])
        tentativas = [modelo] + [m for m in _CLAUDE_MODELS + extra_fallbacks if m != modelo]
        ultimo_erro = None

        for m in tentativas:
            try:
                logger.info("[CLAUDE STREAM] Chamando '%s'", m)
                self.last_request_meta = {
                    "provider": self.provedor,
                    "model": m,
                    "backend": "anthropic_api",
                    "routed": False,
                }
                kwargs: dict[str, Any] = {
                    "model": m,
                    "max_tokens": max_tokens,
                    "messages": ant_messages,
                    "temperature": self.temperatura,
                }
                if system_text:
                    kwargs["system"] = system_text

                with self.cliente.messages.stream(**kwargs) as stream:
                    for text in stream.text_stream:
                        yield text
                return  # sucesso

            except Exception as e:
                if self._is_quota_error(e):
                    logger.warning("[CLAUDE STREAM] Rate limit em '%s'. Próximo...", m)
                    ultimo_erro = e
                    continue
                raise

        raise RuntimeError(
            "[CLAUDE] Quota/rate limit em todos os modelos Claude disponíveis (stream)."
        ) from ultimo_erro
