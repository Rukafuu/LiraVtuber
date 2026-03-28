import logging
import os
import re

from src.config.config_loader import CONFIG

logger = logging.getLogger(__name__)

FERRAMENTAS = [
    {
        "type": "function",
        "function": {
            "name": "anotar_fato",
            "description": (
                "Memoriza um fato importante sobre o usuario ou o mundo para nunca esquecer. "
                "Use isso quando o usuario pedir para 'lembrar', 'anotar', 'decorar' ou "
                "quando ele mencionar algo pessoal relevante (ex: nome do pet, aniversario, preferencias)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sujeito": {
                        "type": "string",
                        "description": "O sujeito do fato (ex: 'Nakamura', 'Gato do Nakamura').",
                    },
                    "relacao": {
                        "type": "string",
                        "description": "A acao ou relacao (ex: 'gosta_de', 'mora_em', 'tem_nome').",
                    },
                    "objeto": {
                        "type": "string",
                        "description": "O valor ou objeto do fato (ex: 'Morango', 'Sushi', 'Sao Paulo').",
                    }
                },
                "required": ["sujeito", "relacao", "objeto"],
            },
        },
    },
]


class ToolManager:
    def __init__(self, memory_manager=None):
        self.memory_manager = memory_manager

    @property
    def ferramentas(self) -> list:
        return FERRAMENTAS

    def executar_tool(self, nome_tool: str, args: dict) -> tuple:
        if nome_tool == "anotar_fato":
            return self._despachar_anotacao(args)

        if nome_tool == "analisar_youtube":
            return self._despachar_youtube(args)

        logger.warning(f"[TOOL MANAGER] Tool desconhecida: {nome_tool}")
        return ("Menu_Tool nao reconhecida pelo sistema.", "Nao reconheci essa acao.")

    def _despachar_anotacao(self, args: dict) -> tuple:
        """Executa a persistência de um fato no sistema de memória."""
        s = args.get("sujeito", "")
        r = args.get("relacao", "")
        o = args.get("objeto", "")
        
        if not (s and r and o):
            return ("Dados incompletos para anotar o fato.", "Ops, não entendi o que você quer que eu anote.")
            
        if self.memory_manager:
            try:
                self.memory_manager.add_fact(s, r, o)
                msg_cons = f"Fato gravado: {s} --[{r}]--> {o}"
                logger.info(f"[TOOL] {msg_cons}")
                return (msg_cons, f"Entendido! Anotei aqui que {s} {r} {o} e não vou mais esquecer.")
            except Exception as e:
                logger.error(f"[TOOL] Erro ao gravar fato: {e}")
                return (f"Erro técnico ao salvar memória: {e}", "Tive um problema ao tentar guardar essa informação.")
        else:
            logger.warning("[TOOL] MemoryManager não configurado no ToolManager.")
            return ("MemoryManager indisponível.", "Não consigo guardar isso na memória permanente agora.")

    def _despachar_youtube(self, args: dict) -> tuple:
        """Puxa a legenda completa de um vídeo do YouTube via youtube-transcript-api."""
        import urllib.parse
        url = args.get("url", "")
        if not url:
            return ("URL vazio.", "Você me passou um link do YouTube vazio.")

        # Extrai o ID do vídeo usando regex/parse
        try:
            parsed = urllib.parse.urlparse(url)
            video_id = None
            if "youtube.com" in parsed.netloc:
                video_id = urllib.parse.parse_qs(parsed.query).get("v", [None])[0]
                if not video_id:
                    # Tenta /shorts/ID, /live/ID, /embed/ID
                    path_match = re.match(r'/(?:shorts|live|embed)/([a-zA-Z0-9_-]+)', parsed.path)
                    if path_match:
                        video_id = path_match.group(1)
            elif "youtu.be" in parsed.netloc:
                video_id = parsed.path.lstrip("/")
            else:
                return ("Link inválido.", "Isso não parece um link válido do YouTube.")
            
            if not video_id:
                return ("ID de vídeo não encontrado no link.", "Não encontrei qual é o vídeo nesse link.")
        except Exception as e:
            logger.error(f"[TOOL YOUTUBE] Erro ao parsear URL: {e}")
            return (f"Erro parse: {e}", "O formato do link está meio estranho.")

        logger.info(f"[TOOL YOUTUBE] Puxando legendas para ID: {video_id}")
        
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['pt', 'en', 'es'])
            
            # Montar a string crua
            textos = [f"[{item['start']:.1f}s] {item['text']}" for item in transcript_list]
            texto_completo = "\n".join(textos)
            
            bloco_retorno = (
                f"--- TRANSCRIÇÃO YOUTUBE ({video_id}) ---\n"
                f"{texto_completo}\n"
                f"--- FIM DA TRANSCRIÇÃO ---\n"
            )
            
            # Limitar tamanho caso a legenda seja monstruosa (ex: 4 horas) - 200k chars ~ 50k tokens
            if len(bloco_retorno) > 200000:
                bloco_retorno = bloco_retorno[:200000] + "\n\n...[TRUNCADO: VÍDEO MUITO LONGO]..."

            return (bloco_retorno, "Prontinho, já li a transcrição do vídeo inteiro.")
            
        except ImportError:
            return ("Biblioteca youtube_transcript_api nã instalada.", "Preciso que me instalem a biblioteca para baixar vídeos.")
        except Exception as e:
            logger.error(f"[TOOL YOUTUBE] Erro ao baixar legenda: {e}")
            return (f"Erro Youtube API: {e}", "Não consegui ler as legendas desse vídeo. Talvez ele não tenha legendas automáticas ou seja privado.")
