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
    {
        "type": "function",
        "function": {
            "name": "gerar_imagem",
            "description": (
                "Gera uma imagem usando IA (modelo FLUX via Pollinations.ai) com base em uma descricao em texto. "
                "Use quando o usuario pedir para 'criar uma imagem', 'gerar uma foto', 'desenhar', 'mostrar como ficaria', etc. "
                "Retorna o caminho local da imagem gerada para exibicao na interface."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "Descricao detalhada da imagem a ser gerada, preferencialmente em ingles para melhor resultado.",
                    },
                    "largura": {
                        "type": "integer",
                        "description": "Largura da imagem em pixels (padrao: 768). Use 512 para rapido, 1024 para alta qualidade.",
                    },
                    "altura": {
                        "type": "integer",
                        "description": "Altura da imagem em pixels (padrao: 768).",
                    }
                },
                "required": ["prompt"],
            },
        },
    {
        "type": "function",
        "function": {
            "name": "agendar_aviso",
            "description": "Agenda um lembrete ou aviso para um momento futuro. A Lira interromperá o usuário para avisar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tempo": {
                        "type": "string", 
                        "description": "Tempo para o aviso. Pode ser relativo (ex: '5m', '1h', '30s') ou absoluto (ex: '20:30')."
                    },
                    "mensagem": {
                        "type": "string",
                        "description": "O que deve ser lembrado."
                    }
                },
                "required": ["tempo", "mensagem"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analisar_video",
            "description": "Analisa visualmente um vídeo (YouTube ou link direto). Extrai frames e os envia para a visão da Lira.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL do vídeo."}
                },
                "required": ["url"],
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

        if nome_tool == "gerar_imagem":
            return self._despachar_imagem(args)

        if nome_tool == "agendar_aviso":
            return self._despachar_agendamento(args)

        if nome_tool == "analisar_video":
            return self._despachar_analise_video(args)

        logger.warning(f"[TOOL MANAGER] Tool desconhecida: {nome_tool}")
        return ("Menu_Tool nao reconhecida pelo sistema.", "Nao reconheci essa acao.")

    def _despachar_imagem(self, args: dict) -> tuple:
        """Gera uma imagem via Pollinations.ai (FLUX) — gratuito, sem chave API."""
        import urllib.request
        import urllib.parse
        import os
        import time

        prompt = args.get("prompt", "")
        if not prompt:
            return ("Prompt vazio.", "Me diz o que você quer que eu desenhe!")

        largura = args.get("largura", 768)
        altura = args.get("altura", 768)
        seed = int(time.time())

        try:
            encoded = urllib.parse.quote(prompt)
            url = f"https://image.pollinations.ai/prompt/{encoded}?width={largura}&height={altura}&model=flux&nologo=true&seed={seed}"
            logger.info(f"[TOOL IMAGEM] Gerando: {prompt[:60]}...")

            os.makedirs("temp", exist_ok=True)
            caminho = os.path.join("temp", f"imagem_gerada_{seed}.jpg")

            req = urllib.request.Request(url, headers={"User-Agent": "HanaNakamura/1.0"})
            with urllib.request.urlopen(req, timeout=60) as response:
                with open(caminho, "wb") as f:
                    f.write(response.read())

            caminho_abs = os.path.abspath(caminho)
            logger.info(f"[TOOL IMAGEM] Imagem salva em: {caminho_abs}")
            bloco_retorno = f"[IMAGEM_GERADA:{caminho_abs}]"
            return (bloco_retorno, f"Criei uma imagem com o tema: {prompt[:60]}. Deixa eu te mostrar!")

        except Exception as e:
            logger.error(f"[TOOL IMAGEM] Erro: {e}")
            return (f"Erro ao gerar imagem: {e}", "Tive um probleminha ao tentar criar a imagem, desculpa!")

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
    def _despachar_agendamento(self, args: dict) -> tuple:
        import datetime
        import time
        
        tempo_raw = str(args.get("tempo", "")).lower().strip()
        msg = args.get("mensagem", "")
        
        if not (tempo_raw and msg):
            return ("Dados de agendamento incompletos.", "Não entendi quando ou o que devo lembrar.")

        try:
            # Lógica simples de parse de tempo
            now = datetime.datetime.now()
            target_time = None
            
            if ":" in tempo_raw: # Formato HH:MM
                h, m = map(int, tempo_raw.split(":"))
                target_time = now.replace(hour=h, minute=m, second=0, microsecond=0)
                if target_time < now: # Se já passou hoje, assume amanhã
                    target_time += datetime.timedelta(days=1)
            else: # Formato relativo (5m, 1h, etc)
                match = re.match(r"(\d+)\s*([smh])", tempo_raw)
                if match:
                    val = int(match.group(1))
                    unit = match.group(2)
                    if unit == "s": target_time = now + datetime.timedelta(seconds=val)
                    elif unit == "m": target_time = now + datetime.timedelta(minutes=val)
                    elif unit == "h": target_time = now + datetime.timedelta(hours=val)
            
            if not target_time:
                return ("Formato de tempo invalido.", "Não entendi esse horário, pode repetir?")

            # Salva no arquivo de agendamentos para o monitor ler
            agenda_path = os.path.abspath("data/scheduler.jsonl")
            os.makedirs("data", exist_ok=True)
            
            with open(agenda_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "target_timestamp": target_time.timestamp(),
                    "message": msg,
                    "created_at": now.timestamp(),
                    "status": "pending"
                }) + "\n")

            diff = target_time - now
            mins = int(diff.total_seconds() / 60)
            tempo_desc = f"em {mins} minutos" if mins > 0 else f"em {int(diff.total_seconds())} segundos"
            if ":" in tempo_raw: tempo_desc = f"às {tempo_raw}"

            return (f"Agendado para {target_time.isoformat()}", f"Ok! Vou te lembrar de '{msg}' {tempo_desc}.")
            
        except Exception as e:
            logger.error(f"[SCHEDULER] Erro ao agendar: {e}")
            return (f"Erro no agendamento: {e}", "Tive um erro interno ao tentar agendar seu aviso.")
    def _despachar_analise_video(self, args: dict) -> tuple:
        from src.modules.media.downloader import baixar_midia
        from src.modules.vision.video_analyzer import VideoAnalyzer
        import base64

        url = args.get("url", "")
        if not url:
            return ("URL ausente.", "Você esqueceu de me passar o link do vídeo.")

        try:
            # 1. Download do vídeo
            video_path = baixar_midia(url, tipo="video")
            if not video_path:
                return ("Falha no download do video.", "Não consegui baixar esse vídeo para olhar.")

            # 2. Extração de frames
            analyzer = VideoAnalyzer()
            frames = analyzer.extrair_frames(video_path, max_frames=4)
            
            if not frames:
                return ("Falha ao extrair frames.", "O vídeo parece estar corrompido ou vazio.")

            # 3. Preparar contexto visual
            res_str = "--- ANÁLISE VISUAL DE VÍDEO ---\n"
            res_str += f"Vídeo: {os.path.basename(video_path)}\n"
            res_str += f"Frames extraídos: {len(frames)}\n"
            res_str += "Analise os frames que foram enviados como imagens para descrever o vídeo.\n"
            res_str += "--- FIM ---"

            # Injetamos as imagens via tag especial para o loop tratar
            for f in frames:
                res_str += f"\n[IMAGE_DATA:{f}]"
            
            return (res_str, "Estou dando uma olhada nos frames desse vídeo agora mesmo...")

        except Exception as e:
            logger.error(f"[TOOL VIDEO] Erro: {e}")
            return (f"Erro na análise de vídeo: {e}", "Tive um problema ao tentar ver esse vídeo.")
