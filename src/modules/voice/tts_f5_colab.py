import logging
import os
import pygame
import threading
import shutil
from gradio_client import Client
from src.config.config_loader import CONFIG
from src.modules.voice import audio_control

logger = logging.getLogger(__name__)

class MotorTTSF5Colab:
    def __init__(self):
        self.provedor = "f5_colab"
        self.audio_disponivel = False
        self._stop_event = threading.Event()
        
        # O link do Gradio
        f5_cfg = CONFIG.get("TTS_SETTINGS", {}).get("f5_colab", {})
        self.api_url = f5_cfg.get("url", "")
        self.ref_text = f5_cfg.get("ref_text", "")
        self.speed = f5_cfg.get("speed", 0.8)
        self.client = None
        
        if self.api_url:
            # Inicializa em uma thread separada para não travar o bot do Discord no startup
            threading.Thread(target=self._init_client, daemon=True).start()

    def _init_client(self):
        try:
            logger.info(f"[F5-Colab] Conectando ao cliente Gradio em {self.api_url}...")
            self.client = Client(self.api_url)
            self.audio_disponivel = True
            audio_control.init_audio_mixer()
            logger.info("[F5-Colab] ✅ Conectado com sucesso!")
        except Exception as e:
            logger.warning(f"[F5-Colab] ❌ Erro ao conectar ao Gradio: {e}")

    def falar(self, texto: str, tocar_local=True) -> bool:
        if not self.client:
            logger.error("[F5-Colab] Cliente Gradio nao inicializado. Verifique a URL.")
            return False
            
        try:
            self._stop_event.clear()
            audio_control.reset_stop_state()
            
            # Limpeza de emojis do Discord (<:nome:id>), tags XML (<tag>), colchetes ([tag]) e chaves ({tag})
            import re
            texto_limpo = re.sub(r'<a?:\w+:\d+>', '', texto) # Remove emojis do Discord
            texto_limpo = re.sub(r'<[^>]+>', '', texto_limpo) # Remove tags XML residuais
            texto_limpo = re.sub(r'\[[^\]]+\]', '', texto_limpo) # Remove tags de colchetes [PARAM:...]
            texto_limpo = re.sub(r'\{[^\}]+\}', '', texto_limpo) # Remove chaves {...} residuais
            
            # Limpeza de risadas excessivas (evita crash no XTTS)
            texto_limpo = re.sub(r'[kK]{4,}', 'kkk', texto_limpo)
            texto_limpo = re.sub(r'[hH]{4,}', 'hhh', texto_limpo)
            
            texto_limpo = texto_limpo.strip()
            
            if not texto_limpo:
                return False

            logger.info(f"[F5-Colab] Solicitando audio para: {texto_limpo[:30]}...")
            
            # ... correcoes foneticas ...
            correcoes = {"GitHub": "Git Râbi", "github": "Git Râbi", "Python": "Páiton", "python": "Páiton", "Lucas": "Lúcas", "Prompt": "Prômp-ti"}
            texto_corrigido = texto_limpo
            for errado, certo in correcoes.items():
                texto_corrigido = texto_corrigido.replace(errado, certo)
            
            # Divisão em frases para evitar o limite de 400 tokens do XTTS
            sentences = re.split(r'(?<=[.!?]) +', texto_corrigido)
            sentences = [s.strip() for s in sentences if s.strip()]
            
            if not sentences:
                return None

            last_path = None
            for i, sentence in enumerate(sentences):
                logger.info(f"[F5-Colab] Processando frase {i+1}/{len(sentences)}: {sentence[:30]}...")
                
                try:
                    # Chama o endpoint /prever com texto + ref_text + speed
                    result = self.client.predict(
                        sentence,
                        self.ref_text,
                        api_name="/prever"
                    )
                except Exception as e:
                    # Fallback para interface de 1 input (compatibilidade)
                    try:
                        result = self.client.predict(sentence, fn_index=0)
                    except Exception as e2:
                        logger.error(f"[F5-Colab] Falha na API do Gradio (frase {i+1}): {e2}")
                        continue
                
                # Extrai o caminho do arquivo do resultado (pode ser string, dict ou tuple)
                result_path = None
                if isinstance(result, str) and os.path.exists(result):
                    result_path = result
                elif isinstance(result, dict) and result.get("name") and os.path.exists(result["name"]):
                    result_path = result["name"]
                elif isinstance(result, dict) and result.get("path") and os.path.exists(result["path"]):
                    result_path = result["path"]
                    
                if result_path:
                    import time
                    timestamp = int(time.time() * 1000) # Milissegundos para evitar colisão
                    target_path = f"data/response_{timestamp}.wav"
                    shutil.copy(result_path, target_path)
                    last_path = target_path # O Discord enviará o último ou o principal
                    
                    if tocar_local:
                        try:
                            if pygame.mixer.music.get_busy():
                                pygame.mixer.music.stop()
                            pygame.mixer.music.unload()
                            pygame.mixer.music.load(target_path)
                            pygame.mixer.music.play()
                            
                            start_wait = time.time()
                            while pygame.mixer.music.get_busy():
                                if time.time() - start_wait > 40:
                                    pygame.mixer.music.stop()
                                    break
                                if self._stop_event.is_set() or audio_control.stop_requested():
                                    pygame.mixer.music.stop()
                                    return target_path
                                pygame.time.Clock().tick(10)
                        except Exception as e:
                            logger.error(f"[F5-Colab] Erro no mixer (frase {i+1}): {e}")

            # Limpeza de arquivos antigos
            try:
                import glob
                audios = sorted(glob.glob("data/response_*.wav"))
                if len(audios) > 5:
                    for old_audio in audios[:-5]:
                        os.remove(old_audio)
            except: pass
            
            return last_path
                
        except Exception as e:
            logger.error(f"[F5-Colab] Erro na comunicacao com o Colab: {e}")
            return None
                
        except Exception as e:
            logger.error(f"[F5-Colab] Erro na comunicacao com o Colab: {e}")
            return None

    def parar(self) -> bool:
        self._stop_event.set()
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
        return True
