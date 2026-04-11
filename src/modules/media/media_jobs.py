"""
Orquestrador e servicos de midia da Hana.
"""

from __future__ import annotations

import datetime as _dt
import logging
import os
import re
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field

from src.config.config_loader import CONFIG

logger = logging.getLogger(__name__)


class MediaJobError(RuntimeError):
    pass


class MediaCancelledError(RuntimeError):
    pass


def _coerce_bool(value, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "sim", "on"}:
            return True
        if lowered in {"0", "false", "no", "nao", "não", "off"}:
            return False
    return default


def _coerce_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _resolve_media_root(folder_name: str, fallback_root: str) -> str:
    try:
        output_dir = os.path.join(os.path.expanduser("~"), fallback_root, folder_name)
        os.makedirs(output_dir, exist_ok=True)
        return output_dir
    except Exception:
        fallback = os.path.join("C:\\", folder_name)
        os.makedirs(fallback, exist_ok=True)
        return fallback


DEFAULT_MUSIC_DIR = _resolve_media_root("Hana Music", "Music")


def get_media_settings() -> dict:
    media_cfg = CONFIG.get("MEDIA", {})
    if not isinstance(media_cfg, dict):
        media_cfg = {}

    music_cfg = media_cfg.get("music", {})
    if not isinstance(music_cfg, dict):
        music_cfg = {}

    queue_cfg = media_cfg.get("queue", {})
    if not isinstance(queue_cfg, dict):
        queue_cfg = {}

    return {
        "enabled": _coerce_bool(media_cfg.get("enabled", True), True),
        "auto_open_terminal_outputs": _coerce_bool(media_cfg.get("auto_open_terminal_outputs", True), True),
        "queue": {
            "max_concurrent_jobs": max(1, _coerce_int(queue_cfg.get("max_concurrent_jobs", 1), 1)),
        },
        "music": {
            "enabled": _coerce_bool(music_cfg.get("enabled", True), True),
            "backend": str(music_cfg.get("backend", "gemini_api") or "gemini_api").strip().lower(),
            "model": str(music_cfg.get("model", "lyria-3-pro-preview") or "lyria-3-pro-preview"),
            "output_dir": str(music_cfg.get("output_dir") or DEFAULT_MUSIC_DIR),
            "api_key": str(
                music_cfg.get("api_key")
                or CONFIG.get("GEMINI_API_KEY")
                or os.getenv("GEMINI_API_KEY")
                or ""
            ).strip(),
        },
    }


def get_media_runtime_capabilities() -> dict:
    settings = get_media_settings()
    media_enabled = bool(settings["enabled"])
    music = settings["music"]

    music_ready = (
        media_enabled
        and bool(music["enabled"])
        and music["backend"] == "gemini_api"
        and bool(music["api_key"])
    )

    return {
        "media_enabled": media_enabled,
        "music_generation_enabled": music_ready,
        "music_backend": music["backend"],
        "music_model": music["model"],
    }


def _slugify_prompt(prompt: str, max_len: int = 60) -> str:
    slug = re.sub(r"[^\w\s-]", "", (prompt or "")[:max_len]).strip()
    slug = re.sub(r"\s+", "_", slug)
    return slug or "midia"


def _timestamp() -> str:
    return _dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def _best_effort_startfile(path: str):
    if not path or not os.path.exists(path):
        return
    try:
        os.startfile(path)
    except Exception as e:
        logger.warning("[MEDIA] Falha ao abrir saida automaticamente %s: %s", path, e)


def _ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)
    return path


def _delete_file_safely(path: str | None):
    if not path:
        return
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


def _extract_parts(response) -> list:
    parts = []
    if hasattr(response, "parts") and response.parts:
        parts.extend(list(response.parts))

    try:
        candidates = list(getattr(response, "candidates", None) or [])
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            candidate_parts = getattr(content, "parts", None)
            if candidate_parts:
                parts.extend(list(candidate_parts))
    except Exception:
        pass

    if parts:
        return parts

    if isinstance(response, dict):
        direct_parts = response.get("parts") or []
        if direct_parts:
            return list(direct_parts)
        for candidate in response.get("candidates", []) or []:
            content = candidate.get("content") or {}
            candidate_parts = content.get("parts") or []
            if candidate_parts:
                parts.extend(list(candidate_parts))
    return parts


