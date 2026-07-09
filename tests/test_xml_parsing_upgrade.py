import pytest
from lira_core.tools.xml_runner import _build_tool_args, default_terminal_action_tags


def test_build_tool_args_json():
    # Test parsing valid JSON payload
    res = _build_tool_args(
        "registrar_transacao",
        '{"tipo": "receita", "valor": 100.0, "estabelecimento": "Venda", "categoria": "freelance", "descricao": "projeto"}'
    )
    assert res == {
        "tipo": "receita",
        "valor": 100.0,
        "estabelecimento": "Venda",
        "categoria": "freelance",
        "descricao": "projeto"
    }


def test_build_tool_args_fallback():
    # Test parsing legacy plain text payload (split by ;)
    res = _build_tool_args("registrar_transacao", 'receita; 100.0; Venda; freelance; projeto')
    assert res == {
        "tipo": "receita",
        "valor": "100.0",
        "estabelecimento": "Venda",
        "categoria": "freelance",
        "descricao": "projeto"
    }


def test_build_tool_args_anotar_fato_json():
    # Test parsing anotar_fato JSON payload
    res = _build_tool_args(
        "anotar_fato",
        '{"sujeito": "Lira", "relacao": "gosta_de", "objeto": "Monster"}'
    )
    assert res == {
        "sujeito": "Lira",
        "relacao": "gosta_de",
        "objeto": "Monster"
    }


def test_default_terminal_action_tags():
    # Test dynamic tags mapping inclusion
    tags = default_terminal_action_tags()
    assert "anotar_fato" in tags
    assert "registrar_transacao" in tags
    assert "salvar_memoria" in tags
