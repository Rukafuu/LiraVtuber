"""Gerenciamento de processos Discord / WhatsApp para o Control Center."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

import psutil

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
SERVICE_LOG_DIR = ROOT / "data" / "logs" / "services"
WHATSAPP_BRIDGE_DIR = ROOT / "whatsapp_bridge"
QR_FILE = WHATSAPP_BRIDGE_DIR / "qr.txt"
QR_META_FILE = WHATSAPP_BRIDGE_DIR / "qr_meta.json"
PAIRING_FILE = WHATSAPP_BRIDGE_DIR / "pairing_code.txt"
BRIDGE_STATUS_FILE = WHATSAPP_BRIDGE_DIR / "bridge_status.json"
AUTH_DIR = WHATSAPP_BRIDGE_DIR / "auth_info_baileys"


@dataclass
class ServiceSpec:
    id: str
    label: str
    command: list[str]
    cwd: Path = ROOT
    health_url: str | None = None
    online_markers: tuple[str, ...] = ()
    error_markers: tuple[str, ...] = ()
    warn_markers: tuple[str, ...] = ()
    process_hint: str = ""


@dataclass
class ManagedProcess:
    spec: ServiceSpec
    process: subprocess.Popen | None = None
    logs: deque = field(default_factory=lambda: deque(maxlen=300))
    started_at: float | None = None
    last_error: str | None = None
    connection_hint: str | None = None
    exit_code: int | None = None
    log_path: Path | None = None
    _log_offset: int = 0

    def append_log(self, line: str, stream: str = "stdout"):
        text = line.rstrip("\r\n")
        if not text:
            return
        entry = {"ts": time.strftime("%H:%M:%S"), "stream": stream, "line": text}
        self.logs.append(entry)
        for marker in self.spec.error_markers:
            if marker in text:
                self.last_error = text
                break
        for marker in self.spec.online_markers:
            if marker in text:
                self.connection_hint = "connected"
                self.last_error = None
                break
        for marker in self.spec.warn_markers:
            if marker in text:
                if "QR" in marker or "Escaneie" in text:
                    self.connection_hint = "awaiting_qr"
                elif "PAIRING" in marker or "CÓDIGO" in text:
                    self.connection_hint = "awaiting_pairing"
                else:
                    self.connection_hint = "connecting"


SERVICES: dict[str, ServiceSpec] = {
    "discord": ServiceSpec(
        id="discord",
        label="Discord Bot",
        command=[sys.executable, "-u", "src/modules/discord_bot.py"],
        online_markers=("[DISCORD] ✦ Online como",),
        error_markers=(
            "[DISCORD] ❌",
            "DISCORD_TOKEN não encontrado",
            "Improper token",
            "LoginFailure",
        ),
        process_hint="discord_bot",
    ),
    "whatsapp_api": ServiceSpec(
        id="whatsapp_api",
        label="WhatsApp API",
        command=[sys.executable, "-u", "apps/whatsapp_api/main.py"],
        health_url=os.getenv("WHATSAPP_API_URL", "http://127.0.0.1:8043").rstrip("/") + "/health",
        error_markers=("[ERROR]", "Traceback", "Address already in use"),
        process_hint="whatsapp_api",
    ),
    "whatsapp_bridge": ServiceSpec(
        id="whatsapp_bridge",
        label="WhatsApp Bridge (Baileys)",
        command=["node", "index.js"],
        cwd=ROOT / "whatsapp_bridge",
        online_markers=("ONLINE no WhatsApp",),
        error_markers=("Error:", "ENOENT", "Cannot find module"),
        warn_markers=("Escaneie o QR", "PAIRING", "CÓDIGO É"),
        process_hint="whatsapp_bridge",
    ),
    "mcp_gateway": ServiceSpec(
        id="mcp_gateway",
        label="MCP Gateway",
        command=[sys.executable, "-u", "apps/mcp_gateway/main.py"],
        health_url=os.getenv("MCP_GATEWAY_URL", "http://127.0.0.1:8045").rstrip("/") + "/health",
        online_markers=("[MCP Gateway]", "Application startup complete"),
        error_markers=("Traceback", "Address already in use", "Error:"),
        process_hint="mcp_gateway/main.py",
    ),
}


class ServiceManager:
    def __init__(self):
        self._lock = threading.RLock()
        self._managed: dict[str, ManagedProcess] = {
            sid: ManagedProcess(spec=spec) for sid, spec in SERVICES.items()
        }
        self._reattach_from_pid_files()

    def _pid_file(self, service_id: str) -> Path:
        return SERVICE_LOG_DIR / f"{service_id}.pid"

    def _write_pid_file(self, service_id: str, pid: int):
        SERVICE_LOG_DIR.mkdir(parents=True, exist_ok=True)
        self._pid_file(service_id).write_text(str(pid), encoding="utf-8")

    def _clear_pid_file(self, service_id: str):
        try:
            self._pid_file(service_id).unlink(missing_ok=True)
        except OSError:
            pass

    def _reattach_from_pid_files(self):
        """Se a Control API reiniciar, reconecta a processos ainda vivos."""
        for sid, mp in self._managed.items():
            path = self._pid_file(sid)
            if not path.is_file():
                continue
            try:
                pid = int(path.read_text(encoding="utf-8").strip())
                if psutil.pid_exists(pid):
                    proc = psutil.Process(pid)
                    cmd = " ".join(proc.cmdline()).lower().replace("\\", "/")
                    if mp.spec.process_hint.lower() in cmd:
                        mp.started_at = proc.create_time()
                        mp.connection_hint = mp.connection_hint or "starting"
                        logger.info("[SERVICES] Reanexado %s PID %s", sid, pid)
            except (ValueError, psutil.NoSuchProcess, psutil.AccessDenied):
                self._clear_pid_file(sid)

    def _log_file(self, service_id: str) -> Path:
        SERVICE_LOG_DIR.mkdir(parents=True, exist_ok=True)
        return SERVICE_LOG_DIR / f"{service_id}.log"

    def _find_external_pid(self, spec: ServiceSpec) -> int | None:
        hint = spec.process_hint.lower()
        for proc in psutil.process_iter(["pid", "cmdline"]):
            try:
                cmdline = proc.info.get("cmdline") or []
                joined = " ".join(cmdline).lower().replace("\\", "/")
                if hint and hint in joined:
                    return proc.info["pid"]
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return None

    def _probe_http(self, url: str, timeout: float = 1.5) -> bool:
        try:
            with urlopen(url, timeout=timeout) as resp:
                return 200 <= resp.status < 300
        except (URLError, TimeoutError, OSError, ValueError):
            return False

    def _pid_alive(self, pid: int, spec: ServiceSpec) -> bool:
        try:
            if not psutil.pid_exists(pid):
                return False
            proc = psutil.Process(pid)
            cmd = " ".join(proc.cmdline()).lower().replace("\\", "/")
            return spec.process_hint.lower() in cmd
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    def _managed_pid(self, mp: ManagedProcess) -> int | None:
        if mp.process and self._process_alive(mp):
            return mp.process.pid
        path = self._pid_file(mp.spec.id)
        if path.is_file():
            try:
                pid = int(path.read_text(encoding="utf-8").strip())
                if self._pid_alive(pid, mp.spec):
                    return pid
            except ValueError:
                pass
        return None

    def _process_alive(self, mp: ManagedProcess) -> bool:
        proc = mp.process
        if proc is not None:
            code = proc.poll()
            if code is None:
                return True
            mp.exit_code = code
            if code != 0 and not mp.last_error:
                mp.last_error = f"Processo encerrou com código {code}"
            mp.process = None
            self._clear_pid_file(mp.spec.id)
            return False
        pid = self._managed_pid(mp)
        if pid is not None:
            return True
        return False

    def _tail_log_lines(self, path: Path, limit: int = 25) -> list[dict]:
        if not path.is_file():
            return []
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                lines = fh.readlines()
        except OSError:
            return []
        out = []
        for line in lines[-limit:]:
            text = line.rstrip("\r\n")
            if not text:
                continue
            out.append({"ts": "", "stream": "file", "line": text})
        return out

    def _scan_log_markers(self, mp: ManagedProcess):
        """Atualiza connection/erro a partir das novas linhas do arquivo de log."""
        path = mp.log_path or self._log_file(mp.spec.id)
        if not path.is_file():
            return
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                fh.seek(mp._log_offset)
                for line in fh:
                    mp.append_log(line, "file")
                mp._log_offset = fh.tell()
        except OSError:
            pass

    def start(self, service_id: str) -> dict[str, Any]:
        with self._lock:
            if service_id not in self._managed:
                return {"status": "error", "message": f"Serviço desconhecido: {service_id}"}
            mp = self._managed[service_id]
            if self._process_alive(mp):
                return {"status": "ok", "message": "Já em execução (gerenciado pelo painel)."}
            if self._find_external_pid(mp.spec):
                return {
                    "status": "error",
                    "message": "Processo já está rodando fora do painel. Pare-o manualmente antes de iniciar aqui.",
                }
            if mp.spec.health_url and self._probe_http(mp.spec.health_url):
                return {
                    "status": "error",
                    "message": "Serviço já responde na porta (instância externa). Pare-a antes de iniciar aqui.",
                }

            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            if service_id in ("discord", "whatsapp_api"):
                env.setdefault("LIRA_RAG_CHROMA", "0")
            creationflags = 0
            if sys.platform == "win32":
                creationflags = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]

            try:
                log_path = self._log_file(service_id)
                mp.log_path = log_path
                banner = (
                    f"\n=== [{time.strftime('%Y-%m-%d %H:%M:%S')}] "
                    f"Inicio via Control Center ===\n"
                )
                with open(log_path, "a", encoding="utf-8") as banner_fh:
                    banner_fh.write(banner)
                mp._log_offset = log_path.stat().st_size

                # Filho abre o log sozinho — evita o pai fechar o handle no Windows
                log_handle = open(log_path, "a", encoding="utf-8", buffering=1)
                mp.process = subprocess.Popen(
                    mp.spec.command,
                    cwd=str(mp.spec.cwd),
                    env=env,
                    stdout=log_handle,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                    creationflags=creationflags,
                )
                log_handle.close()
                mp.exit_code = None
                self._write_pid_file(service_id, mp.process.pid)
                mp.started_at = time.time()
                mp.last_error = None
                mp.connection_hint = "starting"
                mp.append_log(
                    f"[PAINEL] Iniciado PID {mp.process.pid}: {' '.join(mp.spec.command)}",
                    "system",
                )
                mp.append_log(f"[PAINEL] Log: {log_path}", "system")
                return {"status": "ok", "pid": mp.process.pid, "log_file": str(log_path)}
            except Exception as e:
                mp.last_error = str(e)
                return {"status": "error", "message": str(e)}

    def _kill_process_tree(self, pid: int):
        try:
            parent = psutil.Process(pid)
            children = parent.children(recursive=True)
            for child in children:
                try:
                    child.terminate()
                except psutil.Error:
                    pass
            parent.terminate()
            gone, alive = psutil.wait_procs([parent, *children], timeout=5)
            for p in alive:
                try:
                    p.kill()
                except psutil.Error:
                    pass
        except psutil.NoSuchProcess:
            pass

    def stop(self, service_id: str) -> dict[str, Any]:
        with self._lock:
            if service_id not in self._managed:
                return {"status": "error", "message": f"Serviço desconhecido: {service_id}"}
            mp = self._managed[service_id]
            pid = self._managed_pid(mp)
            if pid:
                self._kill_process_tree(pid)
                mp.append_log(f"[PAINEL] Parado PID {pid}", "system")
                mp.process = None
                mp.started_at = None
                mp.connection_hint = None
                self._clear_pid_file(service_id)
                return {"status": "ok"}
            mp.process = None
            mp.started_at = None
            self._clear_pid_file(service_id)
            external = self._find_external_pid(mp.spec)
            if external:
                return {
                    "status": "error",
                    "message": f"Rodando fora do painel (PID {external}). Encerre manualmente.",
                }
            return {"status": "ok", "message": "Já estava parado."}

    def _resolve_state(self, mp: ManagedProcess) -> dict[str, Any]:
        spec = mp.spec
        self._scan_log_markers(mp)
        managed = self._process_alive(mp)
        pid = self._managed_pid(mp) if managed else None
        external_pid = None if managed else self._find_external_pid(spec)
        reattached = managed and mp.process is None and pid is not None

        http_ok: bool | None = None
        if spec.health_url and (managed or external_pid):
            http_ok = self._probe_http(spec.health_url)
        uptime = None
        if managed and mp.started_at:
            uptime = int(time.time() - mp.started_at)

        if managed:
            run_state = "running"
            if spec.health_url and http_ok is False:
                run_state = "starting" if uptime and uptime < 90 else "degraded"
            elif spec.online_markers and mp.connection_hint == "connected":
                run_state = "running"
            elif spec.online_markers and mp.connection_hint in ("awaiting_qr", "awaiting_pairing", "connecting"):
                run_state = "degraded"
            elif spec.online_markers and uptime and uptime < 120:
                run_state = "starting"
        elif external_pid or http_ok is True:
            run_state = "running"
            pid = external_pid or pid
        else:
            run_state = "stopped"
            if mp.exit_code not in (None, 0) or mp.last_error:
                run_state = "error"
            elif self._tail_log_lines(mp.log_path or self._log_file(spec.id), 5):
                last_lines = " ".join(
                    e["line"] for e in self._tail_log_lines(mp.log_path or self._log_file(spec.id), 8)
                )
                if any(m in last_lines for m in spec.error_markers):
                    run_state = "error"

        log_tail = self._tail_log_lines(mp.log_path or self._log_file(spec.id), 25)
        return {
            "id": spec.id,
            "label": spec.label,
            "state": run_state,
            "managed": managed,
            "reattached": reattached,
            "external": bool(external_pid and not managed),
            "pid": pid,
            "exit_code": mp.exit_code,
            "uptime_sec": uptime,
            "health_http": http_ok if spec.health_url else None,
            "connection": mp.connection_hint,
            "last_error": mp.last_error,
            "log_tail": log_tail,
            "log_file": str(mp.log_path or self._log_file(spec.id)),
            "command": spec.command,
            "cwd": str(spec.cwd),
        }

    def status_all(self) -> dict[str, Any]:
        with self._lock:
            items = [self._resolve_state(mp) for mp in self._managed.values()]
            return {"services": items, "updated_at": time.time()}

    def status_one(self, service_id: str) -> dict[str, Any] | None:
        with self._lock:
            mp = self._managed.get(service_id)
            if not mp:
                return None
            return self._resolve_state(mp)

    def logs(self, service_id: str, limit: int = 80) -> list[dict]:
        with self._lock:
            mp = self._managed.get(service_id)
            if not mp:
                return []
            return list(mp.logs)[-limit:]

    def reset_whatsapp_session(self) -> dict[str, Any]:
        """Para o bridge, apaga credenciais Baileys e artefatos de QR/pareamento."""
        import shutil

        self.stop("whatsapp_bridge")
        time.sleep(0.5)

        removed_auth = False
        if AUTH_DIR.is_dir():
            try:
                shutil.rmtree(AUTH_DIR)
                removed_auth = True
            except OSError as e:
                return {"status": "error", "message": f"Não foi possível apagar sessão: {e}"}

        for path in (QR_FILE, QR_META_FILE, PAIRING_FILE, BRIDGE_STATUS_FILE):
            try:
                if path.is_file():
                    path.unlink()
            except OSError:
                pass

        mp = self._managed.get("whatsapp_bridge")
        if mp:
            mp.connection_hint = None
            mp.last_error = None

        return {
            "status": "ok",
            "message": "Sessão WhatsApp limpa. Inicie a stack WhatsApp e escaneie um QR novo.",
            "auth_removed": removed_auth,
        }

    def whatsapp_session(self) -> dict[str, Any]:
        """QR e pareamento dinâmicos (lidos de whatsapp_bridge/)."""
        bridge = self.status_one("whatsapp_bridge") or {}
        connection = bridge.get("connection")
        connected = connection == "connected"

        bridge_status: dict[str, Any] = {}
        if BRIDGE_STATUS_FILE.is_file():
            try:
                bridge_status = json.loads(
                    BRIDGE_STATUS_FILE.read_text(encoding="utf-8")
                )
            except (json.JSONDecodeError, OSError):
                pass

        qr: dict[str, Any] = {
            "available": False,
            "revision": 0,
            "payload": None,
            "updated_at": None,
        }
        pairing_code: str | None = None

        if not connected:
            if PAIRING_FILE.is_file():
                try:
                    pairing_code = PAIRING_FILE.read_text(encoding="utf-8").strip() or None
                except OSError:
                    pass

            if QR_FILE.is_file():
                try:
                    payload = QR_FILE.read_text(encoding="utf-8").strip()
                    if payload:
                        stat = QR_FILE.stat()
                        revision = int(stat.st_mtime * 1000)
                        updated_at = time.strftime(
                            "%Y-%m-%dT%H:%M:%S", time.localtime(stat.st_mtime)
                        )
                        if QR_META_FILE.is_file():
                            try:
                                meta = json.loads(QR_META_FILE.read_text(encoding="utf-8"))
                                revision = int(meta.get("revision") or revision)
                                updated_at = meta.get("updated_at") or updated_at
                            except (json.JSONDecodeError, OSError, TypeError, ValueError):
                                pass
                        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
                        qr = {
                            "available": True,
                            "revision": revision,
                            "fingerprint": digest,
                            "payload": payload,
                            "updated_at": updated_at,
                        }
                except OSError:
                    pass

        return {
            "connected": connected,
            "bridge_state": bridge.get("state", "stopped"),
            "connection": connection,
            "qr": qr,
            "pairing_code": pairing_code,
            "link_mode": bridge_status.get("link_mode"),
            "status_message": bridge_status.get("hint") or bridge_status.get("message"),
            "disconnect_code": bridge_status.get("disconnect_code"),
        }


service_manager = ServiceManager()