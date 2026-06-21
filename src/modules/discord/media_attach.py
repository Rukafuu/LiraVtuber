"""Leitura de anexos de imagem/áudio no Discord e enriquecimento de pedidos."""
from __future__ import annotations

import asyncio
import base64
import logging
import re
from typing import Any

import discord

logger = logging.getLogger(__name__)

_IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")
_AUDIO_EXT = (".ogg", ".opus", ".mp3", ".wav", ".m4a", ".webm", ".flac", ".aac", ".oga")
_VAGUE_MEDIA_RE = re.compile(
    r"\b(isso|disso|aquilo|aqui|essa|esse|este|olha|veja|analisa|analise|manda|mandei)\b",
    re.IGNORECASE,
)


def is_audio_attachment(att: discord.Attachment) -> bool:
    name = (att.filename or "").lower()
    content_type = str(att.content_type or "").lower()
    if any(name.endswith(ext) for ext in _AUDIO_EXT):
        return True
    return content_type.startswith("audio/")


def _audio_suffix(att: discord.Attachment) -> str:
    name = (att.filename or "").lower()
    for ext in _AUDIO_EXT:
        if name.endswith(ext):
            return ext
    content_type = str(att.content_type or "").lower()
    if "ogg" in content_type or "opus" in content_type:
        return ".ogg"
    if "mpeg" in content_type or "mp3" in content_type:
        return ".mp3"
    if "wav" in content_type:
        return ".wav"
    if "webm" in content_type:
        return ".webm"
    if "mp4" in content_type or "m4a" in content_type:
        return ".m4a"
    return ".ogg"


async def transcribe_discord_attachment(att: discord.Attachment) -> str | None:
    """Transcreve anexo de áudio do Discord (mensagem de voz ou arquivo)."""
    if not is_audio_attachment(att):
        return None
    if att.size and att.size > 25 * 1024 * 1024:
        logger.warning("[DISCORD] Áudio muito grande para STT: %s", att.filename)
        return None
    try:
        audio_bytes = await att.read()
    except Exception as exc:
        logger.warning("[DISCORD] Falha ao ler áudio %s: %s", att.filename, exc)
        return None
    if not audio_bytes or len(audio_bytes) < 32:
        return None

    from src.modules.voice.stt_whisper import transcribe_bytes

    suffix = _audio_suffix(att)
    stt_timeout = float(__import__("os").getenv("STT_TRANSCRIBE_TIMEOUT", "90"))
    try:
        text = await asyncio.wait_for(
            asyncio.to_thread(transcribe_bytes, audio_bytes, suffix=suffix),
            timeout=stt_timeout,
        )
    except asyncio.TimeoutError:
        logger.warning("[DISCORD] STT timeout para %s", att.filename)
        return None
    except Exception as exc:
        logger.warning("[DISCORD] STT falhou para %s: %s", att.filename, exc)
        return None

    text = (text or "").strip()
    if text:
        logger.info("[DISCORD] STT ok (%s): %s...", att.filename, text[:80])
    return text or None


def is_image_attachment(att: discord.Attachment) -> bool:
    name = (att.filename or "").lower()
    content_type = str(att.content_type or "").lower()
    if any(name.endswith(ext) for ext in _IMAGE_EXT):
        return True
    return content_type.startswith("image/")


async def read_image_b64(att: discord.Attachment) -> str | None:
    """Lê anexo de imagem e retorna base64, ou None se não for imagem."""
    if not is_image_attachment(att):
        return None
    try:
        img_bytes = await att.read()
    except Exception:
        return None
    if not img_bytes or len(img_bytes) < 32:
        return None
    return base64.b64encode(img_bytes).decode("utf-8")


def enrich_voice_prompt(texto: str, transcript: str) -> str:
    """Monta o texto do usuário a partir da transcrição de áudio."""
    texto = (texto or "").strip()
    transcript = (transcript or "").strip()
    if not transcript:
        return texto
    if texto:
        return f"{texto}\n\n[Mensagem de voz transcrita]: {transcript}"
    return transcript


def enrich_media_prompt(texto: str, *, has_image: bool) -> str:
    """Garante instrução explícita de análise visual quando há imagem."""
    if not has_image:
        return (texto or "").strip()

    texto = (texto or "").strip()
    if not texto:
        return (
            "Analise a imagem anexada em detalhe. Descreva o que aparece visualmente "
            "e responda em português do Brasil com sua personalidade."
        )

    if len(texto) < 16 or _VAGUE_MEDIA_RE.search(texto):
        return (
            f"{texto}\n\n"
            "[INSTRUÇÃO DO SISTEMA: o usuário anexou uma imagem nesta mensagem. "
            "Analise o conteúdo visual com atenção. Descreva o que realmente aparece "
            "na imagem e responda ao pedido em português do Brasil. "
            "Não peça para o usuário 'explicar o que é' — você deve ver a imagem.]"
        )
    return texto


def apply_vision_request_context(ctx: dict[str, Any]) -> dict[str, Any]:
    """Ajusta task_type/modelo/tokens para análise de imagem no Discord."""
    from lira_core.core.request_profiles import get_chat_settings

    settings = get_chat_settings()
    out = dict(ctx)
    out["task_type"] = "media_question"
    out["override_model"] = (
        out.get("media_model")
        or settings.get("media_model")
        or out.get("override_model")
    )
    out["max_output_tokens"] = settings.get("max_output_tokens_media", 8192)
    out["markdown_enabled"] = True
    out["response_mode"] = "normal"
    out["auto_route_media"] = True
    return out


def is_video_attachment(att: discord.Attachment) -> bool:
    name = (att.filename or "").lower()
    content_type = str(att.content_type or "").lower()
    video_exts = (".mp4", ".mov", ".webm", ".mkv")
    if any(name.endswith(ext) for ext in video_exts):
        return True
    return content_type.startswith("video/")


async def extract_video_frames_discord(att: discord.Attachment) -> list[str]:
    import os
    
    temp_dir = os.path.abspath("temp/incoming_media")
    os.makedirs(temp_dir, exist_ok=True)
    
    temp_path = os.path.join(temp_dir, f"discord_video_{att.id}_{att.filename}")
    try:
        await att.save(temp_path)
        from src.modules.vision.video_analyzer import VideoAnalyzer
        analyzer = VideoAnalyzer()
        frames = analyzer.extrair_frames(temp_path, max_frames=5)
        return frames or []
    except Exception as e:
        logger.error(f"[DISCORD] Erro ao extrair frames do video {att.filename}: {e}")
        return []


async def download_discord_sticker(sticker) -> str | None:
    import os
    import aiohttp
    
    temp_dir = os.path.abspath("temp/incoming_media")
    os.makedirs(temp_dir, exist_ok=True)
    
    ext = ".png"
    url = str(sticker.url)
    if ".gif" in url.lower():
        ext = ".gif"
    elif ".apng" in url.lower():
        ext = ".png"
        
    dest_path = os.path.join(temp_dir, f"discord_sticker_{sticker.id}{ext}")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    with open(dest_path, "wb") as f:
                        f.write(await resp.read())
                    return dest_path
    except Exception as e:
        logger.error(f"[DISCORD] Erro ao baixar sticker {sticker.name}: {e}")
    return None


def parse_custom_emojis(text: str) -> str:
    import re
    if not text:
        return ""
    return re.sub(r'<a?:([a-zA-Z0-9_]+):[0-9]+>', r'[Emoji: \1]', text)