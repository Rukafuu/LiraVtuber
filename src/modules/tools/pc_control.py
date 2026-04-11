from __future__ import annotations

import ctypes
import json
import logging
import os
import re
import subprocess
import time
import webbrowser
from dataclasses import dataclass
from ctypes import wintypes
from typing import Any, Callable

import psutil

from src.config.config_loader import CONFIG
from src.gui.widgets.pc_action_popup import confirm_pc_action_popup
from src.modules.tools.inbox_manager import InboxManager

logger = logging.getLogger(__name__)

try:
    import keyboard
except ImportError:  # pragma: no cover - optional dependency path
    keyboard = None


AUDIT_LOG_PATH = os.path.join("data", "logs", "pc_control_audit.jsonl")
LOW_RISK_ACTIONS = {
    "open_url",
    "open_path",
    "read_text_file",
    "view_image",
    "list_processes",
    "start_process",
    "type_text",
    "move_mouse",
    "set_volume",
    "media_key",
}
MEDIUM_RISK_ACTIONS = set()
HIGH_RISK_ACTIONS = {"kill_process", "run_command"}
ALLOWED_ACTIONS = LOW_RISK_ACTIONS | MEDIUM_RISK_ACTIONS | HIGH_RISK_ACTIONS
ACTION_FIELD_CANDIDATES = ("action", "type", "name", "tool")
ACTION_ALIASES = {
    "type": "type_text",
    "write": "type_text",
    "write_text": "type_text",
    "input_text": "type_text",
    "typewrite": "type_text",
    "mouse_move": "move_mouse",
    "move_cursor": "move_mouse",
    "cursor_move": "move_mouse",
    "open_notepad": "start_process",
    "abrir_bloco_de_notas": "start_process",
    "open_bloco_de_notas": "start_process",
    "start_notepad": "start_process",
    "volume_up": "set_volume",
    "increase_volume": "set_volume",
    "raise_volume": "set_volume",
    "volume_down": "set_volume",
    "decrease_volume": "set_volume",
    "lower_volume": "set_volume",
    "mute_volume": "set_volume",
}
NOTEPAD_ALIASES = {
    "open_notepad",
    "abrir_bloco_de_notas",
    "open_bloco_de_notas",
    "start_notepad",
}

VK_MEDIA = {
    "play_pause": 0xB3,
    "next": 0xB0,
    "previous": 0xB1,
    "stop": 0xB2,
}
VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF
KEYEVENTF_KEYUP = 0x0002
SW_RESTORE = 9

_LAST_STARTED_PROCESS: dict[str, Any] = {"pid": None, "target": "", "timestamp": 0.0}


@dataclass(frozen=True)
class PCActionRequest:
    action: str
    payload: dict[str, Any]
    risk: str
    summary: str


def get_pc_control_settings() -> dict:
    block = CONFIG.get("PC_CONTROL", {})
    if not isinstance(block, dict):
        block = {}
    block.setdefault("brave_path", "")
    CONFIG["PC_CONTROL"] = block
    return block


def _extract_action_name(payload: dict[str, Any]) -> tuple[str, str]:
    for field in ACTION_FIELD_CANDIDATES:
        candidate = str(payload.get(field) or "").strip().lower()
        if candidate:
            return candidate, field
    return "", ""


