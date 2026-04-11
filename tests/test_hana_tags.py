from src.utils.hana_tags import extract_xml_actions, sanitize_history_message


def test_sanitize_history_message_strips_assistant_xml_actions():
    raw = 'Pronto.<acao_pc>{"action":"type_text","text":"hana"}</acao_pc><pensamento>interno</pensamento>'

    result = sanitize_history_message("Hana", raw)

    assert result == "Pronto."


def test_sanitize_history_message_keeps_user_text_unchanged():
    raw = '<acao_pc>{"action":"type_text","text":"nao mexe"}</acao_pc>'

    result = sanitize_history_message("Nakamura", raw)

    assert result == raw


def test_sanitize_history_message_can_drop_action_only_assistant_message():
    raw = '<gerar_musica>sad cinematic 90s rock</gerar_musica>'

    result = sanitize_history_message("Hana", raw)

    assert result == ""


def test_legacy_video_tag_is_hidden_but_not_executable():
    raw = '<gerar_video>anime trailer da Hana</gerar_video>'

    result = sanitize_history_message("Hana", raw)

    assert result == ""
    assert "gerar_video" not in extract_xml_actions(raw)
