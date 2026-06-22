import os
import re
import subprocess
import logging
import glob
import json
import shutil
import time

import requests

logger = logging.getLogger(__name__)

# Limite do Discord para upload (25 MB em bytes)
_DISCORD_MAX_BYTES = 24 * 1024 * 1024  # 24MB com margem
_WHATSAPP_MAX_BYTES = 60 * 1024 * 1024  # 60MB com margem

_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_TWITTER_RE = re.compile(
    r"https?://(?:www\.)?(?:twitter\.com|x\.com)/([^/?#]+)/status/(\d+)",
    re.IGNORECASE,
)


def _extract_url(query: str) -> str:
    text = (query or "").strip()
    match = _URL_RE.search(text)
    return match.group(0).rstrip(".,);]") if match else text


def _is_twitter_url(url: str) -> bool:
    return bool(_TWITTER_RE.search(url or ""))


def _normalize_twitter_url(url: str) -> str:
    url = _extract_url(url)
    url = re.sub(r"/(video|photo)/\d+/?$", "", url, flags=re.IGNORECASE)
    return url.split("?")[0].rstrip("/")


def _twitter_media_index(url: str) -> int | None:
    match = re.search(r"/(video|photo)/(\d+)/?$", url, flags=re.IGNORECASE)
    if not match:
        return None
    return max(0, int(match.group(2)) - 1)


def _transcode_para_whatsapp(input_path: str, output_path: str) -> bool:
    """
    Garante codec H.264 + AAC em MP4 — único formato que o WhatsApp reproduz.
    Usa libx264 (CPU) com perfil baseline para máxima compatibilidade.
    Retorna True se converteu com sucesso.
    """
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-c:v", "libx264",
        "-profile:v", "baseline",  # máxima compat com celulares
        "-level", "3.0",
        "-pix_fmt", "yuv420p",     # 8-bit, sem HDR
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart", # streaming imediato
        "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",  # garante resolucao par
        output_path
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            encoding="utf-8", errors="ignore", timeout=180
        )
        if result.returncode == 0 and os.path.exists(output_path):
            logger.info("[DOWNLOADER] ✅ Transcoding OK: %s", os.path.basename(output_path))
            return True
        logger.error("[DOWNLOADER] ffmpeg falhou:\n%s", result.stderr[-600:])
        return False
    except Exception as e:
        logger.error("[DOWNLOADER] Erro no ffmpeg: %s", e)
        return False


def _finalize_download(
    latest: str,
    ts: int,
    titulo: str,
    tipo: str,
    *,
    transcode: bool = True,
) -> dict | None:
    if not latest or not os.path.exists(latest):
        return None

    tamanho = os.path.getsize(latest)
    ext = os.path.splitext(latest)[1].lower()
    tipo_real = "audio" if ext in (".mp3", ".ogg", ".opus", ".m4a", ".flac", ".wav") else "video"

    if tipo_real == "video" and transcode:
        output_dir = os.path.dirname(latest) or "temp"
        transcoded = os.path.join(output_dir, f"lira_{ts}_wpp.mp4")
        if _transcode_para_whatsapp(latest, transcoded):
            try:
                os.remove(latest)
            except Exception:
                pass
            latest = transcoded
            tamanho = os.path.getsize(latest)
        else:
            logger.warning("[DOWNLOADER] Transcoding falhou, enviando arquivo original.")

    logger.info(
        "[DOWNLOADER] ✅ Final: %s (%s, %.1f MB)",
        os.path.basename(latest),
        tipo_real,
        tamanho / 1024 / 1024,
    )
    return {
        "path": os.path.abspath(latest),
        "tipo": tipo_real,
        "titulo": titulo,
        "tamanho": tamanho,
    }


