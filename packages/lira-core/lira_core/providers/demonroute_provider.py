"""
Provider LLM: DemonRoute
Gateway OpenAI-compatible (https://api.demonroute.com/v1) com modelos
open-weight voltados a roleplay. Reaproveita a rotação de keys, o fallback
de modelos e o suporte a mídia do OpenRouterProvider.

Keys aceitas: DEMONROUTE_API_KEY e DEMONROUTE_API_KEY_1..N.
"""

import logging

from lira_core.providers.openrouter_provider import OpenRouterProvider

logger = logging.getLogger(__name__)


class DemonRouteProvider(OpenRouterProvider):
    provedor = "demonroute"
    BASE_URL = "https://api.demonroute.com/v1"
    API_KEY_ENV_PREFIX = "DEMONROUTE_API_KEY"
    DEFAULT_HEADERS: dict[str, str] = {}

    # O gateway recomenda timeout mais longo para respostas de roleplay.
    # Os limites globais (CHAT_SYNTHESIS_TIMEOUT / WHATSAPP_LLM_TIMEOUT)
    # continuam mandando — aumente-os junto se precisar de respostas longas.
    CLIENT_TIMEOUT = 90.0
    REQUEST_TIMEOUT = 60.0
    STREAM_TIMEOUT = 60.0

    DEFAULT_CHAT_MODEL = "TheDrummer/Cydonia-24B-v4.1"
    # Nenhum modelo de visão confirmado no catálogo do gateway.
    DEFAULT_VISION_MODEL = ""
    DEFAULT_FALLBACK_MODELS = (
        "NousResearch/Hermes-3-Llama-3.1-8B",
        "mlabonne/Meta-Llama-3.1-8B-Instruct-abliterated",
    )

    def _resolve_model_queue(self, modelo_exec: str, prov_cfg: dict | None) -> list[str]:
        cfg = prov_cfg or {}
        if "modelos_fallback_quota" in cfg:
            extra = cfg["modelos_fallback_quota"]
        elif "modelos_fallback" in cfg:
            extra = cfg["modelos_fallback"]
        else:
            extra = list(self.DEFAULT_FALLBACK_MODELS)

        modelo_exec = (modelo_exec or self.DEFAULT_CHAT_MODEL).strip()
        if extra == []:
            return [modelo_exec]
        return [modelo_exec] + [m for m in extra if m and m != modelo_exec]

    def _prepare_messages(self, modelo, mensagens, image_b64: str = None, arquivos_multimidia: list = None):
        if (image_b64 or arquivos_multimidia) and not self.modelo_vision:
            logger.warning(
                "[%s] Mídia recebida sem modelo_vision configurado — "
                "use um modelo de visão em LLM_PROVIDERS.demonroute.modelo_vision.",
                self.log_tag,
            )
        return super()._prepare_messages(
            modelo, mensagens, image_b64=image_b64, arquivos_multimidia=arquivos_multimidia
        )
