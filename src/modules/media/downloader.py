import os
import subprocess
import logging
import glob
import json
import shutil

logger = logging.getLogger(__name__)

# Limite do Discord para upload (25 MB em bytes)
_DISCORD_MAX_BYTES = 24 * 1024 * 1024  # 24MB com margem


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


def baixar_midia(query: str, tipo: str = "video") -> dict | None:
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
    import time

    # Busca no YouTube se não for link
    if not query.startswith("http"):
        query = f"ytsearch1:{query}"

    output_dir = "temp"
    os.makedirs(output_dir, exist_ok=True)

    # Cookies do browser para Instagram/Twitter
    cookies_file = os.path.join("data", "cookies.txt")
    cookies_args = ["--cookies", cookies_file] if os.path.exists(cookies_file) else []

    # ── PASSO 1: pegar só o título (sem baixar) ──────────────────────────
    titulo = "video"
    try:
        info_cmd = [
            "yt-dlp", "--no-playlist", "--print", "%(title)s",
            *cookies_args, query
        ]
        info = subprocess.run(
            info_cmd, capture_output=True, text=True,
            encoding="utf-8", errors="ignore", timeout=30
        )
        t = (info.stdout.strip().splitlines() or [""])[0].strip()
        if t:
            titulo = t
    except Exception:
        pass

    # ── PASSO 2: download para arquivo com nome fixo ─────────────────────
    ts = int(time.time())
    ext_final = "mp3" if tipo == "audio" else "mp4"
    safe_title = "".join(c for c in titulo[:40] if c.isalnum() or c in " _-").strip() or "video"
    dest = os.path.join(output_dir, f"lira_{ts}_{safe_title}.{ext_final}")

    cmd = [
        "yt-dlp",
        "--no-mtime",
        "--no-playlist",
        "--max-filesize", f"{_DISCORD_MAX_BYTES}",
        "-o", dest,
        *cookies_args,
    ]

    if tipo == "audio":
        cmd += ["-x", "--audio-format", "mp3", "--audio-quality", "128K"]
    else:
        # Baixa qualquer formato — o ffmpeg vai converter depois
        cmd += [
            "-f", "bestvideo+bestaudio/best",
            "--merge-output-format", "mp4",
        ]

    cmd.append(query)

    try:
        logger.info("[DOWNLOADER] Baixando (%s): %s → %s", tipo, query[:60], os.path.basename(dest))
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            encoding="utf-8", errors="ignore", timeout=180,
        )

        if result.returncode != 0:
            logger.error("[DOWNLOADER] yt-dlp erro %d:\n%s",
                         result.returncode, result.stderr[:600])
            return None

        # O arquivo já tem nome fixo (dest), verificar se existe
        # yt-dlp pode ter adicionado extensão diferente — checar dest e variações
        if os.path.exists(dest):
            latest = dest
        else:
            # Fallback: arquivo mais recente com o mesmo prefixo de timestamp
            pattern = os.path.join(output_dir, f"lira_{ts}_*")
            files = [f for f in glob.glob(pattern)
                     if not f.endswith(".part") and not f.endswith(".ytdl")]
            if not files:
                logger.error("[DOWNLOADER] Arquivo não encontrado após download")
                return None
            latest = max(files, key=os.path.getmtime)

        tamanho = os.path.getsize(latest)
        ext = os.path.splitext(latest)[1].lower()
        tipo_real = "audio" if ext in (".mp3", ".ogg", ".opus", ".m4a", ".flac", ".wav") else "video"

        # === TRANSCODING PARA H.264+AAC ===
        # WhatsApp só reproduz H.264 + AAC em MP4. Sempre transcodamos para garantir.
        if tipo_real == "video":
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

        logger.info("[DOWNLOADER] ✅ Final: %s (%s, %.1f MB)",
                    os.path.basename(latest), tipo_real, tamanho / 1024 / 1024)

        return {
            "path": os.path.abspath(latest),
            "tipo": tipo_real,
            "titulo": titulo,
            "tamanho": tamanho,
        }

    except subprocess.TimeoutExpired:
        logger.error("[DOWNLOADER] Timeout ao baixar: %s", query)
        return None
    except Exception as e:
        logger.error("[DOWNLOADER] Erro inesperado: %s", e)
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
