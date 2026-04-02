"""
Módulo de Geração e Edição de Imagens da Hana — via Gemini 2.5 Flash Image.

Usa o SDK google.genai com response_modalities=["TEXT", "IMAGE"]
para gerar e editar imagens.

Salva as imagens em: ~/Pictures/Hana Artista (auto-detectado)
"""

import datetime
import glob
import logging
import os
import re
import threading

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


def _resolve_output_dir():
    """Auto-detecta a pasta Pictures do usuário e cria 'Hana Artista' dentro."""
    try:
        pictures = os.path.join(os.path.expanduser("~"), "Pictures", "Hana Artista")
        os.makedirs(pictures, exist_ok=True)
        return pictures
    except Exception:
        fallback = os.path.join("C:\\", "Hana Artista")
        os.makedirs(fallback, exist_ok=True)
        return fallback


DEFAULT_OUTPUT_DIR = _resolve_output_dir()


class HanaImageGen:
    """Gerador e editor de imagens usando gemini-2.5-flash-image."""

    def __init__(self, output_dir: str = DEFAULT_OUTPUT_DIR):
        self.output_dir = output_dir
        self.modelo = "gemini-2.5-flash-image"
        self.client = None
        self.last_image_path: str | None = None    # Rastreia a última imagem (pra encadear edições)
        self._init_client()

        # Garante que a pasta de saída existe
        os.makedirs(self.output_dir, exist_ok=True)
        logger.info(f"[IMAGE GEN] Inicializado | Modelo: {self.modelo} | Pasta: {self.output_dir}")

    def _init_client(self):
        """Inicializa o cliente Google GenAI."""
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.error("[IMAGE GEN] GEMINI_API_KEY não encontrada no .env!")
            return
        try:
            self.client = genai.Client(api_key=api_key)
        except Exception as e:
            logger.error(f"[IMAGE GEN] Erro ao inicializar cliente GenAI: {e}")

    def _sanitize_filename(self, prompt: str, prefix: str = "") -> str:
        """Cria um nome de arquivo seguro baseado no prompt."""
        slug = re.sub(r'[^\w\s-]', '', prompt[:50]).strip()
        slug = re.sub(r'\s+', '_', slug)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        tag = f"{prefix}_" if prefix else ""
        return f"{timestamp}_{tag}{slug}.png"

    def _save_image_from_response(self, response, prompt: str, prefix: str = "") -> str | None:
        """Extrai a imagem da resposta do Gemini e salva em disco."""
        if not response.candidates or not response.candidates[0].content:
            logger.warning("[IMAGE GEN] Resposta vazia do modelo.")
            return None

        for part in response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.data:
                image_bytes = part.inline_data.data

                filename = self._sanitize_filename(prompt, prefix=prefix)
                filepath = os.path.join(self.output_dir, filename)

                with open(filepath, "wb") as f:
                    f.write(image_bytes)

                self.last_image_path = filepath
                logger.info(f"[IMAGE GEN] ✅ Imagem salva: {filepath}")
                return filepath

        logger.warning("[IMAGE GEN] Nenhuma imagem encontrada na resposta.")
        return None

    # ─── GERAÇÃO ───

    def generate(self, prompt: str) -> str | None:
        """
        Gera uma imagem a partir de um prompt de texto.

        Returns:
            Caminho absoluto da imagem salva, ou None em caso de erro.
        """
        if not self.client:
            logger.error("[IMAGE GEN] Cliente não inicializado.")
            return None

        logger.info(f"[IMAGE GEN] 🎨 Gerando: '{prompt[:80]}'")

        try:
            response = self.client.models.generate_content(
                model=self.modelo,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["TEXT", "IMAGE"],
                ),
            )
            return self._save_image_from_response(response, prompt, prefix="gen")

        except Exception as e:
            logger.error(f"[IMAGE GEN] Erro ao gerar imagem: {e}")
            return None

    # ─── EDIÇÃO ───

    def get_latest_image(self) -> str | None:
        """
        Retorna o caminho da imagem mais recente na pasta de saída.
        Prioridade: self.last_image_path > arquivo mais recente no diretório.
        """
        if self.last_image_path and os.path.exists(self.last_image_path):
            return self.last_image_path

        # Busca o PNG mais recente na pasta
        pattern = os.path.join(self.output_dir, "*.png")
        files = glob.glob(pattern)
        if not files:
            return None

        return max(files, key=os.path.getmtime)

    def edit(self, prompt: str, image_path: str | None = None) -> str | None:
        """
        Edita uma imagem existente com base em um prompt de texto.

        Args:
            prompt: Instruções de edição (ex: "mude o fundo para um pôr do sol").
            image_path: Caminho da imagem base. Se None, usa a última imagem gerada/editada.

        Returns:
            Caminho absoluto da imagem editada, ou None em caso de erro.
        """
        if not self.client:
            logger.error("[IMAGE EDIT] Cliente não inicializado.")
            return None

        # Resolve a imagem base
        source_path = image_path or self.get_latest_image()
        if not source_path or not os.path.exists(source_path):
            logger.error(f"[IMAGE EDIT] Nenhuma imagem encontrada para editar. Path: {source_path}")
            return None

        logger.info(f"[IMAGE EDIT] ✏️ Editando '{os.path.basename(source_path)}' com: '{prompt[:80]}'")

        try:
            # Carrega a imagem em bytes
            with open(source_path, "rb") as f:
                image_bytes = f.read()

            # Detecta o mime type
            ext = os.path.splitext(source_path)[1].lower()
            mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
            mime_type = mime_map.get(ext, "image/png")

            # Monta o conteúdo: imagem + prompt de edição
            contents = [
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                types.Part.from_text(text=prompt),
            ]

            response = self.client.models.generate_content(
                model=self.modelo,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_modalities=["TEXT", "IMAGE"],
                ),
            )
            return self._save_image_from_response(response, prompt, prefix="edit")

        except Exception as e:
            logger.error(f"[IMAGE EDIT] Erro ao editar imagem: {e}")
            return None

    # ─── WRAPPERS COM THREAD ───

    def generate_and_show(self, prompt: str):
        """Gera e abre a imagem. Roda em thread separada."""
        def _worker():
            filepath = self.generate(prompt)
            if filepath:
                try:
                    os.startfile(filepath)
                except Exception as e:
                    logger.error(f"[IMAGE GEN] Erro ao abrir imagem: {e}")

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
        logger.info(f"[IMAGE GEN] Thread de geração iniciada: '{prompt[:50]}'")

    def edit_and_show(self, prompt: str, image_path: str | None = None):
        """Edita e abre a imagem. Roda em thread separada."""
        def _worker():
            filepath = self.edit(prompt, image_path=image_path)
            if filepath:
                try:
                    os.startfile(filepath)
                except Exception as e:
                    logger.error(f"[IMAGE EDIT] Erro ao abrir imagem: {e}")

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
        logger.info(f"[IMAGE EDIT] Thread de edição iniciada: '{prompt[:50]}'")

