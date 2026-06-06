"""
Provider LLM: OpenRouter
Suporta múltiplas API keys (OPENROUTER_API_KEY, OPENROUTER_API_KEY_1..N)
com rotação automática em caso de 429 / RESOURCE_EXHAUSTED.
"""

import logging
import os

from openai import OpenAI

from lira_core.brain.base_llm import BaseLLM
from lira_core.config.config_loader import CONFIG

logger = logging.getLogger(__name__)


def _carregar_api_keys() -> list[str]:
    """
    Coleta todas as API keys do OpenRouter disponíveis no ambiente.
    Aceita:
      - OPENROUTER_API_KEY        (key principal / legacy)
      - OPENROUTER_API_KEY_1..N   (keys extras para rotação)
    Retorna lista sem duplicatas, preservando ordem.
    """
    vistas = set()
    keys = []

    # key principal (sem sufixo)
    k = os.getenv("OPENROUTER_API_KEY", "").strip()
    if k and k not in vistas:
        keys.append(k)
        vistas.add(k)

    # keys numeradas (_1, _2, ...)
    for i in range(1, 20):
        k = os.getenv(f"OPENROUTER_API_KEY_{i}", "").strip()
        if not k:
            break
        if k not in vistas:
            keys.append(k)
            vistas.add(k)

    return keys


def _is_quota_error(e: Exception) -> bool:
    msg = str(e)
    return (
        "429" in msg
        or "RESOURCE_EXHAUSTED" in msg
        or "quota" in msg.lower()
        or "rate limit" in msg.lower()
    )


def _is_model_error(e: Exception) -> bool:
    """Erro que indica o modelo não existe ou foi descontinuado (404, etc.)."""
    msg = str(e)
    return (
        "404" in msg
        or "no longer available" in msg.lower()
        or "model not found" in msg.lower()
        or "does not exist" in msg.lower()
    )


OPENROUTER_FREE_ROUTER = "openrouter/free"


def resolve_openrouter_model_queue(modelo_exec: str, prov_cfg: dict | None = None) -> list[str]:
    """
    Monta a fila de modelos para tentativa.
    Com openrouter/free, repete o router (cada chamada pode cair em outro backend free).
    """
    cfg = prov_cfg or {}
    if "modelos_fallback_quota" in cfg:
        extra = cfg["modelos_fallback_quota"]
    elif "modelos_fallback" in cfg:
        extra = cfg["modelos_fallback"]
    else:
        extra = None

    modelo_exec = (modelo_exec or OPENROUTER_FREE_ROUTER).strip()

    if modelo_exec == OPENROUTER_FREE_ROUTER:
        retries = max(1, int(cfg.get("free_router_retries", 3)))
        queue = [OPENROUTER_FREE_ROUTER] * retries
        if extra:
            queue.extend(m for m in extra if m and m != OPENROUTER_FREE_ROUTER)
        return queue

    if extra is None:
        extra = [
            "qwen/qwen3-30b-a3b:free",
            "google/gemma-3-27b-it:free",
            "mistralai/mistral-7b-instruct:free",
        ]
    if extra == []:
        return [modelo_exec]
    return [modelo_exec] + [m for m in extra if m != modelo_exec]


def _criar_cliente_com_key(api_key: str) -> OpenAI:
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        max_retries=1,
        timeout=25.0,
        default_headers={
            "HTTP-Referer": "https://github.com/Rukafuu/LiraVtuber",
            "X-Title": "Lira Amarinth",
        },
    )


