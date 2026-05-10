import os
import glob
import random
import logging
import requests
import re
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class LiraImageGen:
    """Gerador de Imagens Pollinations (Rota Blindada) - Grátis e Ilimitado."""

    def __init__(self, output_dir: str = None):
        if output_dir is None:
            # Usa Pictures do sistema, mas com fallback portável para temp/
            default_pictures = os.path.join(os.path.expanduser("~"), "Pictures", "Hana Artista")
            output_dir = os.getenv("HANA_IMAGE_OUTPUT_DIR", default_pictures)

        self.output_dir = output_dir
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir, exist_ok=True)
            
        self.last_image_path = None
        logger.info(f"[IMAGE GEN] Motor Pollinations (Blindado) inicializado.")

    def generate(self, prompt: str) -> str | None:
        """Gera uma imagem usando a rota direta do Pollinations."""
        logger.info(f"[IMAGE GEN] Solicitando arte: '{prompt[:50]}...'")

        try:
            import urllib.parse
            # Prompt otimizado
            enhanced_prompt = f"anime style, masterpiece, high quality, {prompt}"
            safe_p = urllib.parse.quote(enhanced_prompt)
            
            # Rota direta que o site deles usa
            seed = random.randint(1, 100000)
            url = f"https://image.pollinations.ai/prompt/{safe_p}?width=1024&height=1024&seed={seed}&nologo=true&model=flux"
            
            logger.info(f"[IMAGE GEN] URL: {url}")
            
            response = requests.get(url, timeout=60)
            
            if response.status_code == 200 and len(response.content) > 10000:
                filename = self._sanitize_filename(prompt, prefix="flux")
                filepath = os.path.join(self.output_dir, filename)
                with open(filepath, "wb") as f:
                    f.write(response.content)
                
                self.last_image_path = filepath
                logger.info(f"[IMAGE GEN] ✅ SUCESSO! Salva em: {filepath} ({len(response.content)} bytes)")
                return filepath
            else:
                logger.error(f"[IMAGE GEN] Erro na resposta: {response.status_code} - Tamanho: {len(response.content)}")
                
        except Exception as e:
            logger.error(f"[IMAGE GEN] Erro na geração: {e}")

        return None

    def _sanitize_filename(self, prompt: str, prefix: str = "img") -> str:
        clean_prompt = re.sub(r'[^\w\s-]', '', prompt).strip().lower()
        clean_prompt = re.sub(r'[-\s]+', '_', clean_prompt)[:30]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{prefix}_{timestamp}_{clean_prompt}.png"

    def get_latest_image(self) -> str | None:
        if self.last_image_path and os.path.exists(self.last_image_path):
            return self.last_image_path
        pattern = os.path.join(self.output_dir, "*.png")
        files = glob.glob(pattern)
        if not files: return None
        return max(files, key=os.path.getmtime)