def _compress_video_to_limit(input_path: str, output_path: str, max_bytes: int) -> bool:
    """Recompacta vídeo para caber no limite (WhatsApp/Discord)."""
    target_mb = max(8, int(max_bytes / 1024 / 1024) - 2)
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-c:v", "libx264", "-profile:v", "baseline", "-level", "3.0",
        "-pix_fmt", "yuv420p", "-vf", "scale='min(1280,iw)':-2",
        "-b:v", f"{max(600, target_mb * 80)}k", "-maxrate", f"{max(800, target_mb * 100)}k",
        "-bufsize", f"{max(1200, target_mb * 150)}k",
        "-c:a", "aac", "-b:a", "96k",
        "-movflags", "+faststart",
        output_path,
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            encoding="utf-8", errors="ignore", timeout=300,
        )
        return (
            result.returncode == 0
            and os.path.exists(output_path)
            and os.path.getsize(output_path) <= max_bytes
        )
    except Exception as exc:
        logger.error("[DOWNLOADER] Falha ao compactar vídeo: %s", exc)
        return False


def _extract_audio_mp3(video_path: str, ts: int) -> str | None:
    output_dir = os.path.dirname(video_path) or "temp"
    mp3_path = os.path.join(output_dir, f"lira_{ts}_twitter.mp3")
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vn", "-acodec", "libmp3lame", "-b:a", "128k",
        mp3_path,
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            encoding="utf-8", errors="ignore", timeout=120,
        )
        if result.returncode == 0 and os.path.exists(mp3_path):
            try:
                os.remove(video_path)
            except Exception:
                pass
            return mp3_path
    except Exception as exc:
        logger.error("[DOWNLOADER] Falha ao extrair áudio: %s", exc)
    return None


def _download_twitter_fxtwitter(
    query: str,
    tipo: str,
    ts: int,
    max_bytes: int,
    *,
    transcode: bool = True,
) -> dict | None:
    """Fallback para Twitter/X quando o yt-dlp não autentica (sem cookies)."""
    url = _normalize_twitter_url(query)
    match = _TWITTER_RE.search(url)
    if not match:
        return None

    user, status_id = match.group(1), match.group(2)
    media_index = _twitter_media_index(query)

    try:
        resp = requests.get(
            f"https://api.fxtwitter.com/{user}/status/{status_id}",
            timeout=30,
            headers={"User-Agent": "LiraVT/1.0"},
        )
        resp.raise_for_status()
        payload = resp.json()
    except Exception as exc:
        logger.error("[DOWNLOADER] fxtwitter API falhou: %s", exc)
        return None

    tweet = payload.get("tweet") or {}
    media_items = (tweet.get("media") or {}).get("all") or []
    if not media_items:
        logger.error("[DOWNLOADER] Tweet sem mídia no fxtwitter: %s", url)
        return None

    if media_index is not None and media_index < len(media_items):
        item = media_items[media_index]
    else:
        item = media_items[0]

    titulo = (tweet.get("text") or f"twitter_{status_id}")[:80]
    output_dir = "temp"
    os.makedirs(output_dir, exist_ok=True)
    media_type = (item.get("type") or "").lower()

    if media_type == "photo":
        media_url = item.get("url")
        if not media_url:
            return None
        ext = ".jpg" if ".jpg" in media_url.lower() else ".png"
        dest = os.path.join(output_dir, f"lira_{ts}_twitter{ext}")
        try:
            with requests.get(media_url, timeout=90, stream=True) as r:
                r.raise_for_status()
                with open(dest, "wb") as f:
                    for chunk in r.iter_content(65536):
                        f.write(chunk)
        except Exception as exc:
            logger.error("[DOWNLOADER] Falha ao baixar imagem Twitter: %s", exc)
            return None
        result = _finalize_download(dest, ts, titulo, "video", transcode=False)
        if result:
            result["tipo"] = "image"
        return result

    if media_type not in ("video", "gif"):
        logger.error("[DOWNLOADER] Tipo de mídia Twitter não suportado: %s", media_type)
        return None

    mp4_candidates = []
    for fmt in item.get("formats") or []:
        fmt_url = fmt.get("url")
        if fmt.get("container") == "mp4" and fmt_url:
            mp4_candidates.append({"url": fmt_url, "bitrate": int(fmt.get("bitrate") or 0)})
    if not mp4_candidates and item.get("url"):
        mp4_candidates.append({"url": item["url"], "bitrate": 0})
    mp4_candidates.sort(key=lambda x: x["bitrate"])

    partial = os.path.join(output_dir, f"lira_{ts}_twitter_src.mp4")
    downloaded = None
    for candidate in reversed(mp4_candidates):
        try:
            with requests.get(candidate["url"], timeout=180, stream=True) as r:
                r.raise_for_status()
                with open(partial, "wb") as f:
                    for chunk in r.iter_content(65536):
                        f.write(chunk)
            size = os.path.getsize(partial)
            if size <= max_bytes:
                downloaded = partial
                break
            logger.info(
                "[DOWNLOADER] Twitter MP4 %.1f MB excede limite; tentando qualidade menor.",
                size / 1024 / 1024,
            )
            os.remove(partial)
        except Exception as exc:
            logger.warning("[DOWNLOADER] Falha em candidato Twitter: %s", exc)
            if os.path.exists(partial):
                try:
                    os.remove(partial)
                except Exception:
                    pass

    if not downloaded:
        logger.error("[DOWNLOADER] Nenhum MP4 do Twitter coube no limite de %.1f MB", max_bytes / 1024 / 1024)
        return None

    if tipo == "audio":
        mp3_path = _extract_audio_mp3(downloaded, ts)
        if not mp3_path:
            return None
        return _finalize_download(mp3_path, ts, titulo, "audio", transcode=False)

    # MP4 do CDN do Twitter já é H.264 — reencode só aumenta o arquivo.
    result = _finalize_download(downloaded, ts, titulo, tipo, transcode=False)
    if result and result["tamanho"] > max_bytes:
        compressed = os.path.join(output_dir, f"lira_{ts}_twitter_small.mp4")
        if _compress_video_to_limit(downloaded, compressed, max_bytes):
            try:
                os.remove(downloaded)
            except Exception:
                pass
            result = _finalize_download(compressed, ts, titulo, tipo, transcode=False)
    return result


