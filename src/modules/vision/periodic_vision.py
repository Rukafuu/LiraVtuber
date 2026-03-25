"""
Visão Sob Demanda da Nyra.
Captura a tela apenas quando solicitado, em Full HD, e retorna para análise.
"""

import os
import base64
import logging
from io import BytesIO

try:
    import mss
except ImportError:
    mss = None

try:
    from PIL import Image
except ImportError:
    Image = None

logger = logging.getLogger(__name__)


class VisaoNyra:
    """Sistema de visão sob demanda - captura a tela apenas quando solicitado."""

    def __init__(self):
        self.monitor_index = 1  # Monitor principal
        self._ultimo_caminho_img = None

    def capturar(self) -> dict:
        """
        Captura a tela agora em Full HD e retorna base64 + caminho do arquivo.
        
        Returns:
            dict: {
                "sucesso": bool,
                "b64": str (base64 da imagem),
                "caminho": str (caminho absoluto do arquivo)
                "erro": str (se sucesso for False)
            }
        """
        if not mss:
            return {"sucesso": False, "erro": "Módulo 'mss' não instalado. pip install mss"}
        
        if not Image:
            return {"sucesso": False, "erro": "Módulo 'Pillow' não instalado. pip install Pillow"}

        try:
            img_bytes = self._capturar_screenshot()
            img_b64 = base64.b64encode(img_bytes).decode("utf-8")
            
            # Salva temporariamente
            path_temp = os.path.join("temp", "ultima_visao.png")
            os.makedirs("temp", exist_ok=True)
            with open(path_temp, "wb") as f:
                f.write(img_bytes)
            
            self._ultimo_caminho_img = os.path.abspath(path_temp)
                
            return {
                "sucesso": True,
                "b64": img_b64,
                "caminho": self._ultimo_caminho_img
            }
            
        except Exception as e:
            logger.error(f"[VISÃO] Erro na captura: {e}")
            return {"sucesso": False, "erro": str(e)}

    def _capturar_screenshot(self) -> bytes:
        """Captura a tela do monitor configurado em Full HD e retorna como bytes PNG."""
        with mss.mss() as sct:
            monitor = sct.monitors[self.monitor_index]
            screenshot = sct.grab(monitor)
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
            
            # Redimensiona para Full HD (1920px de largura)
            largura_alvo = 1920
            
            if img.width > largura_alvo:
                ratio = largura_alvo / img.width
                novo_tamanho = (largura_alvo, int(img.height * ratio))
                img = img.resize(novo_tamanho, Image.LANCZOS)
                
            buffer = BytesIO()
            img.save(buffer, format="PNG", optimize=True)
            return buffer.getvalue()