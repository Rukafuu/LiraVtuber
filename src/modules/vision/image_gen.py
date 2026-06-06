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
        """Gera uma imagem usando a rota direta do Pollinations, com fallback para o OpenRouter."""
        logger.info(f"[IMAGE GEN] Solicitando arte: '{prompt[:50]}...'")

        # 1. Tenta gerar via Pollinations
        try:
            import urllib.parse
            # Prompt otimizado
            enhanced_prompt = f"anime style, masterpiece, high quality, {prompt}"
            safe_p = urllib.parse.quote(enhanced_prompt)
            
            seed = random.randint(1, 100000)
            pollinations_key = os.getenv("POLLINATIONS_API_KEY")
            
            if pollinations_key:
                url = f"https://image.pollinations.ai/prompt/{safe_p}?width=1024&height=1024&seed={seed}&nologo=true&model=flux&key={pollinations_key}"
                headers = {"Authorization": f"Bearer {pollinations_key}"}
            else:
                url = f"https://image.pollinations.ai/prompt/{safe_p}?width=1024&height=1024&seed={seed}&nologo=true&model=flux"
                headers = {}
            
            logger.info(f"[IMAGE GEN] URL: {url}")
            response = requests.get(url, headers=headers, timeout=60)
            
            if response.status_code == 200 and len(response.content) > 10000:
                filename = self._sanitize_filename(prompt, prefix="flux")
                filepath = os.path.join(self.output_dir, filename)
                with open(filepath, "wb") as f:
                    f.write(response.content)
                
                self.last_image_path = filepath
                logger.info(f"[IMAGE GEN] ✅ SUCESSO! Salva em: {filepath} ({len(response.content)} bytes)")
                return filepath
            else:
                logger.warning(f"[IMAGE GEN] Pollinations falhou/limitou (status: {response.status_code}). Tentando fallback do OpenRouter...")
                
        except Exception as e:
            logger.error(f"[IMAGE GEN] Erro na geração Pollinations: {e}. Tentando fallback do OpenRouter...")

        # 2. Fallback para OpenRouter
        try:
            img_bytes = self._generate_via_openrouter(prompt)
            if img_bytes:
                filename = self._sanitize_filename(prompt, prefix="openrouter")
                filepath = os.path.join(self.output_dir, filename)
                with open(filepath, "wb") as f:
                    f.write(img_bytes)
                
                self.last_image_path = filepath
                logger.info(f"[IMAGE GEN] ✅ SUCESSO via OpenRouter! Salva em: {filepath} ({len(img_bytes)} bytes)")
                return filepath
        except Exception as e:
            logger.error(f"[IMAGE GEN] Erro no fallback do OpenRouter: {e}")

        return None

    def _generate_via_openrouter(self, prompt: str) -> bytes | None:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            logger.warning("[IMAGE GEN] OPENROUTER_API_KEY ausente no .env. Impossível usar fallback.")
            return None
        try:
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            # Adiciona contexto de anime para bater com o padrão da Lira
            enhanced_prompt = f"anime style, masterpiece, high quality, {prompt}"
            payload = {
                "model": "sourceful/riverflow-v2.5-fast:free",
                "messages": [{"role": "user", "content": enhanced_prompt}],
                "modalities": ["image"]
            }
            logger.info("[IMAGE GEN] Enviando requisicao de imagem ao OpenRouter...")
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            if response.status_code == 200:
                res_data = response.json()
                choices = res_data.get("choices", [])
                if choices:
                    images = choices[0].get("message", {}).get("images", [])
                    if images:
                        img_url = images[0].get("image_url", {}).get("url", "")
                        if img_url.startswith("data:image"):
                            import base64
                            header, encoded = img_url.split(",", 1)
                            return base64.b64decode(encoded)
            else:
                logger.error(f"[IMAGE GEN] OpenRouter retornou status {response.status_code}: {response.text}")
        except Exception as e:
            logger.error(f"[IMAGE GEN] Falha na chamada ao OpenRouter: {e}")
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
