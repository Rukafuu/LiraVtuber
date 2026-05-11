import os
import subprocess
import logging

logger = logging.getLogger(__name__)

def baixar_midia(query, tipo="video"):
    # Se não for um link, trata como busca no YouTube
    if not query.startswith("http"):
        query = f"ytsearch1:{query}"
    
    url = query
    """
    Baixa vídeo ou áudio de diversas plataformas usando yt-dlp.
    tipo: 'video' ou 'audio'
    Retorna o caminho do arquivo baixado ou None se falhar.
    """
    output_dir = "temp"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    output_template = os.path.join(output_dir, "%(title)s.%(ext)s")
    
    cmd = ["yt-dlp", "-o", output_template]
    
    if tipo == "audio":
        cmd += ["-x", "--audio-format", "mp3"]
    else:
        # Tenta baixar o melhor formato de vídeo que seja mp4 para compatibilidade
        cmd += ["-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"]
        
    cmd.append(url)
    
    try:
        print(f"[DOWNLOADER] Iniciando download de {tipo}: {url}")
        # Captura o output para saber o nome do arquivo final
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"[DOWNLOADER] Erro no yt-dlp: {result.stderr}")
            return None
            
        # Tenta encontrar o arquivo na pasta temp (o yt-dlp não retorna o path fácil)
        # Uma forma melhor é listar os arquivos mais recentes na pasta temp
        import glob
        files = glob.glob(os.path.join(output_dir, "*"))
        if not files:
            return None
            
        # Pega o arquivo mais recente
        latest_file = max(files, key=os.path.getmtime)
        print(f"[DOWNLOADER] Download concluído: {latest_file}")
        return os.path.abspath(latest_file)
        
    except Exception as e:
        logger.error(f"[DOWNLOADER] Erro inesperado: {e}")
        return None
