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
                        "description": "O sujeito do fato (ex: 'Amarinth', 'Gato do Amarinth').",
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
    {
        "type": "function",
        "function": {
            "name": "pesquisa_web",
            "description": "Pesquisa informações em tempo real na internet (noticias, fatos, clima, etc).",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "A busca em português ou inglês."}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ler_tela_ocr",
            "description": "Tira uma captura da tela e extrai todo o texto visivel usando uma IA focada em OCR. Use isso quando o usuario pedir para 'ler a tela', 'ver o que esta escrito', ou extrair um texto que esta na tela do computador dele.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]


class ToolManager:
    def __init__(self, memory_manager=None):
        self.memory_manager = memory_manager
        self._tavily = None
        self._setup_tavily()

    def _setup_tavily(self):
        try:
            from tavily import TavilyClient
            api_key = os.getenv("TAVILY_API_KEY")
            if api_key:
                self._tavily = TavilyClient(api_key=api_key)
                logger.info("[TOOL MANAGER] Tavily configurado.")
        except Exception:
            pass

    @property
    def ferramentas(self) -> list:
        return FERRAMENTAS

    def executar_tool(self, nome_tool: str, args: dict) -> tuple:
        if nome_tool == "anotar_fato":
            return self._despachar_anotacao(args)

        if nome_tool == "analisar_youtube":
            return self._despachar_youtube(args)

        if nome_tool == "pesquisa_web":
            return self._despachar_web(args)

        if nome_tool == "ler_tela_ocr":
            return self._despachar_ocr(args)

        logger.warning(f"[TOOL MANAGER] Tool desconhecida: {nome_tool}")
        return ("Menu_Tool nao reconhecida pelo sistema.", "Nao reconheci essa acao.")

    def _despachar_ocr(self, args: dict) -> tuple:
        import os
        import json
        import urllib.request
        from src.modules.vision.periodic_vision import VisaoNyra

        try:
            visao = VisaoNyra()
            captura = visao.capturar()
            if not captura.get("sucesso"):
                return ("Erro ao capturar tela.", "Não consegui olhar para a tela agora.")
                
            b64 = captura.get("b64")
            api_key = os.getenv("OPENROUTER_API_KEY")
            if not api_key:
                return ("OPENROUTER_API_KEY ausente.", "Minha chave de visão OCR não está configurada.")

            req = urllib.request.Request(
                "https://openrouter.ai/api/v1/chat/completions",
                data=json.dumps({
                    "model": "baidu/qianfan-ocr-fast:free",
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Extraia todo o texto desta imagem. Apenas o texto, sem formatação extra."},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
                        ]
                    }]
                }).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/rukafuu/HanaNakamura-VTuber-OSS",
                    "X-Title": "Hana Nakamura"
                },
                method="POST"
            )

            with urllib.request.urlopen(req, timeout=15) as response:
                result = json.loads(response.read().decode("utf-8"))
                texto_extraido = result.get("choices", [{}])[0].get("message", {}).get("content", "")

            if not texto_extraido or len(texto_extraido.strip()) < 2:
                return ("Nenhum texto encontrado.", "Olhei para a tela, mas não consegui ler nenhum texto lá.")
                
            bloco_retorno = f"--- TEXTO EXTRAÍDO DA TELA (OCR) ---\n{texto_extraido}\n--- FIM ---"
            return (bloco_retorno, "Acabei de dar uma lida na sua tela, processando os textos...")

        except Exception as e:
            logger.error(f"[TOOL OCR] Erro: {e}")
            return (f"Erro no OCR: {e}", "Tive um problema ao tentar ler a sua tela.")

    def _despachar_web(self, args: dict) -> tuple:
        query = args.get("query", "")
        if not query or not self._tavily:
            return ("Tavily desabilitado ou query vazia.", "Não consegui pesquisar isso agora, mestre.")

        try:
            logger.info(f"[TOOL WEB] Pesquisando: {query}")
            search_result = self._tavily.search(query, max_results=3)
            results = search_result.get("results", [])
            
            if not results:
                return (f"Nenhum resultado para '{query}'", "Não encontrei nada sobre isso na internet.")

            lines = [f"Resultados para '{query}':"]
            for r in results:
                lines.append(f"- {r.get('title')}: {r.get('content')[:300]}... ({r.get('url')})")
            
            contexto = "\n".join(lines)
            return (contexto, f"Dei uma olhada na internet sobre {query} e descobri algumas coisas!")
        except Exception as e:
            logger.error(f"[TOOL WEB] Erro: {e}")
            return (f"Erro na pesquisa web: {e}", "Tive um probleminha técnico ao pesquisar na internet.")

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
