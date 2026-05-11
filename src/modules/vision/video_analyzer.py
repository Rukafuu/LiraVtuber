import cv2
import os
import logging
import time

logger = logging.getLogger(__name__)

class VideoAnalyzer:
    def __init__(self, output_dir="temp/frames"):
        self.output_dir = output_dir
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def extrair_frames(self, video_path: str, max_frames: int = 5) -> list:
        """
        Extrai um número limitado de frames de um vídeo.
        Retorna uma lista de caminhos para as imagens geradas.
        """
        if not os.path.exists(video_path):
            logger.error(f"[VIDEO ANALYZER] Arquivo não encontrado: {video_path}")
            return []

        cap = cv2.VideoCapture(video_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames <= 0:
            return []

        # Calcula o intervalo para pegar frames bem distribuídos
        intervalo = max(1, total_frames // max_frames)
        frames_extraidos = []

        for i in range(max_frames):
            pos = i * intervalo
            cap.set(cv2.CAP_PROP_POS_FRAMES, pos)
            ret, frame = cap.read()
            if ret:
                frame_path = os.path.join(self.output_dir, f"frame_{int(time.time())}_{i}.jpg")
                cv2.imwrite(frame_path, frame)
                frames_extraidos.append(os.path.abspath(frame_path))
            else:
                break

        cap.release()
        logger.info(f"[VIDEO ANALYZER] Extraídos {len(frames_extraidos)} frames do vídeo.")
        return frames_extraidos
