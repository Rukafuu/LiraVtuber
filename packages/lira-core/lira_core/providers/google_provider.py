"""
Provider LLM: Google Gemini / Vertex AI via google.genai
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from google import genai
from google.genai import types

from lira_core.brain.base_llm import BaseLLM
from lira_core.config.config_loader import CONFIG

logger = logging.getLogger(__name__)

# Cadeia de fallback intra-Gemini
_FALLBACK_CHAIN = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
]

def _get_openrouter_fallback():
    """Retorna instância lazy do OpenRouterProvider configurada com modelos free."""
    try:
        from lira_core.providers.openrouter_provider import (
            OpenRouterProvider,
            resolve_openrouter_model_queue,
        )
        from lira_core.config.config_loader import CONFIG as _CFG
        import os

        if not os.getenv("OPENROUTER_API_KEY"):
            return None, []

        prov = OpenRouterProvider()
        if not prov.config_valida:
            return None, []

        or_cfg = _CFG.get("LLM_PROVIDERS", {}).get("openrouter", {})
        models = resolve_openrouter_model_queue(prov.modelo_chat, or_cfg)
        return prov, models
    except Exception as e:
        logger.warning("[GOOGLE] OpenRouter fallback indisponível: %s", e)
        return None, []


def _get_claude_fallback():
    """Retorna instância lazy do ClaudeProvider como fallback premium."""
    try:
        from lira_core.providers.claude_provider import ClaudeProvider
        import os

        if not os.getenv("ANTHROPIC_API_KEY"):
            return None

        prov = ClaudeProvider()
        return prov if prov.config_valida else None
    except Exception as e:
        logger.warning("[GOOGLE] Claude fallback indisponível: %s", e)
        return None


def _get_groq_fallback():
    """Groq — fallback rápido quando Gemini/OpenRouter free estão em 429."""
    try:
        from lira_core.providers.groq_provider import GroqProvider

        if not os.getenv("GROQ_API_KEY"):
            return None
        prov = GroqProvider()
        return prov if prov.config_valida else None
    except Exception as e:
        logger.warning("[GOOGLE] Groq fallback indisponível: %s", e)
        return None


def _try_provider_api(provider, modelo, mensagens, request_context, *, label: str):
    if not provider:
        return None
    try:
        result = provider._chamar_api(
            modelo=modelo,
            mensagens=mensagens,
            request_context=request_context,
        )
        if not result:
            return None
        text = ""
        if hasattr(result, "choices") and result.choices:
            text = result.choices[0].message.content or ""
        elif hasattr(result, "text"):
            text = result.text
        if text:
            logger.info("[%s] Resposta obtida com sucesso", label)
            return text
    except Exception as exc:
        logger.warning("[%s] Falha: %s", label, exc)
    return None





class GoogleProvider(BaseLLM):
    def __init__(self):
        self.provedor = "google_cloud"
        prov_cfg = CONFIG.get("LLM_PROVIDERS", {}).get(self.provedor, {})
        self.modelo_chat = prov_cfg.get("modelo", "gemini-2.5-flash-preview-04-17")
        self._client_gemini_api = None
        self._client_vertex = None
        self._default_backend = "gemini_api"
        super().__init__()

    def _criar_cliente(self):
        client = self._get_client_for_backend(self._resolve_backend({}))
        if client:
            logger.info(
                "[GOOGLE] Cliente inicializado | backend=%s | modelo=%s",
                self._default_backend,
                self.modelo_chat,
            )
        return client

    def _provider_config(self) -> dict:
        prov_cfg = CONFIG.get("LLM_PROVIDERS", {}).get(self.provedor, {})
        return prov_cfg if isinstance(prov_cfg, dict) else {}

    def _resolve_backend(self, request_context: dict | None) -> str:
        prov_cfg = self._provider_config()
        requested_backend = str(prov_cfg.get("backend", "auto") or "auto").strip().lower()
        if requested_backend not in {"auto", "gemini_api", "vertex_ai"}:
            requested_backend = "auto"

        if requested_backend == "gemini_api":
            self._default_backend = "gemini_api"
            return "gemini_api"

        if requested_backend == "vertex_ai":
            if self._vertex_ready():
                self._default_backend = "vertex_ai"
                return "vertex_ai"
            self._default_backend = "gemini_api"
            return "gemini_api"

        if self._vertex_ready():
            self._default_backend = "vertex_ai"
            return "vertex_ai"
        self._default_backend = "gemini_api"
        return "gemini_api"

    def _vertex_ready(self) -> bool:
        prov_cfg = self._provider_config()
        project = (
            prov_cfg.get("vertex_project")
            or CONFIG.get("GOOGLE_CLOUD_PROJECT")
            or os.getenv("GOOGLE_CLOUD_PROJECT")
        )
        location = (
            prov_cfg.get("vertex_location")
            or CONFIG.get("GOOGLE_CLOUD_LOCATION")
            or os.getenv("GOOGLE_CLOUD_LOCATION")
            or "global"
        )
        has_creds = bool(
            prov_cfg.get("vertex_credentials")
            or CONFIG.get("GOOGLE_APPLICATION_CREDENTIALS")
            or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        )
        return bool(project and location and has_creds)

    def _build_vertex_client(self):
        prov_cfg = self._provider_config()
        project = (
            prov_cfg.get("vertex_project")
            or CONFIG.get("GOOGLE_CLOUD_PROJECT")
            or os.getenv("GOOGLE_CLOUD_PROJECT")
        )
        location = (
            prov_cfg.get("vertex_location")
            or CONFIG.get("GOOGLE_CLOUD_LOCATION")
            or os.getenv("GOOGLE_CLOUD_LOCATION")
            or "global"
        )
        credentials_path = (
            prov_cfg.get("vertex_credentials")
            or CONFIG.get("GOOGLE_APPLICATION_CREDENTIALS")
            or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        )
        if credentials_path:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(credentials_path)

        return genai.Client(vertexai=True, project=project, location=location)

    def _build_gemini_api_client(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.error("[GOOGLE] GEMINI_API_KEY não encontrada.")
            return None
        return genai.Client(api_key=api_key)

    def _get_client_for_backend(self, backend: str):
        try:
            if backend == "vertex_ai":
                if self._client_vertex is None:
                    self._client_vertex = self._build_vertex_client()
                return self._client_vertex

            if self._client_gemini_api is None:
                self._client_gemini_api = self._build_gemini_api_client()
            return self._client_gemini_api
        except Exception as e:
            logger.error("[GOOGLE] Falha ao criar cliente %s: %s", backend, e)
            return None

    def _resolve_model(self, modelo, image_b64: str = None, arquivos_multimidia: list | None = None, request_context: dict | None = None):
        prov_cfg = self._provider_config()
        override_model = (request_context or {}).get("override_model")
        if override_model:
            return str(override_model)

        if image_b64 or arquivos_multimidia:
            return prov_cfg.get("modelo_vision", modelo)
        return modelo

    def _build_contents(self, mensagens, image_b64: str = None, arquivos_multimidia: list | None = None, client=None):
        contents = []
        system_instruction = None

        for msg in mensagens:
            role = msg["role"]
            content_text = msg["content"]

            if role == "system":
                system_instruction = content_text
                continue

            gemini_role = "user" if role == "user" else "model"
            contents.append(types.Content(role=gemini_role, parts=[types.Part.from_text(text=content_text)]))

        if image_b64 and contents:
            import base64

            img_bytes = base64.b64decode(image_b64)
            contents[-1].parts.append(types.Part.from_bytes(data=img_bytes, mime_type="image/png"))

        if arquivos_multimidia and contents:
            import mimetypes
            for filepath in arquivos_multimidia:
                if not os.path.exists(filepath):
                    continue
                try:
                    logger.info("[GOOGLE] Carregando mídia inline: %s", filepath)
                    with open(filepath, "rb") as f:
                        file_bytes = f.read()

                    mime_type, _ = mimetypes.guess_type(filepath)
                    if not mime_type:
                        lower = filepath.lower()
                        if lower.endswith(".png"):
                            mime_type = "image/png"
                        elif lower.endswith((".jpg", ".jpeg")):
                            mime_type = "image/jpeg"
                        elif lower.endswith(".gif"):
                            mime_type = "image/gif"
                        elif lower.endswith(".webp"):
                            mime_type = "image/webp"
                        else:
                            mime_type = "image/png"

                    file_part = types.Part.from_bytes(data=file_bytes, mime_type=mime_type)
                    contents[-1].parts.append(file_part)
                except Exception as e:
                    logger.error("[GOOGLE] Erro ao processar mídia inline %s: %s", filepath, e)

        return contents, system_instruction

    def _build_tools(self, image_b64: str = None, arquivos_multimidia: list | None = None, request_context: dict | None = None):
        if image_b64 or arquivos_multimidia:
            return None
        if request_context and request_context.get("native_search") is True:
            return [types.Tool(google_search=types.GoogleSearch())]
        return None

    def _thinking_config_for_request(self, modelo_exec: str, request_context: dict | None):
        request_context = request_context or {}
        thinking_level = request_context.get("thinking_level")
        thinking_budget = request_context.get("thinking_budget")
        model_key = (modelo_exec or "").lower()

        if "gemini-3" in model_key and thinking_level:
            normalized_level = str(thinking_level).upper()
            if "flash-lite" in model_key and normalized_level == "LOW":
                normalized_level = "MINIMAL"
            level_enum = getattr(types.ThinkingLevel, normalized_level, None)
            if level_enum is not None:
                return types.ThinkingConfig(thinking_level=level_enum)

        if ("gemini-2.5" in model_key or "gemini-2.0" in model_key) and thinking_budget is not None:
            return types.ThinkingConfig(thinking_budget=int(thinking_budget))

        return None

    def _build_generation_config(self, modelo_exec: str, system_instruction: str | None, image_b64: str = None, arquivos_multimidia: list | None = None, request_context: dict | None = None):
        request_context = request_context or {}
        config_kwargs: dict[str, Any] = {
            "temperature": self.temperatura,
            "system_instruction": system_instruction,
            "tools": self._build_tools(image_b64=image_b64, arquivos_multimidia=arquivos_multimidia, request_context=request_context),
            "max_output_tokens": request_context.get("max_output_tokens"),
        }

        thinking_config = self._thinking_config_for_request(modelo_exec, request_context)
        if thinking_config is not None:
            config_kwargs["thinking_config"] = thinking_config

        response_mime_type = request_context.get("response_mime_type")
        response_schema = request_context.get("response_schema")
        if response_mime_type:
            config_kwargs["response_mime_type"] = response_mime_type
        if response_schema:
            config_kwargs["response_schema"] = response_schema

        if request_context.get("audio_timestamp"):
            config_kwargs["audio_timestamp"] = True

        clean_kwargs = {key: value for key, value in config_kwargs.items() if value is not None}
        return types.GenerateContentConfig(**clean_kwargs)

    def _count_tokens_if_possible(self, client, modelo_exec: str, contents, request_context: dict | None = None):
        if not (request_context or {}).get("measure_tokens", False):
            return None
        try:
            response = client.models.count_tokens(model=modelo_exec, contents=contents)
            return getattr(response, "total_tokens", None)
        except Exception as e:
            logger.debug("[GOOGLE] Count tokens indisponível: %s", e)
            return None

    def _mock_response(self, text: str):
        class MockResponse:
            class MockChoice:
                class MockMessage:
                    def __init__(self, content):
                        self.content = content
                        self.tool_calls = None

                def __init__(self, content):
                    self.message = self.MockMessage(content)

            def __init__(self, value):
                self.choices = [self.MockChoice(value)]

        return MockResponse(text)

    def _prepare_request(self, modelo, mensagens, image_b64: str = None, arquivos_multimidia: list | None = None, request_context: dict | None = None):
        backend = self._resolve_backend(request_context)
        client = self._get_client_for_backend(backend)
        if not client and backend == "vertex_ai":
            backend = "gemini_api"
            client = self._get_client_for_backend(backend)
        if not client:
            raise RuntimeError("Cliente Google indisponível para Gemini API/Vertex AI.")

        modelo_exec = self._resolve_model(modelo, image_b64=image_b64, arquivos_multimidia=arquivos_multimidia, request_context=request_context)
        contents, system_instruction = self._build_contents(
            mensagens,
            image_b64=image_b64,
            arquivos_multimidia=arquivos_multimidia,
            client=client,
        )
        gen_config = self._build_generation_config(
            modelo_exec,
            system_instruction=system_instruction,
            image_b64=image_b64,
            arquivos_multimidia=arquivos_multimidia,
            request_context=request_context,
        )
        token_count = self._count_tokens_if_possible(client, modelo_exec, contents, request_context=request_context)
        self.last_request_meta = {
            "provider": self.provedor,
            "model": modelo_exec,
            "backend": backend,
            "routed": bool((request_context or {}).get("routed")),
            "token_count": token_count,
            "structured_output": bool((request_context or {}).get("response_schema")),
        }
        return client, modelo_exec, contents, gen_config

    def _is_quota_error(self, exc: Exception) -> bool:
        """Retorna True se o erro é 429 / RESOURCE_EXHAUSTED."""
        msg = str(exc).lower()
        return "429" in msg or "resource_exhausted" in msg or "quota" in msg

    def _fallback_models_for(self, modelo_exec: str) -> list[str]:
        """Retorna próximos modelos na cadeia de fallback após modelo_exec."""
        model_lower = modelo_exec.lower()
        # encontra onde estamos na cadeia
        for i, m in enumerate(_FALLBACK_CHAIN):
            if m in model_lower:
                return _FALLBACK_CHAIN[i + 1:]
        return _FALLBACK_CHAIN  # se não reconhecer, tenta todos

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
        client, modelo_exec, contents, gen_config = self._prepare_request(
            modelo,
            mensagens,
            image_b64=image_b64,
            arquivos_multimidia=arquivos_multimidia,
            request_context=request_context,
        )
        try:
            response = client.models.generate_content(
                model=modelo_exec,
                contents=contents,
                config=gen_config,
            )
            return self._mock_response(response.text)
        except Exception as e:
            if not self._is_quota_error(e):
                raise
            # --- fallback intra-Gemini ---
            logger.warning(
                "[GOOGLE] 429 no modelo '%s'. Tentando fallback Gemini...", modelo_exec
            )
            for fallback_model in self._fallback_models_for(modelo_exec):
                try:
                    logger.info("[GOOGLE] Fallback Gemini → %s", fallback_model)
                    response = client.models.generate_content(
                        model=fallback_model,
                        contents=contents,
                        config=gen_config,
                    )
                    logger.info("[GOOGLE] Resposta via Gemini fallback '%s'", fallback_model)
                    return self._mock_response(response.text)
                except Exception as fe:
                    if self._is_quota_error(fe):
                        logger.warning("[GOOGLE] 429 fallback '%s'. Próximo...", fallback_model)
                    else:
                        logger.warning("[GOOGLE] Erro '%s' no fallback '%s'. Próximo...", fe, fallback_model)
                    continue

            # --- fallback Claude → Groq → OpenRouter ---
            logger.warning("[GOOGLE] Quota Gemini esgotada. Tentando Claude...")
            claude_prov = _get_claude_fallback()
            text = _try_provider_api(
                claude_prov,
                claude_prov.modelo_chat if claude_prov else None,
                mensagens,
                request_context,
                label="GOOGLE→CLAUDE",
            )
            if text:
                return self._mock_response(text)

            logger.warning("[GOOGLE] Tentando Groq...")
            groq_prov = _get_groq_fallback()
            text = _try_provider_api(
                groq_prov,
                groq_prov.modelo_chat if groq_prov else None,
                mensagens,
                request_context,
                label="GOOGLE→GROQ",
            )
            if text:
                return self._mock_response(text)

            # --- fallback cross-provider: OpenRouter ---
            logger.warning("[GOOGLE] Tentando OpenRouter...")
            or_provider, or_models = _get_openrouter_fallback()
            if or_provider:
                for or_model in or_models:
                    try:
                        logger.info("[GOOGLE→OPENROUTER] Tentando '%s'", or_model)
                        result = or_provider._chamar_api(
                            modelo=or_model,
                            mensagens=mensagens,
                            request_context=request_context,
                        )
                        if result:
                            text = ""
                            if hasattr(result, "choices") and result.choices:
                                text = result.choices[0].message.content or ""
                            elif hasattr(result, "text"):
                                text = result.text
                            logger.info("[GOOGLE→OPENROUTER] Resposta via '%s'", or_model)
                            return self._mock_response(text)
                    except Exception as ore:
                        logger.warning("[GOOGLE→OPENROUTER] Falha em '%s': %s", or_model, ore)
                        continue

            raise RuntimeError(
                "Quota esgotada em todos os provedores (Gemini, Claude, Groq, OpenRouter). "
                "Espere 1–2 min ou troque LLM_PROVIDER para groq/openrouter no painel."
            ) from e

    def _chamar_api_stream(
        self,
        modelo,
        mensagens,
        image_b64: str = None,
        arquivos_multimidia: list = None,
        request_context: dict | None = None,
    ):
        client, modelo_exec, contents, gen_config = self._prepare_request(
            modelo,
            mensagens,
            image_b64=image_b64,
            arquivos_multimidia=arquivos_multimidia,
            request_context=request_context,
        )
        try:
            for chunk in client.models.generate_content_stream(
                model=modelo_exec,
                contents=contents,
                config=gen_config,
            ):
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            if not self._is_quota_error(e):
                raise
            logger.warning("[GOOGLE] 429 no stream '%s'. Fallback Gemini...", modelo_exec)
            for fallback_model in self._fallback_models_for(modelo_exec):
                try:
                    logger.info("[GOOGLE] Stream Gemini fallback → %s", fallback_model)
                    for chunk in client.models.generate_content_stream(
                        model=fallback_model, contents=contents, config=gen_config,
                    ):
                        if chunk.text:
                            yield chunk.text
                    return
                except Exception as fe:
                    if self._is_quota_error(fe):
                        logger.warning("[GOOGLE] 429 stream fallback '%s'. Próximo...", fallback_model)
                    else:
                        logger.warning("[GOOGLE] Erro '%s' no stream fallback '%s'. Próximo...", fe, fallback_model)
                    continue

            # --- fallback Claude → Groq stream ---
            logger.warning("[GOOGLE] Quota Gemini stream esgotada. Tentando Claude...")
            claude_prov = _get_claude_fallback()
            if claude_prov:
                try:
                    for token in claude_prov._chamar_api_stream(
                        modelo=claude_prov.modelo_chat,
                        mensagens=mensagens,
                        request_context=request_context,
                    ):
                        yield token
                    return
                except Exception as ce:
                    logger.warning("[GOOGLE→CLAUDE STREAM] Falha: %s", ce)

            logger.warning("[GOOGLE] Tentando Groq stream...")
            groq_prov = _get_groq_fallback()
            if groq_prov:
                try:
                    for token in groq_prov._chamar_api_stream(
                        modelo=groq_prov.modelo_chat,
                        mensagens=mensagens,
                        request_context=request_context,
                    ):
                        yield token
                    return
                except Exception as ge:
                    logger.warning("[GOOGLE→GROQ STREAM] Falha: %s", ge)

            # --- fallback cross-provider: OpenRouter stream ---
            logger.warning("[GOOGLE] Tentando OpenRouter stream...")
            or_provider, or_models = _get_openrouter_fallback()
            if or_provider:
                for or_model in or_models:
                    try:
                        logger.info("[GOOGLE→OPENROUTER STREAM] Tentando '%s'", or_model)
                        for token in or_provider._chamar_api_stream(
                            modelo=or_model,
                            mensagens=mensagens,
                            request_context=request_context,
                        ):
                            yield token
                        return
                    except Exception as ore:
                        logger.warning("[GOOGLE→OPENROUTER STREAM] Falha em '%s': %s", or_model, ore)
                        continue

            raise RuntimeError(
                "Quota esgotada em todos os provedores (Gemini, Claude, Groq, OpenRouter) - stream."
            ) from e
