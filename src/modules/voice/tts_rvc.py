import os
import asyncio
import threading
import logging
import pygame
from rvc_python.infer import RVCInference
from src.config.config_loader import CONFIG
from src.modules.voice import audio_control
from src.modules.voice.tts_edge import MotorTTSEdge

logger = logging.getLogger(__name__)

class MotorTTSRVC:
    def __init__(self):
        self.provedor = "rvc"
        self._stop_event = threading.Event()
        
        # Configurações do RVC
        settings = CONFIG.get("TTS_SETTINGS", {}).get("rvc", {})
        self.model_name = settings.get("model", "rei_br")
        self.pitch = settings.get("pitch", 0)  # Ajuste de tom (-12 a +12)
        
        # Caminhos dos modelos
        self.base_dir = os.path.join("data", "rvc_models", self.model_name)
        self.model_path = ""
        self.index_path = ""
        
        self._load_model_paths()
        
        # --- MONKEY PATCH PARA CORRIGIR BUG DO PYTORCH 2.4+ (weights_only) ---
        import torch
        original_torch_load = torch.load
        def patched_torch_load(*args, **kwargs):
            if 'weights_only' in kwargs:
                kwargs['weights_only'] = False
            else:
                # Se não estiver no kwargs, forçamos como False para evitar o default do PyTorch novo
                return original_torch_load(*args, **kwargs, weights_only=False)
            return original_torch_load(*args, **kwargs)
        torch.load = patched_torch_load
        # --------------------------------------------------------------------

        # --- MONKEY PATCH PARA CORRIGIR BUG DA BIBLIOTECA rvc-python (tuple error) ---
        import rvc_python.lib.audio as rvc_audio
        def patched_load_audio(file, sr):
            import librosa
            # Usamos librosa diretamente para evitar a tupla maldita
            data, _ = librosa.load(file, sr=sr)
            return data
            
        rvc_audio.load_audio = patched_load_audio
        # -----------------------------------------------------------

        # Inicializa o motor de inferência
        self.rvc = None
        if os.path.exists(self.model_path):
            try:
                # Forçamos CPU primeiro para estabilidade, se tiver 1660s podemos tentar cuda:0 depois
                device = "cuda:0" if CONFIG.get("USE_GPU", True) else "cpu:0"
                self.rvc = RVCInference(device=device)
                self.rvc.load_model(self.model_path, index_path=self.index_path)
                print(f"[TTS RVC] Modelo {self.model_name} carregado com PATCH de áudio!", flush=True)
            except Exception as e:
                logger.error(f"[TTS RVC] Erro ao carregar modelo: {e}")

        # Motor de voz base (Edge TTS)
        self.edge_motor = MotorTTSEdge()
        
        self.config_valida = (self.rvc is not None)

    def _load_model_paths(self):
        if not os.path.exists(self.base_dir):
            return
            
        for file in os.listdir(self.base_dir):
            if file.endswith(".pth"):
                self.model_path = os.path.join(self.base_dir, file)
            elif file.endswith(".index"):
                self.index_path = os.path.join(self.base_dir, file)

    def falar(self, texto, tocar_local=True) -> bool:
        if not texto: return False
        if not self.rvc:
            logger.error("[TTS RVC] Motor RVC não inicializado.")
            return False
        
        try:
            # 1. Gerar áudio base via Edge TTS
            success = self.edge_motor.falar(texto, tocar_local=False)
            if not success:
                return False
                
            input_mp3 = "data/last_response.mp3"
            input_wav = "data/last_response_base.wav" # Convertido para WAV para o RVC
            output_wav = "data/last_response_rvc.wav"
            
            if not os.path.exists(input_mp3):
                logger.error("[TTS RVC] Áudio base não gerado pelo Edge.")
                return False

            # Pré-conversão MP3 -> WAV (RVC gosta de WAV 16k ou 44k puro, mono, pcm_s16le)
            print(f"[DEBUG TTS RVC] Pré-convertendo MP3 para WAV (16k mono pcm_s16le)...", flush=True)
            try:
                if os.path.exists(input_wav): os.remove(input_wav)
                # Forçamos 16kHz, mono e pcm_s16le para evitar o erro de 'tuple'
                os.system(f'ffmpeg -i {input_mp3} -ar 16000 -ac 1 -acodec pcm_s16le {input_wav} -y -loglevel quiet')
            except Exception as e:
                logger.error(f"[TTS RVC] Erro ao converter para WAV: {e}")
                return False

            # 2. Converter via RVC
            print(f"[DEBUG TTS RVC] Iniciando conversão para {self.model_name}...", flush=True)
            
            try:
                import soundfile as sf
                import numpy as np
                
                # Definimos os parâmetros
                self.rvc.set_params(f0up_key=self.pitch, f0method="rmvpe")
                
                # TRUQUE FINAL: Como o infer_file está bugado na biblioteca, 
                # vamos tentar usar o vc_single diretamente se conseguirmos acessar o objeto interno
                if hasattr(self.rvc, 'vc'):
                    print(f"[DEBUG TTS RVC] Usando vc_single diretamente...", flush=True)
                    # O vc_single espera (sid, input_audio_path, f0_up_key, f0_file, f0_method, file_index, file_index2, index_rate, filter_radius, resample_sr, rms_mix_rate, protect)
                    audio_opt = self.rvc.vc.vc_single(
                        0, input_wav, self.pitch, None, "rmvpe", self.index_path, "", 
                        0.75, 3, 0, 0.15, 0.50
                    )
                    
                    # Se o retorno for uma tupla (erro, None), logamos
                    if isinstance(audio_opt, tuple) and len(audio_opt) == 2:
                        print(f"[DEBUG TTS RVC] Erro no vc_single: {audio_opt[0]}", flush=True)
                        return False
                    
                    # Salvar o resultado
                    import scipy.io.wavfile as wavfile
                    wavfile.write(output_wav, self.rvc.vc.tgt_sr, audio_opt)
                else:
                    # Fallback para o infer_file se não houver o objeto vc (mas com o patch de áudio que vou reforçar agora)
                    self.rvc.infer_file(input_wav, output_wav)
                
                print(f"[DEBUG TTS RVC] Inferência concluída.", flush=True)
            except Exception as rvc_err:
                import traceback
                print(f"[DEBUG TTS RVC] ERRO CRÍTICO: {rvc_err}", flush=True)
                print(traceback.format_exc(), flush=True)
                return False

            # Substituir o arquivo original pelo convertido
            final_audio = "data/last_response.mp3"
            if os.path.exists(output_wav):
                print(f"[DEBUG TTS RVC] Arquivo de saída encontrado: {output_wav}", flush=True)
                if os.path.exists(final_audio): os.remove(final_audio)
                
                # Converter WAV de volta para MP3 para o WhatsApp Bridge
                os.system(f'ffmpeg -i {output_wav} -acodec libmp3lame -ab 128k {final_audio} -y -loglevel quiet')
                print(f"[DEBUG TTS RVC] Conversão final para MP3 concluída!", flush=True)
                
                # Limpeza
                if os.path.exists(input_wav): os.remove(input_wav)
                if os.path.exists(output_wav): os.remove(output_wav)
                
                # 3. Tocar local se solicitado (para debug/teste)
                if tocar_local:
                    if not pygame.mixer.get_init(): pygame.mixer.init()
                    pygame.mixer.music.load(final_audio)
                    pygame.mixer.music.play()
                    while pygame.mixer.music.get_busy():
                        if self._stop_event.is_set() or audio_control.stop_requested():
                            pygame.mixer.music.stop()
                            break
                        pygame.time.Clock().tick(10)
                    try:
                        pygame.mixer.music.unload()
                    except Exception:
                        pass
                
                return True
            else:
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    if self._stop_event.is_set() or audio_control.stop_requested():
                        pygame.mixer.music.stop()
                        break
                    pygame.time.Clock().tick(10)
                try:
                    pygame.mixer.music.unload()
                except Exception:
                    pass

            return True

        except Exception as e:
            logger.error(f"[TTS RVC] Erro geral: {e}")
            return False

    def parar(self) -> bool:
        self._stop_event.set()
        self.edge_motor.parar()
        try:
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
        except Exception:
            pass
        return True