def _extract_inline_data(part):
    inline_data = getattr(part, "inline_data", None)
    if inline_data is not None:
        return inline_data
    if isinstance(part, dict):
        return part.get("inline_data") or part.get("inlineData")
    return None


def _extract_text_from_part(part) -> str:
    text_value = getattr(part, "text", None)
    if text_value:
        return str(text_value)
    if isinstance(part, dict):
        text_value = part.get("text")
        if text_value:
            return str(text_value)
    return ""


def _extract_response_text(response) -> str:
    text_chunks: list[str] = []
    direct_text = getattr(response, "text", None)
    if direct_text:
        text_chunks.append(str(direct_text))

    for part in _extract_parts(response):
        part_text = _extract_text_from_part(part)
        if part_text:
            text_chunks.append(part_text)

    return "\n".join(chunk for chunk in text_chunks if chunk).strip()


@dataclass
class MediaJobRecord:
    job_id: str
    kind: str
    prompt: str
    origin: str
    request_meta: dict = field(default_factory=dict)
    state: str = "queued"
    output_path: str | None = None
    mime_type: str | None = None
    source_uri: str | None = None
    error: str | None = None
    details: dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    cancel_requested: bool = False

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["kind_label"] = "musica"
        return payload


class _MusicGenerationBackend:
    MIME_TO_EXT = {
        "audio/mpeg": ".mp3",
        "audio/mp3": ".mp3",
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
    }

    def generate(self, prompt: str, cancel_event: threading.Event | None = None) -> dict:
        settings = get_media_settings()
        capabilities = get_media_runtime_capabilities()
        if not settings["enabled"] or not settings["music"]["enabled"]:
            raise MediaJobError("Geracao de musica esta desativada na configuracao.")
        if not capabilities["music_generation_enabled"]:
            raise MediaJobError("Musica indisponivel. Configure GEMINI_API_KEY para usar Lyria.")
        if cancel_event and cancel_event.is_set():
            raise MediaCancelledError("Geracao de musica cancelada pelo usuario.")

        from google import genai
        from google.genai import types

        music_cfg = settings["music"]
        client = genai.Client(api_key=music_cfg["api_key"])
        response = client.models.generate_content(
            model=music_cfg["model"],
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO", "TEXT"],
            ),
        )

        if cancel_event and cancel_event.is_set():
            raise MediaCancelledError("Geracao de musica cancelada pelo usuario.")

        audio_data = None
        mime_type = "audio/mp3"
        text_parts: list[str] = []
        for part in _extract_parts(response):
            part_text = _extract_text_from_part(part)
            if part_text:
                text_parts.append(part_text)
                continue
            inline_data = _extract_inline_data(part)
            if inline_data is None:
                continue
            if isinstance(inline_data, dict):
                inline_bytes = inline_data.get("data")
                inline_mime = inline_data.get("mime_type") or inline_data.get("mimeType")
            else:
                inline_bytes = getattr(inline_data, "data", None)
                inline_mime = getattr(inline_data, "mime_type", None)
            if inline_bytes:
                audio_data = inline_bytes
                mime_type = inline_mime or mime_type

        if not audio_data:
            response_text = "\n".join(text_parts).strip() or _extract_response_text(response)
            extra = f" Resposta textual: {response_text[:240]}" if response_text else ""
            raise MediaJobError(f"A resposta do Lyria nao retornou audio.{extra}")

        output_dir = _ensure_dir(music_cfg["output_dir"])
        ext = self.MIME_TO_EXT.get(str(mime_type).lower(), ".mp3")
        output_path = os.path.join(output_dir, f"{_timestamp()}_music_{_slugify_prompt(prompt)}{ext}")
        with open(output_path, "wb") as f:
            f.write(audio_data)

        return {
            "output_path": output_path,
            "mime_type": mime_type,
            "details": {
                "backend": "gemini_api",
                "model": music_cfg["model"],
                "text_preview": "\n".join(text_parts).strip(),
            },
        }