def baixar_midia(
    query: str,
    tipo: str = "video",
    *,
    max_bytes: int | None = None,
    transcode: bool = True,
) -> dict | None:
    """
    Baixa vídeo ou áudio de qualquer plataforma suportada pelo yt-dlp
    (YouTube, Instagram, Twitter/X, TikTok, etc.).

    Retorna dict com:
      - path: caminho absoluto do arquivo
      - tipo: 'video' ou 'audio'
      - titulo: título do vídeo/post
      - tamanho: tamanho em bytes
    Ou None se falhar.
    """
    raw_query = (query or "").strip()
    if not raw_query:
        return None

    size_limit = max_bytes if max_bytes is not None else _DISCORD_MAX_BYTES
    url = _extract_url(raw_query)
    ytdlp_query = url if url.startswith("http") else f"ytsearch1:{raw_query}"
    if _is_twitter_url(url):
        ytdlp_query = _normalize_twitter_url(url)

    output_dir = "temp"
    os.makedirs(output_dir, exist_ok=True)

    cookies_file = os.path.join("data", "cookies.txt")
    cookies_args = ["--cookies", cookies_file] if os.path.exists(cookies_file) else []

    titulo = "video"
    try:
        info_cmd = ["yt-dlp", "--no-playlist", "--print", "%(title)s", *cookies_args, ytdlp_query]
        info = subprocess.run(
            info_cmd, capture_output=True, text=True,
            encoding="utf-8", errors="ignore", timeout=30,
        )
        t = (info.stdout.strip().splitlines() or [""])[0].strip()
        if t and "error" not in t.lower():
            titulo = t
    except Exception:
        pass

    ts = int(time.time())
    ext_final = "mp3" if tipo == "audio" else "mp4"
    safe_title = "".join(c for c in titulo[:40] if c.isalnum() or c in " _-").strip() or "video"
    dest = os.path.join(output_dir, f"lira_{ts}_{safe_title}.{ext_final}")

    cmd = [
        "yt-dlp",
        "--no-mtime",
        "--no-playlist",
        "--max-filesize", f"{size_limit}",
        "-o", dest,
        *cookies_args,
    ]
    if tipo == "audio":
        cmd += ["-x", "--audio-format", "mp3", "--audio-quality", "128K"]
    else:
        cmd += ["-f", "bestvideo+bestaudio/best", "--merge-output-format", "mp4"]
    cmd.append(ytdlp_query)

    try:
        logger.info("[DOWNLOADER] Baixando (%s): %s → %s", tipo, ytdlp_query[:80], os.path.basename(dest))
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            encoding="utf-8", errors="ignore", timeout=240,
        )

        if result.returncode != 0:
            logger.error("[DOWNLOADER] yt-dlp erro %d:\n%s", result.returncode, result.stderr[:600])
            if _is_twitter_url(url):
                logger.info("[DOWNLOADER] Tentando fallback fxtwitter para Twitter/X...")
                return _download_twitter_fxtwitter(
                    url, tipo, ts, size_limit, transcode=transcode,
                )
            return None

        if os.path.exists(dest):
            latest = dest
        else:
            pattern = os.path.join(output_dir, f"lira_{ts}_*")
            files = [
                f for f in glob.glob(pattern)
                if not f.endswith(".part") and not f.endswith(".ytdl")
            ]
            if not files:
                if _is_twitter_url(url):
                    return _download_twitter_fxtwitter(
                        url, tipo, ts, size_limit, transcode=transcode,
                    )
                logger.error("[DOWNLOADER] Arquivo não encontrado após download")
                return None
            latest = max(files, key=os.path.getmtime)

        return _finalize_download(latest, ts, titulo, tipo, transcode=transcode)

    except subprocess.TimeoutExpired:
        logger.error("[DOWNLOADER] Timeout ao baixar: %s", ytdlp_query)
        if _is_twitter_url(url):
            return _download_twitter_fxtwitter(url, tipo, ts, size_limit, transcode=transcode)
        return None
    except Exception as e:
        logger.error("[DOWNLOADER] Erro inesperado: %s", e)
        if _is_twitter_url(url):
            return _download_twitter_fxtwitter(url, tipo, ts, size_limit, transcode=transcode)
        return None