def _normalize_pc_action_payload(payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    raw_action, source_field = _extract_action_name(payload)
    normalized = dict(payload)
    action = ACTION_ALIASES.get(raw_action, raw_action)
    normalized["action"] = action

    if source_field and source_field != "action":
        normalized.pop(source_field, None)

    if raw_action in NOTEPAD_ALIASES:
        normalized.setdefault("command", "notepad.exe")

    if action == "type_text":
        for fallback_field in ("text", "value", "content", "message"):
            value = normalized.get(fallback_field)
            if value:
                normalized["text"] = str(value)
                break

    if action == "move_mouse":
        if normalized.get("dx") is None and normalized.get("delta_x") is not None:
            normalized["dx"] = normalized.get("delta_x")
        if normalized.get("dy") is None and normalized.get("delta_y") is not None:
            normalized["dy"] = normalized.get("delta_y")
        if normalized.get("distance") is None:
            for fallback_field in ("amount", "pixels", "offset", "delta"):
                value = normalized.get(fallback_field)
                if value is not None:
                    normalized["distance"] = value
                    break
        if not normalized.get("direction") and normalized.get("dir"):
            normalized["direction"] = normalized.get("dir")

    if action == "set_volume":
        normalized = _normalize_set_volume_payload(normalized, raw_action)

    return action, normalized


def _normalize_set_volume_payload(payload: dict[str, Any], raw_action: str) -> dict[str, Any]:
    normalized = dict(payload)

    if raw_action in {"volume_up", "increase_volume", "raise_volume"} and normalized.get("delta") is None:
        normalized["delta"] = 6
    if raw_action in {"volume_down", "decrease_volume", "lower_volume"} and normalized.get("delta") is None:
        normalized["delta"] = -6
    if raw_action in {"mute_volume"} and normalized.get("mute") is None:
        normalized["mute"] = True

    level = normalized.get("level")
    if isinstance(level, str):
        match = re.search(r"(-?\d{1,3})", level)
        if match:
            normalized["level"] = int(match.group(1))

    delta = normalized.get("delta")
    if isinstance(delta, str):
        match = re.search(r"(-?\d{1,3})", delta)
        if match:
            normalized["delta"] = int(match.group(1))

    if normalized.get("level") is not None or normalized.get("delta") is not None or normalized.get("mute") is not None:
        return normalized

    amount = normalized.get("amount")
    if amount is None:
        amount = normalized.get("step")
    if amount is None:
        amount = normalized.get("value")
    amount_value = None
    if amount is not None:
        try:
            amount_value = int(float(str(amount).replace("%", "").strip()))
        except (TypeError, ValueError):
            amount_value = None

    for candidate_field in ("direction", "mode", "operation", "intent", "query", "text", "instruction", "command", "value"):
        raw_value = normalized.get(candidate_field)
        if raw_value is None:
            continue
        lowered = str(raw_value).strip().lower()
        if not lowered:
            continue

        if re.search(r"(-?\d{1,3})\s*%", lowered):
            normalized["level"] = int(re.search(r"(-?\d{1,3})\s*%", lowered).group(1))
            return normalized

        if any(token in lowered for token in ("mute", "silenc", "mutar")):
            normalized["mute"] = True
            return normalized

        if any(token in lowered for token in ("down", "lower", "decrease", "quieter", "abaix", "diminu", "reduz", "menos volume")):
            normalized["delta"] = -abs(amount_value or 6)
            return normalized

        if any(token in lowered for token in ("up", "raise", "increase", "louder", "aument", "sobe", "mais volume")):
            normalized["delta"] = abs(amount_value or 6)
            return normalized

        if any(token in lowered for token in ("full volume", "volume total")) or re.search(r"\bmax(?:im[oa]?|imum)?\b", lowered):
            normalized["level"] = 100
            return normalized

        if any(token in lowered for token in ("zero volume", "sem volume")) or re.search(r"\bmin(?:im[oa]?|imum)?\b", lowered):
            normalized["level"] = 0
            return normalized

    return normalized


def parse_pc_action_payload(raw_payload: str | dict[str, Any]) -> PCActionRequest:
    payload = raw_payload
    if isinstance(raw_payload, str):
        try:
            payload = json.loads(raw_payload)
        except Exception as exc:
            raise ValueError(f"JSON invalido em <acao_pc>: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError("O payload de <acao_pc> precisa ser um objeto JSON.")

    action, normalized = _normalize_pc_action_payload(payload)
    if action not in ALLOWED_ACTIONS:
        raise ValueError(f"Acao de PC nao suportada: {action or '(vazia)'}")

    return PCActionRequest(
        action=action,
        payload=normalized,
        risk=get_action_risk(action),
        summary=summarize_pc_action(normalized),
    )


def get_action_risk(action: str) -> str:
    if action in HIGH_RISK_ACTIONS:
        return "alto"
    if action in MEDIUM_RISK_ACTIONS:
        return "medio"
    return "baixo"


def summarize_pc_action(payload: dict[str, Any]) -> str:
    action = str(payload.get("action") or "").strip().lower()
    if action == "open_url":
        return f"Abrir URL: {payload.get('url', '')}"
    if action == "open_path":
        return f"Abrir caminho: {payload.get('path', '')}"
    if action == "read_text_file":
        return f"Ler arquivo: {payload.get('path', '')}"
    if action == "view_image":
        return f"Abrir imagem: {payload.get('path', '')}"
    if action == "list_processes":
        query = str(payload.get("query") or "").strip()
        return f"Listar processos{' com filtro ' + query if query else ''}"
    if action == "start_process":
        return f"Iniciar processo: {payload.get('path') or payload.get('command') or ''}"
    if action == "kill_process":
        target = payload.get("pid") or payload.get("name") or ""
        return f"Encerrar processo: {target}"
    if action == "run_command":
        return f"Executar comando: {payload.get('command', '')}"
    if action == "type_text":
        text = str(payload.get("text") or "")
        preview = text[:80] + ("..." if len(text) > 80 else "")
        return f"Digitar texto: {preview}"
    if action == "move_mouse":
        if payload.get("x") is not None and payload.get("y") is not None:
            return f"Mover mouse para ({payload.get('x')}, {payload.get('y')})"
        if payload.get("dx") is not None or payload.get("dy") is not None:
            return f"Mover mouse relativamente por dx={payload.get('dx', 0)}, dy={payload.get('dy', 0)}"
        direction = str(payload.get("direction") or "").strip().lower()
        if direction:
            return f"Mover mouse para {direction} por {payload.get('distance', 120)}px"
        return f"Mover mouse para ({payload.get('x')}, {payload.get('y')})"
    if action == "set_volume":
        if payload.get("mute") is not None:
            return "Alternar mute do sistema"
        if payload.get("level") is not None:
            return f"Ajustar volume para {payload.get('level')}%"
        return f"Ajustar volume por delta {payload.get('delta')}"
    if action == "media_key":
        return f"Enviar tecla de midia: {payload.get('key', '')}"
    return f"Acao de PC: {action}"


def append_pc_action_audit(entry: dict[str, Any]):
    os.makedirs(os.path.dirname(AUDIT_LOG_PATH), exist_ok=True)
    payload = dict(entry)
    payload.setdefault("timestamp", time.strftime("%Y-%m-%d %H:%M:%S"))
    with open(AUDIT_LOG_PATH, "a", encoding="utf-8") as file:
        file.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _remember_started_process(pid: int | None, target: str):
    _LAST_STARTED_PROCESS["pid"] = int(pid) if pid else None
    _LAST_STARTED_PROCESS["target"] = str(target or "")
    _LAST_STARTED_PROCESS["timestamp"] = time.time()


def _get_cursor_pos() -> tuple[int, int]:
    point = wintypes.POINT()
    if not ctypes.windll.user32.GetCursorPos(ctypes.byref(point)):
        raise ctypes.WinError()
    return int(point.x), int(point.y)


def _iter_visible_windows() -> list[tuple[int, int, str]]:
    windows: list[tuple[int, int, str]] = []
    user32 = ctypes.windll.user32

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def _callback(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        title_buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, title_buffer, length + 1)
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        windows.append((int(hwnd), int(pid.value), title_buffer.value))
        return True

    user32.EnumWindows(_callback, 0)
    return windows


def _find_window_handle(*, pid: int | None = None, process_name: str = "", title_contains: str = "") -> int | None:
    process_name = process_name.strip().lower()
    title_contains = title_contains.strip().lower()
    for hwnd, window_pid, title in _iter_visible_windows():
        if pid is not None and window_pid != int(pid):
            continue
        if title_contains and title_contains not in title.lower():
            continue
        if process_name:
            try:
                current_name = psutil.Process(window_pid).name().lower()
            except Exception:
                continue
            if current_name != process_name:
                continue
        return hwnd
    return None


def _focus_window_handle(hwnd: int | None) -> bool:
    if not hwnd:
        return False
    user32 = ctypes.windll.user32
    user32.ShowWindow(hwnd, SW_RESTORE)
    user32.BringWindowToTop(hwnd)
    user32.SetForegroundWindow(hwnd)
    return int(user32.GetForegroundWindow()) == int(hwnd)


def _focus_window_for_payload(payload: dict[str, Any]) -> bool:
    pid = payload.get("pid") or _LAST_STARTED_PROCESS.get("pid")
    title = str(payload.get("window_title") or payload.get("title") or "").strip()
    process_name = str(payload.get("process_name") or "").strip().lower()

    hwnd = None
    if pid is not None:
        hwnd = _find_window_handle(pid=int(pid), title_contains=title)
    if hwnd is None and process_name:
        hwnd = _find_window_handle(process_name=process_name, title_contains=title)
    if hwnd is None and title:
        hwnd = _find_window_handle(title_contains=title)
    if hwnd is None and _LAST_STARTED_PROCESS.get("pid"):
        hwnd = _find_window_handle(pid=int(_LAST_STARTED_PROCESS["pid"]))

    return _focus_window_handle(hwnd)


def confirm_pc_action(request: PCActionRequest) -> bool:
    return confirm_pc_action_popup(
        title="Confirmar ação no PC",
        body=request.summary,
        risk_label=request.risk,
        timeout_seconds=15,
        parent=None,
    )


def execute_pc_action(
    raw_payload: str | dict[str, Any],
    *,
    confirm_callback: Callable[[PCActionRequest], bool] | None = None,
) -> dict[str, Any]:
    request = parse_pc_action_payload(raw_payload)
    confirm_callback = confirm_callback or confirm_pc_action

    if request.risk in {"medio", "alto"}:
        allowed = bool(confirm_callback(request))
        append_pc_action_audit(
            {
                "action": request.action,
                "risk": request.risk,
                "decision": "allowed" if allowed else "denied",
                "summary": request.summary,
            }
        )
        if not allowed:
            return {
                "ok": False,
                "status": "denied",
                "action": request.action,
                "risk": request.risk,
                "summary": request.summary,
                "message": "Ação negada pelo usuário.",
            }

    try:
        result = _dispatch_pc_action(request)
        append_pc_action_audit(
            {
                "action": request.action,
                "risk": request.risk,
                "decision": "executed",
                "summary": request.summary,
                "details": result,
            }
        )
        return {
            "ok": True,
            "status": "executed",
            "action": request.action,
            "risk": request.risk,
            "summary": request.summary,
            **result,
        }
    except Exception as exc:
        logger.exception("[PC CONTROL] Falha ao executar %s", request.action)
        append_pc_action_audit(
            {
                "action": request.action,
                "risk": request.risk,
                "decision": "failed",
                "summary": request.summary,
                "error": str(exc),
            }
        )
        return {
            "ok": False,
            "status": "failed",
            "action": request.action,
            "risk": request.risk,
            "summary": request.summary,
            "message": str(exc),
        }


def _dispatch_pc_action(request: PCActionRequest) -> dict[str, Any]:
    action = request.action
    payload = request.payload

    if action == "open_url":
        return _open_url(payload)
    if action == "open_path":
        return _open_path(payload)
    if action == "read_text_file":
        return _read_text_file(payload)
    if action == "view_image":
        return _view_image(payload)
    if action == "list_processes":
        return _list_processes(payload)
    if action == "start_process":
        return _start_process(payload)
    if action == "kill_process":
        return _kill_process(payload)
    if action == "run_command":
        return _run_command(payload)
    if action == "type_text":
        return _type_text(payload)
    if action == "move_mouse":
        return _move_mouse(payload)
    if action == "set_volume":
        return _set_volume(payload)
    if action == "media_key":
        return _media_key(payload)
    raise RuntimeError(f"Ação não implementada: {action}")


def _require_path(payload: dict[str, Any], field: str = "path") -> str:
    path = os.path.abspath(str(payload.get(field) or "").strip())
    if not path:
        raise ValueError(f"O campo '{field}' é obrigatório.")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Caminho não encontrado: {path}")
    return path


def _open_url(payload: dict[str, Any]) -> dict[str, Any]:
    url = str(payload.get("url") or "").strip()
    if not url.startswith(("http://", "https://")):
        raise ValueError("A URL precisa começar com http:// ou https://")

    brave_path = str(get_pc_control_settings().get("brave_path") or "").strip()
    if brave_path and os.path.exists(brave_path):
        subprocess.Popen([brave_path, url])
        return {"message": f"URL aberta no Brave: {url}", "target": url}

    webbrowser.open(url)
    return {"message": f"URL aberta: {url}", "target": url}


def _open_path(payload: dict[str, Any]) -> dict[str, Any]:
    path = _require_path(payload)
    os.startfile(path)
    return {"message": f"Caminho aberto: {path}", "target": path}


def _read_text_file(payload: dict[str, Any]) -> dict[str, Any]:
    path = _require_path(payload)
    max_chars = int(payload.get("max_chars") or 4000)
    ext = os.path.splitext(path)[1].lower()
    inbox = InboxManager()
    if ext == ".pdf":
        content = inbox.read_pdf(path, max_chars=max_chars)
    else:
        content = inbox.read_text_like(path, max_chars=max_chars)
    return {
        "message": f"Arquivo lido: {path}",
        "target": path,
        "content": content,
    }


def _view_image(payload: dict[str, Any]) -> dict[str, Any]:
    path = _require_path(payload)
    os.startfile(path)
    return {"message": f"Imagem aberta: {path}", "target": path}


def _list_processes(payload: dict[str, Any]) -> dict[str, Any]:
    query = str(payload.get("query") or "").strip().lower()
    limit = max(1, min(int(payload.get("limit") or 25), 100))
    rows = []
    for proc in psutil.process_iter(["pid", "name"]):
        name = str(proc.info.get("name") or "")
        if query and query not in name.lower():
            continue
        rows.append({"pid": proc.info.get("pid"), "name": name})
        if len(rows) >= limit:
            break

    content = "\n".join([f"{row['pid']} - {row['name']}" for row in rows]) or "(nenhum processo encontrado)"
    return {
        "message": f"{len(rows)} processo(s) listado(s).",
        "content": content,
        "count": len(rows),
    }


def _start_process(payload: dict[str, Any]) -> dict[str, Any]:
    args = payload.get("args") or []
    cwd = str(payload.get("cwd") or "").strip() or None

    if payload.get("path"):
        path = str(payload.get("path")).strip()
        if not os.path.exists(path):
            raise FileNotFoundError(f"Executável não encontrado: {path}")
        if not isinstance(args, list):
            raise ValueError("O campo 'args' precisa ser uma lista.")
        proc = subprocess.Popen([path, *[str(item) for item in args]], cwd=cwd)
        target = path
    else:
        command = payload.get("command")
        if not command:
            raise ValueError("Use 'path' ou 'command' para iniciar processo.")
        if isinstance(command, list):
            proc = subprocess.Popen([str(item) for item in command], cwd=cwd)
        else:
            proc = subprocess.Popen(str(command), cwd=cwd, shell=True)
        target = str(command)

    _remember_started_process(proc.pid, target)
    focus_requested = payload.get("focus_window", True)
    focus_ok = False
    if focus_requested:
        for _ in range(20):
            time.sleep(0.15)
            if _focus_window_handle(_find_window_handle(pid=proc.pid)):
                focus_ok = True
                break

    return {
        "message": f"Processo iniciado: {target}",
        "target": target,
        "pid": proc.pid,
        "window_focused": focus_ok,
    }


def _kill_process(payload: dict[str, Any]) -> dict[str, Any]:
    pid = payload.get("pid")
    name = str(payload.get("name") or "").strip().lower()

    if pid is not None:
        proc = psutil.Process(int(pid))
    elif name:
        matches = [proc for proc in psutil.process_iter(["pid", "name"]) if str(proc.info.get("name") or "").lower() == name]
        if not matches:
            raise RuntimeError(f"Nenhum processo encontrado com nome exato: {name}")
        if len(matches) > 1:
            raise RuntimeError(f"Mais de um processo com nome '{name}'. Informe o PID.")
        proc = psutil.Process(matches[0].info["pid"])
    else:
        raise ValueError("Informe 'pid' ou 'name' para encerrar processo.")

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except psutil.TimeoutExpired:
        proc.kill()
    return {
        "message": f"Processo encerrado: {proc.pid}",
        "pid": proc.pid,
        "target": proc.name(),
    }


def _run_command(payload: dict[str, Any]) -> dict[str, Any]:
    command = payload.get("command")
    if not command:
        raise ValueError("O campo 'command' é obrigatório.")

    cwd = str(payload.get("cwd") or "").strip() or None
    timeout_seconds = max(1, min(int(payload.get("timeout") or 20), 60))

    if isinstance(command, list):
        completed = subprocess.run(
            [str(item) for item in command],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
        )
        command_text = " ".join([str(item) for item in command])
    else:
        command_text = str(command)
        completed = subprocess.run(
            command_text,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=True,
        )

    stdout = (completed.stdout or "").strip()
    stderr = (completed.stderr or "").strip()
    return {
        "message": f"Comando executado com código {completed.returncode}.",
        "target": command_text,
        "returncode": completed.returncode,
        "stdout": stdout[:4000],
        "stderr": stderr[:2000],
    }


def _type_text(payload: dict[str, Any]) -> dict[str, Any]:
    if keyboard is None:
        raise RuntimeError("Biblioteca 'keyboard' não está disponível para digitação automatizada.")
    text = str(payload.get("text") or "")
    if not text:
        raise ValueError("O campo 'text' é obrigatório para type_text.")
    delay = float(payload.get("delay") or 0)
    focus_ok = _focus_window_for_payload(payload)
    focus_delay = max(0.0, min(float(payload.get("focus_delay") or 0.35), 3.0))
    if focus_delay:
        time.sleep(focus_delay)
    keyboard.write(text, delay=delay)
    if payload.get("press_enter"):
        keyboard.press_and_release("enter")
    return {
        "message": "Texto digitado no sistema.",
        "chars": len(text),
        "window_focused": focus_ok,
    }


def _move_mouse(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("x") is not None and payload.get("y") is not None:
        x_pos = int(payload["x"])
        y_pos = int(payload["y"])
    else:
        current_x, current_y = _get_cursor_pos()
        if payload.get("dx") is not None or payload.get("dy") is not None:
            dx = int(payload.get("dx") or 0)
            dy = int(payload.get("dy") or 0)
        else:
            direction = str(payload.get("direction") or "").strip().lower()
            distance = int(payload.get("distance") or 120)
            direction_map = {
                "right": (distance, 0),
                "left": (-distance, 0),
                "up": (0, -distance),
                "down": (0, distance),
                "upright": (distance, -distance),
                "up_right": (distance, -distance),
                "upleft": (-distance, -distance),
                "up_left": (-distance, -distance),
                "downright": (distance, distance),
                "down_right": (distance, distance),
                "downleft": (-distance, distance),
                "down_left": (-distance, distance),
            }
            if direction not in direction_map:
                raise ValueError("Use 'x'/'y', 'dx'/'dy' ou 'direction'/'distance' para move_mouse.")
            dx, dy = direction_map[direction]
        x_pos = current_x + dx
        y_pos = current_y + dy
    ctypes.windll.user32.SetCursorPos(x_pos, y_pos)
    return {
        "message": f"Mouse movido para ({x_pos}, {y_pos}).",
        "x": x_pos,
        "y": y_pos,
    }


def _send_vk(vk_code: int, count: int = 1):
    for _ in range(max(1, count)):
        ctypes.windll.user32.keybd_event(vk_code, 0, 0, 0)
        ctypes.windll.user32.keybd_event(vk_code, 0, KEYEVENTF_KEYUP, 0)


def _set_volume(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("mute") is not None:
        _send_vk(VK_VOLUME_MUTE)
        return {"message": "Mute alternado."}

    if payload.get("level") is not None:
        level = max(0, min(int(payload["level"]), 100))
        _send_vk(VK_VOLUME_DOWN, 60)
        _send_vk(VK_VOLUME_UP, round(level / 2))
        return {"message": f"Volume aproximado ajustado para {level}%."}

    if payload.get("delta") is None:
        raise ValueError("Use 'level', 'delta' ou 'mute' em set_volume.")

    delta = int(payload["delta"])
    if delta > 0:
        _send_vk(VK_VOLUME_UP, min(abs(delta), 20))
    elif delta < 0:
        _send_vk(VK_VOLUME_DOWN, min(abs(delta), 20))
    return {"message": f"Volume ajustado por delta {delta}."}


def _media_key(payload: dict[str, Any]) -> dict[str, Any]:
    key = str(payload.get("key") or "").strip().lower()
    vk_code = VK_MEDIA.get(key)
    if vk_code is None:
        raise ValueError("Use media_key com 'play_pause', 'next', 'previous' ou 'stop'.")
    _send_vk(vk_code)
    return {"message": f"Tecla de mídia enviada: {key}.", "target": key}