class MediaJobManager:
    def __init__(self):
        settings = get_media_settings()
        self._jobs: dict[str, MediaJobRecord] = {}
        self._cancel_events: dict[str, threading.Event] = {}
        self._lock = threading.Lock()
        self._queue_limiter = threading.Semaphore(settings["queue"]["max_concurrent_jobs"])
        self._music_backend = _MusicGenerationBackend()

    def submit(self, kind: str, prompt: str, origin: str, request_meta: dict | None = None) -> str:
        normalized_kind = str(kind or "").strip().lower()
        if normalized_kind != "music":
            raise MediaJobError(f"Tipo de midia nao suportado: {kind}")

        job_id = uuid.uuid4().hex[:12]
        job = MediaJobRecord(
            job_id=job_id,
            kind=normalized_kind,
            prompt=prompt,
            origin=origin,
            request_meta=dict(request_meta or {}),
        )
        cancel_event = threading.Event()
        with self._lock:
            self._jobs[job_id] = job
            self._cancel_events[job_id] = cancel_event

        threading.Thread(target=self._run_job, args=(job_id,), daemon=True, name=f"HanaMedia-{job_id}").start()
        return job_id

    def get_status(self, job_id: str) -> dict:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return {"job_id": job_id, "state": "failed", "error": "Job nao encontrado."}
            return job.to_dict()

    def _friendly_job_error(self, kind: str, technical_error: str) -> str:
        lowered = str(technical_error or "").strip().lower()
        if "nao retornou audio" in lowered or "não retornou áudio" in lowered or "nao retornou áudio" in lowered:
            return "O backend de musica respondeu sem audio nesta tentativa. Tente novamente ou ajuste o prompt."
        if any(token in lowered for token in ("api_key", "gemini", "lyria", "credential", "unauthorized", "401", "403")):
            return "Nao foi possivel gerar musica agora. Verifique a chave da Gemini API e tente novamente."
        return "Nao foi possivel gerar musica agora. Tente novamente em instantes."

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            cancel_event = self._cancel_events.get(job_id)
            if not job or not cancel_event:
                return False
            job.cancel_requested = True
            job.updated_at = time.time()
            if job.state == "queued":
                job.state = "cancelled"
            cancel_event.set()
            return True

    def _run_job(self, job_id: str):
        cancel_event = self._cancel_events.get(job_id)
        if cancel_event is None:
            return

        self._queue_limiter.acquire()
        try:
            job = self._get_job(job_id)
            if job is None:
                return
            if job.cancel_requested or cancel_event.is_set():
                self._update_job(job_id, state="cancelled")
                return

            self._update_job(job_id, state="running")
            result = self._music_backend.generate(job.prompt, cancel_event=cancel_event)

            if job.cancel_requested or cancel_event.is_set():
                _delete_file_safely(result.get("output_path"))
                self._update_job(job_id, state="cancelled")
                return

            self._update_job(
                job_id,
                state="completed",
                output_path=result.get("output_path"),
                mime_type=result.get("mime_type"),
                source_uri=result.get("source_uri"),
                details=result.get("details") or {},
                error=None,
            )
        except MediaCancelledError:
            self._update_job(job_id, state="cancelled")
        except Exception as e:
            technical_error = str(e)
            logger.exception("[MEDIA] Job %s falhou", job_id)
            self._update_job(
                job_id,
                state="failed",
                error=self._friendly_job_error(job.kind if job else "", technical_error),
                details={"technical_error": technical_error},
            )
        finally:
            self._queue_limiter.release()

    def _get_job(self, job_id: str) -> MediaJobRecord | None:
        with self._lock:
            return self._jobs.get(job_id)

    def _update_job(self, job_id: str, **changes):
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            for key, value in changes.items():
                setattr(job, key, value)
            job.updated_at = time.time()


_MEDIA_JOB_MANAGER: MediaJobManager | None = None
_MEDIA_MANAGER_LOCK = threading.Lock()


def get_media_job_manager() -> MediaJobManager:
    global _MEDIA_JOB_MANAGER
    with _MEDIA_MANAGER_LOCK:
        if _MEDIA_JOB_MANAGER is None:
            _MEDIA_JOB_MANAGER = MediaJobManager()
        return _MEDIA_JOB_MANAGER


class HanaMusicGen:
    def __init__(self):
        self._manager = get_media_job_manager()

    def submit(self, prompt: str, origin: str, request_meta: dict | None) -> str:
        return self._manager.submit("music", prompt, origin, request_meta)

    def get_status(self, job_id: str) -> dict:
        return self._manager.get_status(job_id)

    def cancel(self, job_id: str) -> bool:
        return self._manager.cancel(job_id)