class OpenRouterProvider(BaseLLM):
    def __init__(self):
        self.provedor = "openrouter"
        prov_cfg = CONFIG.get("LLM_PROVIDERS", {}).get(self.provedor, {})
        self.modelo_chat = prov_cfg.get("modelo", prov_cfg.get("modelo_chat", "openrouter/owl-alpha"))
        self.modelo_vision = prov_cfg.get("modelo_vision", "nvidia/nemotron-nano-12b-v2-vl:free")
        self.modelo_fallback_vision = prov_cfg.get("modelo_fallback_vision", "nvidia/nemotron-nano-12b-v2-vl:free")

        # ── Multi-key setup ──────────────────────────────────────────────
        self._api_keys = _carregar_api_keys()
        self._idx_key = 0  # índice da key ativa

        if len(self._api_keys) > 1:
            logger.info(
                "[OPENROUTER] %d API keys carregadas — rotação automática ativada.",
                len(self._api_keys),
            )
        elif len(self._api_keys) == 1:
            logger.info("[OPENROUTER] 1 API key carregada (sem rotação).")
        else:
            logger.error("[OPENROUTER] Nenhuma OPENROUTER_API_KEY encontrada no .env!")

        super().__init__()

    # ── Criação de cliente ───────────────────────────────────────────────

    def _criar_cliente(self):
        if not self._api_keys:
            logger.error("[OPENROUTER] OPENROUTER_API_KEY não encontrada no .env")
            return None
        try:
            return _criar_cliente_com_key(self._api_keys[self._idx_key])
        except Exception as e:
            logger.error(f"[OPENROUTER] Erro ao criar cliente: {e}")
            return None

    def _rotacionar_key(self) -> bool:
        """
        Avança para a próxima API key disponível.
        Retorna True se conseguiu rotacionar, False se esgotou todas.
        """
        if self._idx_key + 1 >= len(self._api_keys):
            return False
        self._idx_key += 1
        nova_key = self._api_keys[self._idx_key]
        logger.warning(
            "[OPENROUTER] Quota esgotada — rotacionando para key %d/%d.",
            self._idx_key + 1,
            len(self._api_keys),
        )
        try:
            self.cliente = _criar_cliente_com_key(nova_key)
            return True
        except Exception as e:
            logger.error(f"[OPENROUTER] Erro ao criar cliente com nova key: {e}")
            return False

    # ── Preparação de payload ────────────────────────────────────────────

    def _prepare_messages(self, modelo, mensagens, image_b64: str = None):
        modelo_exec = modelo
        payload_messages = list(mensagens)
        if image_b64:
            prov_cfg = CONFIG.get("LLM_PROVIDERS", {}).get(self.provedor, {})
            modelo_exec = prov_cfg.get("modelo_vision", self.modelo_vision or modelo)

            mime_type = "image/png"
            if image_b64.startswith("/9j/"):
                mime_type = "image/jpeg"
            elif image_b64.startswith("iVBOR"):
                mime_type = "image/png"
            elif image_b64.startswith("R0lGOD"):
                mime_type = "image/gif"

            ultima_msg = payload_messages[-1]
            payload_messages[-1] = {
                "role": "user",
                "content": [
                    {"type": "text", "text": ultima_msg["content"]},
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_b64}"}},
                ],
            }
            logger.info(f"[OPENROUTER] Ativando modo VISÃO com modelo: {modelo_exec}")
        return modelo_exec, payload_messages

    # ── Chamada principal com fallback de key + modelo ───────────────────

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
        modelo_exec, payload_messages = self._prepare_messages(modelo, mensagens, image_b64=image_b64)

        prov_cfg = CONFIG.get("LLM_PROVIDERS", {}).get(self.provedor, {})
        modelos = resolve_openrouter_model_queue(modelo_exec, prov_cfg)
        ultimo_erro = None

        for idx_modelo, m_tentativa in enumerate(modelos):
            # Para cada modelo, tenta todas as keys disponíveis
            tentativas_key = 0
            while True:
                logger.info(
                    "[OPENROUTER] Modelo %s | Key %d/%d",
                    m_tentativa, self._idx_key + 1, len(self._api_keys),
                )
                kwargs = {
                    "model": m_tentativa,
                    "messages": payload_messages,
                    "temperature": self.temperatura,
                    "max_tokens": (request_context or {}).get("max_output_tokens", 8192),
                    "timeout": 25.0,
                }
                if ferramentas:
                    kwargs["tools"] = ferramentas
                    kwargs["tool_choice"] = tool_choice

                self.last_request_meta = {
                    "provider": self.provedor,
                    "model": m_tentativa,
                    "backend": "openrouter_api",
                    "routed": m_tentativa == OPENROUTER_FREE_ROUTER,
                    "api_key_index": self._idx_key,
                }
                try:
                    resposta = self.cliente.chat.completions.create(**kwargs)
                    logger.info(f"[OPENROUTER] ✅ Sucesso: {m_tentativa} (key {self._idx_key + 1})")
                    return resposta

                except Exception as e:
                    ultimo_erro = e

                    if _is_quota_error(e):
                        # Tenta a próxima key antes de trocar de modelo
                        if self._rotacionar_key():
                            tentativas_key += 1
                            continue  # repete o while com a nova key
                        else:
                            # Esgotou todas as keys — reseta o índice e vai pro próximo modelo
                            logger.warning(
                                "[OPENROUTER] Todas as keys esgotadas para %s — tentando próximo modelo.",
                                m_tentativa,
                            )
                            self._idx_key = 0
                            self.cliente = _criar_cliente_com_key(self._api_keys[0])
                            break  # sai do while, continua o for

                    elif _is_model_error(e):
                        logger.warning(f"[OPENROUTER] Modelo indisponível: {m_tentativa} — {e}")
                        break  # vai pro próximo modelo

                    else:
                        # Erro genérico (timeout, 500, etc.) — tenta o próximo modelo direto
                        logger.warning(f"[OPENROUTER] Erro em {m_tentativa}: {e}")
                        break

        raise ultimo_erro

    # ── Stream com fallback de key + modelo ─────────────────────────────

    def _chamar_api_stream(
        self,
        modelo,
        mensagens,
        image_b64: str = None,
        arquivos_multimidia: list = None,
        request_context: dict | None = None,
    ):
        modelo_exec, payload_messages = self._prepare_messages(modelo, mensagens, image_b64=image_b64)

        prov_cfg = CONFIG.get("LLM_PROVIDERS", {}).get(self.provedor, {})
        modelos = resolve_openrouter_model_queue(modelo_exec, prov_cfg)
        ultimo_erro = None

        for m_tentativa in modelos:
            while True:
                logger.info(
                    "[OPENROUTER STREAM] Modelo %s | Key %d/%d",
                    m_tentativa, self._idx_key + 1, len(self._api_keys),
                )
                self.last_request_meta = {
                    "provider": self.provedor,
                    "model": m_tentativa,
                    "backend": "openrouter_api",
                    "routed": m_tentativa == OPENROUTER_FREE_ROUTER,
                    "api_key_index": self._idx_key,
                }
                try:
                    stream = self.cliente.chat.completions.create(
                        model=m_tentativa,
                        messages=payload_messages,
                        temperature=self.temperatura,
                        max_tokens=(request_context or {}).get("max_output_tokens", 8192),
                        stream=True,
                        timeout=20.0,
                    )
                    for chunk in stream:
                        delta = chunk.choices[0].delta if chunk.choices else None
                        if delta and delta.content:
                            yield delta.content
                    return  # stream concluído com sucesso

                except Exception as e:
                    ultimo_erro = e

                    if _is_quota_error(e):
                        if self._rotacionar_key():
                            continue
                        else:
                            self._idx_key = 0
                            self.cliente = _criar_cliente_com_key(self._api_keys[0])
                            break
                    else:
                        logger.warning(f"[OPENROUTER STREAM] Falha no modelo {m_tentativa}: {e}")
                        break

        raise ultimo_erro
