import json
import os
import glob
import random
import logging
import requests
import re
import threading
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class LiraImageGen:
    """Gerador de Imagens Pollinations (Rota Blindada) - Grátis e Ilimitado."""

    def __init__(self, output_dir: str = None):
        if output_dir is None:
            default_pictures = os.path.join(os.path.expanduser("~"), "Pictures", "Lira Artista")
            output_dir = (
                os.getenv("LIRA_IMAGE_OUTPUT_DIR")
                or os.getenv("HANA_IMAGE_OUTPUT_DIR")
                or default_pictures
            )

        self.output_dir = output_dir
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir, exist_ok=True)
            
        self.last_image_path = None
        logger.info(f"[IMAGE GEN] Motor Pollinations (Blindado) inicializado.")

    def generate(self, prompt: str) -> str | None:
        """Gera uma imagem usando a rota direta do Pollinations (com retry sem chave) e fallback."""
        logger.info(f"[IMAGE GEN] Solicitando arte: '{prompt[:50]}...'")

        # 1. Tenta gerar via Pollinations (com chave, se existir no .env)
        pollinations_key = os.getenv("POLLINATIONS_API_KEY")
        filepath = self._try_pollinations(prompt, key=pollinations_key)
        if filepath:
            return filepath
            
        # 2. Se falhou e tínhamos chave configurada, tenta Pollinations SEM chave (modo anônimo)
        if pollinations_key:
            logger.info("[IMAGE GEN] Tentando novamente sem API Key (modo anonimo)...")
            filepath = self._try_pollinations(prompt, key=None)
            if filepath:
                return filepath

        # 3. Fallback para OpenRouter (se configurado com modelo pago no .env)
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

    def generate_advanced(self, prompt: str) -> str | None:
        """Gera uma imagem avançada tentando primeiro o OpenRouter Riverflow (raciocínio) e caindo para Pollinations."""
        logger.info(f"[IMAGE GEN] Solicitando arte avançada (Riverflow): '{prompt[:50]}...'")

        # 1. Tenta OpenRouter Riverflow primeiro
        try:
            img_bytes = self._generate_via_openrouter(prompt)
            if img_bytes:
                filename = self._sanitize_filename(prompt, prefix="riverflow")
                filepath = os.path.join(self.output_dir, filename)
                with open(filepath, "wb") as f:
                    f.write(img_bytes)
                self.last_image_path = filepath
                logger.info(f"[IMAGE GEN] ✅ SUCESSO via Riverflow! Salva em: {filepath} ({len(img_bytes)} bytes)")
                return filepath
        except Exception as e:
            logger.error(f"[IMAGE GEN] Falha no Riverflow: {e}. Tentando fallback Pollinations...")

        # 2. Se falhou, tenta Pollinations (modo anônimo livre)
        return self._try_pollinations(prompt, key=None)

    def _try_pollinations(self, prompt: str, key: str | None = None) -> str | None:
        try:
            import urllib.parse
            # Prompt otimizado
            enhanced_prompt = f"anime style, masterpiece, high quality, {prompt}"
            safe_p = urllib.parse.quote(enhanced_prompt)
            seed = random.randint(1, 100000)
            
            if key:
                url = f"https://image.pollinations.ai/prompt/{safe_p}?width=1024&height=1024&seed={seed}&nologo=true&model=flux&key={key}"
                headers = {"Authorization": f"Bearer {key}"}
            else:
                url = f"https://image.pollinations.ai/prompt/{safe_p}?width=1024&height=1024&seed={seed}&nologo=true&model=flux"
                headers = {}
                
            logger.info(f"[IMAGE GEN] URL: {url.split('&key=')[0]} (Chave: {'Sim' if key else 'Nao'})")
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200 and len(response.content) > 10000:
                filename = self._sanitize_filename(prompt, prefix="flux")
                filepath = os.path.join(self.output_dir, filename)
                with open(filepath, "wb") as f:
                    f.write(response.content)
                self.last_image_path = filepath
                logger.info(f"[IMAGE GEN] ✅ SUCESSO! Salva em: {filepath} ({len(response.content)} bytes)")
                return filepath
            else:
                logger.warning(f"[IMAGE GEN] Pollinations retornou status: {response.status_code} - Erro: {response.text[:200]}")
        except Exception as e:
            logger.error(f"[IMAGE GEN] Erro na geracao Pollinations: {e}")
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
            # Se você possuir créditos no OpenRouter, configure um modelo de imagem real no .env
            # Ex: OPENROUTER_IMAGE_MODEL=stabilityai/stable-diffusion-xl
            model = os.getenv("OPENROUTER_IMAGE_MODEL", "sourceful/riverflow-v2.5-fast:free")
            enhanced_prompt = f"anime style, masterpiece, high quality, {prompt}"
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": enhanced_prompt}],
                "modalities": ["image"]
            }
            logger.info(f"[IMAGE GEN] Enviando requisicao de imagem ao OpenRouter (modelo: {model})...")
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
        if not files:
            return None
        return max(files, key=os.path.getmtime)

    def edit(self, prompt: str, image_path: str | None = None) -> str | None:
        """Edição compatível — usa Riverflow para mudanças precisas."""
        ref = image_path if image_path and os.path.exists(image_path) else self.get_latest_image()
        if ref:
            self.last_image_path = ref
        edit_prompt = f"edit existing image, preserve layout where possible: {prompt}"
        return self.generate_advanced(edit_prompt)

    def generate_character(self, payload: str) -> str | None:
        """Compat Control API — payload JSON ou texto."""
        data = self._parse_payload(payload)
        prompt = str(data.get("prompt") or data.get("description") or payload).strip()
        if not prompt:
            return None
        style = data.get("style", "anime character portrait")
        return self.generate(f"{style}, {prompt}")

    def edit_character(self, payload: str) -> str | None:
        """Compat Control API — edição de personagem."""
        data = self._parse_payload(payload)
        prompt = str(data.get("prompt") or data.get("edit") or payload).strip()
        source = data.get("source_image") or data.get("image_path")
        return self.edit(prompt, image_path=source)

    def generate_and_show(self, prompt: str) -> None:
        """Pollinations/Flux em thread + abre no visualizador do Windows."""
        self._spawn_image_job(self.generate, prompt, label="flux")

    def generate_advanced_and_show(self, prompt: str) -> None:
        """Riverflow em thread + abre no visualizador do Windows."""
        self._spawn_image_job(self.generate_advanced, prompt, label="riverflow")

    def edit_and_show(self, prompt: str) -> None:
        """Edição em thread + abre no visualizador do Windows."""
        self._spawn_image_job(self.edit, prompt, label="edit")

    def _parse_payload(self, payload: str) -> dict:
        text = (payload or "").strip()
        if not text:
            return {}
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
        return {"prompt": text}

    def _open_image(self, path: str) -> None:
        try:
            os.startfile(path)
        except Exception as exc:
            logger.warning("[IMAGE GEN] Nao foi possivel abrir %s: %s", path, exc)

    def _spawn_image_job(self, fn, prompt: str, *, label: str) -> None:
        def _job():
            try:
                path = fn(prompt)
                if path:
                    self._open_image(path)
                    logger.info("[IMAGE GEN] %s pronto: %s", label, path)
                else:
                    logger.warning("[IMAGE GEN] %s falhou para: %s", label, prompt[:80])
            except Exception as exc:
                logger.error("[IMAGE GEN] Erro em %s: %s", label, exc)

        threading.Thread(target=_job, daemon=True, name=f"LiraImage-{label}").start()
