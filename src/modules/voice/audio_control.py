from __future__ import annotations

import logging
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

STOP_SIGNAL_PATH = Path(tempfile.gettempdir()) / "hana_global_audio_stop.signal"

_callbacks: dict[str, Callable] = {}
_callbacks_lock = threading.RLock()
_local_stop_event = threading.Event()


def _read_signal_version() -> int:
    try:
        return STOP_SIGNAL_PATH.stat().st_mtime_ns
    except OSError:
        return 0


_last_seen_signal_version = _read_signal_version()


def _emit_local_stop(reason: str) -> None:
    _local_stop_event.set()
    with _callbacks_lock:
        callbacks = list(_callbacks.items())

    for name, callback in callbacks:
        try:
            callback(reason=reason)
        except TypeError:
            try:
                callback()
            except Exception as exc:
                logger.warning("[AUDIO CONTROL] Callback '%s' falhou: %s", name, exc)
        except Exception as exc:
            logger.warning("[AUDIO CONTROL] Callback '%s' falhou: %s", name, exc)


def register_stop_callback(name: str, callback: Callable) -> None:
    with _callbacks_lock:
        _callbacks[name] = callback


def unregister_stop_callback(name: str) -> None:
    with _callbacks_lock:
        _callbacks.pop(name, None)


def request_global_stop(reason: str = "user_request") -> bool:
    global _last_seen_signal_version

    try:
        STOP_SIGNAL_PATH.parent.mkdir(parents=True, exist_ok=True)
        STOP_SIGNAL_PATH.write_text(f"{time.time_ns()}|{reason}", encoding="utf-8")
        _last_seen_signal_version = _read_signal_version()
    except Exception as exc:
        logger.warning("[AUDIO CONTROL] Falha ao escrever sinal global de stop: %s", exc)

    _emit_local_stop(reason)
    return True


def poll_external_stop() -> bool:
    global _last_seen_signal_version

    current_version = _read_signal_version()
    if not current_version or current_version <= _last_seen_signal_version:
        return False

    _last_seen_signal_version = current_version
    _emit_local_stop("external_stop")
    return True


def stop_requested() -> bool:
    poll_external_stop()
    return _local_stop_event.is_set()


def reset_stop_state() -> None:
    poll_external_stop()
    _local_stop_event.clear()