def buscar_opcoes_musica(query, limite=5):
    """
    Busca opções de vídeos no YouTube usando yt-dlp sem baixar.
    Retorna uma lista de dicionários contendo title, duration, url, id.
    """
    # Garante que usamos a sintaxe ytsearch
    search_query = f"ytsearch{limite}:{query}"
    
    cmd = [
        "yt-dlp",
        "--print", "%(title)s >>>LIRA<<< %(duration_string)s >>>LIRA<<< %(id)s",
        search_query
    ]
    
    try:
        print(f"[DOWNLOADER] Buscando opções de música para: {query}")
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore")
        
        if result.returncode != 0:
            logger.error(f"[DOWNLOADER] Erro ao buscar no YouTube: {result.stderr}")
            return []
            
        opcoes = []
        lines = result.stdout.strip().split('\n')
        
        for line in lines:
            if not line or '>>>LIRA<<<' not in line:
                continue
            parts = line.split('>>>LIRA<<<')
            if len(parts) >= 3:
                title = parts[0].strip()
                duration = parts[1].strip()
                video_id = parts[2].strip()
                
                opcoes.append({
                    "title": title,
                    "duration": duration,
                    "id": video_id,
                    "url": f"https://www.youtube.com/watch?v={video_id}"
                })
                
        return opcoes
        
    except Exception as e:
        logger.error(f"[DOWNLOADER] Erro ao buscar opções: {e}")
        return []
