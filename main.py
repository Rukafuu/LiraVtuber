"""
Supervisor local LiraVT.

Uso:
  python main.py              # stack completa
  python main.py backend-only # API + WhatsApp + bridge
  python main.py api-only     # so Control API
  python main.py frontend-only
  python main.py healthcheck
  python main.py status

VTuber (voz/terminal): python apps/vtuber/main.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env", encoding="utf-8-sig")

CONTROL_URL = "http://127.0.0.1:" + os.getenv("CONTROL_API_PORT", "8042")
WHATSAPP_URL = os.getenv("WHATSAPP_API_URL", "http://127.0.0.1:8043").rstrip("/")
MCP_URL = os.getenv("MCP_GATEWAY_URL", "http://127.0.0.1:8045").rstrip("/")
FRONTEND_DIR = ROOT / "control_panel"
BACKEND_SERVICES = ("whatsapp_api", "whatsapp_bridge")


def _probe(url: str, timeout: float = 2.0) -> bool:
    try:
        with urlopen(url, timeout=timeout) as resp:
            return 200 <= resp.status < 300
    except (URLError, TimeoutError, OSError, ValueError):
        return False


def _start_backend_services() -> list[str]:
    from apps.control_api.service_manager import service_manager

    started: list[str] = []
    for service_id in BACKEND_SERVICES:
        result = service_manager.start(service_id)
        if result.get("status") == "ok":
            print(f"[SERVICES] {service_id}: OK (PID {result.get('pid')})", flush=True)
            started.append(service_id)
        else:
            print(
                f"[SERVICES] {service_id}: AVISO — {result.get('message')}",
                flush=True,
            )
    return started


def _stop_backend_services(service_ids: list[str]) -> None:
    if not service_ids:
        return
    from apps.control_api.service_manager import service_manager

    for service_id in service_ids:
        result = service_manager.stop(service_id)
        print(f"[SERVICES] {service_id}: {result.get('status')}", flush=True)


def _run_control_api() -> None:
    from apps.control_api.server import start_server

    host = os.getenv("CONTROL_API_HOST", "0.0.0.0")
    port = int(os.getenv("CONTROL_API_PORT", "8042"))
    start_server(host=host, port=port)


def _run_frontend() -> int:
    if not (FRONTEND_DIR / "package.json").is_file():
        print(f"[FRONTEND] {FRONTEND_DIR} sem package.json.", file=sys.stderr, flush=True)
        return 1
    npm = "npm.cmd" if os.name == "nt" else "npm"
    print("[FRONTEND] npm run tauri dev (Vite 1425 + janela Tauri)", flush=True)
    return subprocess.call([npm, "run", "tauri", "dev"], cwd=FRONTEND_DIR)


def _healthcheck() -> int:
    checks = {
        "control_api": CONTROL_URL + "/api/health",
        "whatsapp_api": WHATSAPP_URL + "/health",
        "mcp_gateway": MCP_URL + "/health",
    }
    all_up = True
    for name, url in checks.items():
        up = _probe(url)
        all_up = all_up and up
        print(f"[{'UP' if up else 'DOWN'}] {name}: {url}", flush=True)
    return 0 if all_up else 1


def _status() -> int:
    from apps.control_api.service_manager import service_manager

    print(json.dumps(service_manager.status_all(), ensure_ascii=False, indent=2))
    return 0


def _stack() -> int:
    started = _start_backend_services()
    api = threading.Thread(target=_run_control_api, name="control-api", daemon=True)
    api.start()
    for _ in range(30):
        if _probe(CONTROL_URL + "/api/health"):
            print(f"[CONTROL API] UP em {CONTROL_URL}", flush=True)
            break
        time.sleep(1)
    try:
        return _run_frontend()
    finally:
        _stop_backend_services(started)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    mode = args[0] if args else "stack"

    if mode in ("stack", "all"):
        return _stack()
    if mode == "backend-only":
        started = _start_backend_services()
        try:
            _run_control_api()
        finally:
            _stop_backend_services(started)
        return 0
    if mode == "api-only":
        _run_control_api()
        return 0
    if mode == "frontend-only":
        return _run_frontend()
    if mode == "healthcheck":
        return _healthcheck()
    if mode == "status":
        return _status()

    print(f"Modo desconhecido: {mode}", file=sys.stderr)
    print(__doc__.strip(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
