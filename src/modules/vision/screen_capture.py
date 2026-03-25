import os
import glob
import base64
import io
from PIL import Image

class MotorVisaoGroq:
    def __init__(self):
        # Pasta onde o ShareX salva as prints (Windows)
        # ShareX organiza por subpastas de data (ex: 2026-02), então usamos glob recursivo
        self.pasta_prints = os.path.join(
            os.path.expanduser("~"), "Documents", "ShareX", "Screenshots"
        )

    def obter_imagem_processada(self):
        """Encontra a última print, recorta se for dupla, e converte para Base64"""
        # Busca recursiva em todas as subpastas do ShareX (organizado por mês)
        arquivos = glob.glob(os.path.join(self.pasta_prints, "**", "*"), recursive=True)
        # Filtra apenas imagens
        extensoes_img = ('.png', '.jpg', '.jpeg', '.bmp', '.webp')
        arquivos = [f for f in arquivos if os.path.isfile(f) and f.lower().endswith(extensoes_img)]
        
        if not arquivos:
            return None, None
        
        caminho_imagem = max(arquivos, key=os.path.getctime)
        
        # Processamento da imagem para corrigir o Dual Monitor
        img = Image.open(caminho_imagem)
        largura, altura = img.size

        # Se a imagem for muito larga (Dual Monitor), recorta apenas a metade esquerda (Monitor 1)
        if largura > altura * 1.8:  
            print(f"[VISÃO] Print dupla detetada ({largura}x{altura}). A recortar apenas o Monitor 1...")
            # Posições do corte: (esquerda, topo, direita, baixo)
            img = img.crop((0, 0, largura // 2, altura))
            
        # Salva a imagem recortada na memória temporária e converte para código
        buffer = io.BytesIO() 
        img.save(buffer, format="PNG")
        imagem_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        return caminho_imagem, imagem_b64