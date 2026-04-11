from pathlib import Path

from src.modules.voice import audio_control
from src.modules.voice.tts_selector import get_tts_settings


def test_global_stop_notifies_callbacks(tmp_path, monkeypatch):
    signal_path = tmp_path / "hana_stop.signal"
    monkeypatch.setattr(audio_control, "STOP_SIGNAL_PATH", signal_path)
    monkeypatch.setattr(audio_control, "_last_seen_signal_version", 0)
    audio_control.reset_stop_state()

    reasons = []
    callback_name = "test_audio_control_callback"
    audio_control.register_stop_callback(callback_name, lambda reason=None: reasons.append(reason))
    try:
        assert audio_control.request_global_stop("pytest_stop") is True
        assert audio_control.stop_requested() is True
        assert signal_path.exists()
        assert reasons[-1] == "pytest_stop"
    finally:
        audio_control.unregister_stop_callback(callback_name)
        audio_control.reset_stop_state()


def test_poll_external_stop_detects_new_signal(tmp_path, monkeypatch):
    signal_path = tmp_path / "hana_stop_external.signal"
    monkeypatch.setattr(audio_control, "STOP_SIGNAL_PATH", signal_path)
    monkeypatch.setattr(audio_control, "_last_seen_signal_version", 0)
    audio_control.reset_stop_state()

    signal_path.write_text("external", encoding="utf-8")
    monkeypatch.setattr(audio_control, "_last_seen_signal_version", 0)

    assert audio_control.poll_external_stop() is True
    assert audio_control.stop_requested() is True

    audio_control.reset_stop_state()


def test_global_stop_signal_changes_on_repeated_requests(tmp_path, monkeypatch):
    signal_path = tmp_path / "hana_stop_unique.signal"
    monkeypatch.setattr(audio_control, "STOP_SIGNAL_PATH", signal_path)
    monkeypatch.setattr(audio_control, "_last_seen_signal_version", 0)
    audio_control.reset_stop_state()

    assert audio_control.request_global_stop("first") is True
    first_payload = signal_path.read_text(encoding="utf-8")

    assert audio_control.request_global_stop("second") is True
    second_payload = signal_path.read_text(encoding="utf-8")

    assert first_payload != second_payload
    assert second_payload.endswith("|second")


def test_tts_settings_seed_elevenlabs_defaults():
    settings = get_tts_settings()
    eleven = settings.get("elevenlabs")

    assert isinstance(eleven, dict)
    assert eleven.get("voice_id")
    assert eleven.get("model_id") in {
        "eleven_flash_v2_5",
        "eleven_multilingual_v2",
        "eleven_turbo_v2_5",
        "eleven_v3",
    }
    assert "rate" in eleven
