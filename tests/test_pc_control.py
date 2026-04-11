from pathlib import Path

import pytest

from src.modules.tools import pc_control


@pytest.fixture(autouse=True)
def isolate_audit_log(tmp_path, monkeypatch):
    monkeypatch.setattr(pc_control, "AUDIT_LOG_PATH", str(tmp_path / "pc_control_audit.jsonl"))


def test_parse_pc_action_payload_rejects_unknown_action():
    with pytest.raises(ValueError):
        pc_control.parse_pc_action_payload('{"action":"explode_pc"}')


def test_parse_pc_action_payload_accepts_type_alias_for_type_text():
    request = pc_control.parse_pc_action_payload('{"action":"type","text":"hana"}')

    assert request.action == "type_text"
    assert request.payload["text"] == "hana"


def test_parse_pc_action_payload_accepts_open_notepad_alias():
    request = pc_control.parse_pc_action_payload('{"action":"open_notepad"}')

    assert request.action == "start_process"
    assert request.payload["command"] == "notepad.exe"


def test_execute_pc_action_denies_high_risk_when_confirmation_rejects():
    result = pc_control.execute_pc_action(
        {"action": "run_command", "command": "echo hello"},
        confirm_callback=lambda _request: False,
    )

    assert result["ok"] is False
    assert result["status"] == "denied"
    assert result["action"] == "run_command"


def test_execute_pc_action_reads_text_file(tmp_path):
    sample = tmp_path / "sample.txt"
    sample.write_text("hana desktop control", encoding="utf-8")

    result = pc_control.execute_pc_action(
        {"action": "read_text_file", "path": str(sample)},
        confirm_callback=lambda _request: True,
    )

    assert result["ok"] is True
    assert "desktop control" in result["content"]


def test_execute_pc_action_kill_process_requires_target():
    result = pc_control.execute_pc_action(
        {"action": "kill_process"},
        confirm_callback=lambda _request: True,
    )

    assert result["ok"] is False
    assert result["status"] == "failed"
    assert "pid" in result["message"].lower() or "name" in result["message"].lower()


def test_execute_pc_action_list_processes_formats_output(monkeypatch):
    class FakeProc:
        def __init__(self, pid, name):
            self.info = {"pid": pid, "name": name}

    monkeypatch.setattr(
        pc_control.psutil,
        "process_iter",
        lambda _fields: [FakeProc(10, "brave.exe"), FakeProc(11, "python.exe")],
    )

    result = pc_control.execute_pc_action(
        {"action": "list_processes", "query": "brave"},
        confirm_callback=lambda _request: True,
    )

    assert result["ok"] is True
    assert result["count"] == 1
    assert "brave.exe" in result["content"]


def test_execute_pc_action_move_mouse_supports_direction(monkeypatch):
    moved = {}

    monkeypatch.setattr(pc_control, "_get_cursor_pos", lambda: (100, 200))

    class User32Stub:
        @staticmethod
        def SetCursorPos(x, y):
            moved["coords"] = (x, y)

    monkeypatch.setattr(pc_control.ctypes, "windll", type("WindllStub", (), {"user32": User32Stub()})())

    result = pc_control.execute_pc_action(
        {"action": "move_mouse", "direction": "right", "distance": 50},
        confirm_callback=lambda _request: (_ for _ in ()).throw(AssertionError("confirmacao nao deveria ser chamada")),
    )

    assert result["ok"] is True
    assert moved["coords"] == (150, 200)


def test_execute_pc_action_type_text_does_not_require_confirmation(monkeypatch):
    typed = {}

    class KeyboardStub:
        @staticmethod
        def write(text, delay=0):
            typed["text"] = text
            typed["delay"] = delay

        @staticmethod
        def press_and_release(_key):
            typed["pressed_enter"] = True

    monkeypatch.setattr(pc_control, "keyboard", KeyboardStub())
    monkeypatch.setattr(pc_control, "_focus_window_for_payload", lambda _payload: True)

    result = pc_control.execute_pc_action(
        {"action": "type_text", "text": "hana"},
        confirm_callback=lambda _request: (_ for _ in ()).throw(AssertionError("confirmacao nao deveria ser chamada")),
    )

    assert result["ok"] is True
    assert typed["text"] == "hana"


def test_parse_pc_action_payload_infers_set_volume_from_natural_language():
    request = pc_control.parse_pc_action_payload(
        {"action": "set_volume", "text": "diminui o som do PC"}
    )

    assert request.action == "set_volume"
    assert request.payload["delta"] < 0


def test_parse_pc_action_payload_infers_set_volume_level_from_percent_string():
    request = pc_control.parse_pc_action_payload(
        {"action": "set_volume", "value": "30%"}
    )

    assert request.action == "set_volume"
    assert request.payload["level"] == 30


def test_execute_pc_action_start_process_does_not_require_confirmation(monkeypatch):
    launched = {}

    class FakeProc:
        pid = 4321

    def fake_popen(command, cwd=None, shell=False):
        launched["command"] = command
        launched["cwd"] = cwd
        launched["shell"] = shell
        return FakeProc()

    monkeypatch.setattr(pc_control.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(pc_control, "_find_window_handle", lambda **_kwargs: 123)
    monkeypatch.setattr(pc_control, "_focus_window_handle", lambda _hwnd: True)
    monkeypatch.setattr(pc_control.time, "sleep", lambda _seconds: None)

    result = pc_control.execute_pc_action(
        {"action": "start_process", "command": "notepad.exe"},
        confirm_callback=lambda _request: (_ for _ in ()).throw(AssertionError("confirmacao nao deveria ser chamada")),
    )

    assert result["ok"] is True
    assert result["pid"] == 4321
    assert launched["command"] == "notepad.exe"
