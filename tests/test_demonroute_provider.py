from __future__ import annotations

from lira_core.core.provider_catalog import find_model, get_llm_providers, get_models_for_provider
from lira_core.providers.demonroute_provider import DemonRouteProvider
from lira_core.providers.openrouter_provider import OpenRouterProvider, _carregar_api_keys
from lira_core.providers.provider_selector import ProviderSelector


def test_carregar_api_keys_por_prefixo(monkeypatch):
    monkeypatch.setenv("DEMONROUTE_API_KEY", "primaria")
    monkeypatch.setenv("DEMONROUTE_API_KEY_1", "extra-1")
    monkeypatch.setenv("DEMONROUTE_API_KEY_2", "")

    assert _carregar_api_keys("DEMONROUTE_API_KEY") == ["primaria", "extra-1"]


def test_cliente_aponta_para_gateway(monkeypatch):
    monkeypatch.setenv("DEMONROUTE_API_KEY", "sk-test")

    provider = DemonRouteProvider()

    assert provider.cliente is not None
    assert str(provider.cliente.base_url).rstrip("/") == "https://api.demonroute.com/v1"
    assert provider.CLIENT_TIMEOUT == 90.0
    assert provider.STREAM_TIMEOUT == 60.0


def test_fila_padrao_com_fallback(monkeypatch):
    monkeypatch.delenv("DEMONROUTE_API_KEY", raising=False)
    provider = DemonRouteProvider()

    assert provider._resolve_model_queue("TheDrummer/Cydonia-24B-v4.1", {}) == [
        "TheDrummer/Cydonia-24B-v4.1",
        "NousResearch/Hermes-3-Llama-3.1-8B",
        "mlabonne/Meta-Llama-3.1-8B-Instruct-abliterated",
    ]
    assert provider._resolve_model_queue("TheDrummer/Cydonia-24B-v4.1", {"modelos_fallback": []}) == [
        "TheDrummer/Cydonia-24B-v4.1"
    ]


def test_selector_carrega_demonroute(monkeypatch):
    monkeypatch.setenv("DEMONROUTE_API_KEY", "sk-test")

    provider = ProviderSelector().get_provider("demonroute")

    assert isinstance(provider, DemonRouteProvider)


def test_catalogo_expoe_demonroute():
    assert "demonroute" in get_llm_providers()

    models = get_models_for_provider("demonroute")
    assert {model.id for model in models} >= {
        "TheDrummer/Cydonia-24B-v4.1",
        "knifeayumu/Cydonia-v4.1-MS3.2-Magnum-Diamond-24B",
        "NousResearch/Hermes-3-Llama-3.1-8B",
    }
    assert all(model.backend == "demonroute_api" for model in models)
    assert find_model("demonroute", "TheDrummer/Cydonia-24B-v4.1") is not None


def test_openrouter_preservado_apos_refactor(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")

    provider = OpenRouterProvider()

    assert str(provider.cliente.base_url).rstrip("/") == "https://openrouter.ai/api/v1"
    assert provider.REQUEST_TIMEOUT == 25.0
    assert provider._resolve_model_queue("openrouter/free", {}) == ["openrouter/free"] * 3
