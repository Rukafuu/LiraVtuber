import logging
import os
import re

from lira_core.providers.provider_selector import ProviderSelector
from lira_core.tools.registry import TOOL_REGISTRY, resolve_tool_id
from lira_core.economy import account_from_caller, lira_finance

logger = logging.getLogger(__name__)

_LIRA_HTTP_HEADERS = {
    "User-Agent": "LiraVT/1.0",
    "HTTP-Referer": "https://github.com/AmarinthIA/AmarinthLira-VTuber-OSS",
    "X-Title": "Lira AM Amarinth",
}


class ToolManager:
    def __init__(self, memory_manager=None, caller_context=None):
        self.memory_manager = memory_manager
        self.caller_context = caller_context
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
    def registry(self) -> dict:
        return TOOL_REGISTRY

    def list_tool_ids(self) -> list[str]:
        return sorted(TOOL_REGISTRY.keys())

    def executar_tool(self, nome_tool: str, args: dict) -> tuple[str, str]:
        tool_id = resolve_tool_id(nome_tool)

        if tool_id == "anotar_fato":
            return self._despachar_anotacao(args)
        if tool_id == "analisar_youtube":
            return self._despachar_youtube(args)
        if tool_id == "pesquisa_web":
            return self._despachar_web(args)
        if tool_id == "ler_tela_ocr":
            return self._despachar_ocr(args)
        if tool_id == "gerar_imagem":
            return self._despachar_imagem(args)
        if tool_id == "registrar_transacao":
            return self._despachar_registrar_transacao(args)
        if tool_id == "obter_financas":
            return self._despachar_obter_financas(args)

        logger.warning("[TOOL MANAGER] Tool desconhecida: %s (resolvido: %s)", nome_tool, tool_id)
        return ("Tool nao reconhecida pelo sistema.", "Nao reconheci essa acao.")

    def _despachar_imagem(self, args: dict) -> tuple[str, str]:
        import time
        import urllib.parse
        import urllib.request
        import base64
        import json

        prompt = args.get("prompt", "")
        if not prompt:
            return ("Prompt vazio.", "Me diz o que voce quer que eu desenhe!")

        largura = args.get("largura", 768)
        altura = args.get("altura", 768)
        seed = int(time.time())

        # 1. Tenta gerar via Pollinations
        try:
            encoded = urllib.parse.quote(prompt)
            pollinations_key = os.getenv("POLLINATIONS_API_KEY")
            
            if pollinations_key:
                url = (
                    f"https://image.pollinations.ai/prompt/{encoded}"
                    f"?width={largura}&height={altura}&model=flux&nologo=true&seed={seed}&key={pollinations_key}"
                )
                headers = {
                    "User-Agent": _LIRA_HTTP_HEADERS["User-Agent"],
                    "Authorization": f"Bearer {pollinations_key}"
                }
            else:
                url = (
                    f"https://image.pollinations.ai/prompt/{encoded}"
                    f"?width={largura}&height={altura}&model=flux&nologo=true&seed={seed}"
                )
                headers = {"User-Agent": _LIRA_HTTP_HEADERS["User-Agent"]}
                
            logger.info("[TOOL IMAGEM] Gerando via Pollinations: %s...", prompt[:60])

            os.makedirs("temp", exist_ok=True)
            caminho = os.path.join("temp", f"imagem_gerada_{seed}.jpg")

            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as response:
                img_data = response.read()
                
            if len(img_data) > 10000:
                with open(caminho, "wb") as f:
                    f.write(img_data)
                caminho_abs = os.path.abspath(caminho)
                logger.info("[TOOL IMAGEM] Imagem salva em: %s", caminho_abs)
                return (f"[IMAGEM_GERADA:{caminho_abs}]", f"Criei uma imagem com o tema: {prompt[:60]}. Deixa eu te mostrar!")
            else:
                logger.warning("[TOOL IMAGEM] Resposta da imagem muito pequena, tentando fallback OpenRouter...")

        except Exception as e:
            logger.warning("[TOOL IMAGEM] Erro Pollinations: %s. Tentando fallback OpenRouter...", e)

        # 2. Fallback para OpenRouter
        try:
            api_key = os.getenv("OPENROUTER_API_KEY")
            if not api_key:
                return ("Erro: chaves de imagem indisponiveis.", "Tive um problema ao tentar gerar a imagem (sem conexao/chaves).")
                
            url = "https://openrouter.ai/api/v1/chat/completions"
            enhanced_prompt = f"anime style, masterpiece, high quality, {prompt}"
            payload = {
                "model": "sourceful/riverflow-v2.5-fast:free",
                "messages": [{"role": "user", "content": enhanced_prompt}],
                "modalities": ["image"]
            }
            
            logger.info("[TOOL IMAGEM] Chamando OpenRouter fallback...")
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": _LIRA_HTTP_HEADERS["User-Agent"]
                },
                method="POST"
            )
            
            with urllib.request.urlopen(req, timeout=60) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                
            choices = res_data.get("choices", [])
            if choices:
                images = choices[0].get("message", {}).get("images", [])
                if images:
                    img_url = images[0].get("image_url", {}).get("url", "")
                    if img_url.startswith("data:image"):
                        header, encoded = img_url.split(",", 1)
                        img_bytes = base64.b64decode(encoded)
                        
                        os.makedirs("temp", exist_ok=True)
                        caminho = os.path.join("temp", f"imagem_gerada_{seed}.jpg")
                        with open(caminho, "wb") as f:
                            f.write(img_bytes)
                            
                        caminho_abs = os.path.abspath(caminho)
                        logger.info("[TOOL IMAGEM] Imagem salva via OpenRouter em: %s", caminho_abs)
                        return (f"[IMAGEM_GERADA:{caminho_abs}]", f"Criei uma imagem com o tema: {prompt[:60]}. Deixa eu te mostrar!")
                        
            return ("Erro ao obter imagem da API.", "Nao consegui gerar a imagem...")
            
        except Exception as e:
            logger.error("[TOOL IMAGEM] Erro no fallback: %s", e)
            return (f"Erro ao gerar imagem: {e}", "Tive um probleminha ao tentar criar a imagem, desculpa!")

    def _despachar_ocr(self, args: dict) -> tuple[str, str]:
        import json
        import urllib.request

        try:
            from src.modules.vision.periodic_vision import VisaoNyra
        except ImportError as exc:
            return ("Modulo de visao indisponivel.", f"Nao consegui acessar a captura de tela: {exc}")

        try:
            visao = VisaoNyra()
            captura = visao.capturar()
            if not captura.get("sucesso"):
                return ("Erro ao capturar tela.", "Nao consegui olhar para a tela agora.")

            b64 = captura.get("b64")
            api_key = os.getenv("OPENROUTER_API_KEY")
            if not api_key:
                return ("OPENROUTER_API_KEY ausente.", "Minha chave de visao OCR nao esta configurada.")

            req = urllib.request.Request(
                "https://openrouter.ai/api/v1/chat/completions",
                data=json.dumps({
                    "model": "baidu/qianfan-ocr-fast:free",
                    "messages": [{
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Extraia todo o texto desta imagem. Apenas o texto, sem formatacao extra.",
                            },
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                        ],
                    }],
                }).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    **_LIRA_HTTP_HEADERS,
                },
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=15) as response:
                result = json.loads(response.read().decode("utf-8"))
                texto_extraido = result.get("choices", [{}])[0].get("message", {}).get("content", "")

            if not texto_extraido or len(texto_extraido.strip()) < 2:
                return ("Nenhum texto encontrado.", "Olhei para a tela, mas nao consegui ler nenhum texto la.")

            bloco_retorno = f"--- TEXTO EXTRAIDO DA TELA (OCR) ---\n{texto_extraido}\n--- FIM ---"
            return (bloco_retorno, "Acabei de dar uma lida na sua tela, processando os textos...")

        except Exception as e:
            logger.error("[TOOL OCR] Erro: %s", e)
            return (f"Erro no OCR: {e}", "Tive um problema ao tentar ler a sua tela.")

    def _despachar_web(self, args: dict) -> tuple[str, str]:
        query = args.get("query", "")
        if not query:
            return ("Query vazia.", "Nao consegui pesquisar isso agora.")

        try:
            from lira_core.tools.runner_helpers import mcp_gateway_reachable
            from lira_core.tools.mcp_client import call_mcp

            if mcp_gateway_reachable():
                logger.info("[TOOL WEB] MCP tavily/search: %s", query)
                return call_mcp("tavily", "search", {"query": query})
        except Exception as e:
            logger.warning("[TOOL WEB] MCP indisponível, fallback SDK: %s", e)

        if not self._tavily:
            return ("Tavily desabilitado ou query vazia.", "Nao consegui pesquisar isso agora.")

        try:
            logger.info("[TOOL WEB] Pesquisando (SDK): %s", query)
            search_result = self._tavily.search(query, max_results=5)
            results = search_result.get("results", [])

            if not results:
                return (f"Nenhum resultado para '{query}'", "Nao encontrei nada sobre isso na internet.")

            lines = [f"Resultados para '{query}':"]
            for r in results:
                lines.append(f"- {r.get('title')}: {r.get('content')[:300]}... ({r.get('url')})")

            return ("\n".join(lines), f"Dei uma olhada na internet sobre {query} e descobri algumas coisas!")
        except Exception as e:
            logger.error("[TOOL WEB] Erro: %s", e)
            return (f"Erro na pesquisa web: {e}", "Tive um probleminha tecnico ao pesquisar na internet.")

    def _despachar_anotacao(self, args: dict) -> tuple[str, str]:
        s = args.get("sujeito", "")
        r = args.get("relacao", "")
        o = args.get("objeto", "")

        if not (s and r and o):
            return ("Dados incompletos para anotar o fato.", "Ops, nao entendi o que voce quer que eu anote.")

        if self.memory_manager:
            try:
                self.memory_manager.add_fact(s, r, o)
                msg_cons = f"Fato gravado: {s} --[{r}]--> {o}"
                logger.info("[TOOL] %s", msg_cons)
                return (msg_cons, f"Entendido! Anotei aqui que {s} {r} {o} e nao vou mais esquecer.")
            except Exception as e:
                logger.error("[TOOL] Erro ao gravar fato: %s", e)
                return (f"Erro tecnico ao salvar memoria: {e}", "Tive um problema ao tentar guardar essa informacao.")

        logger.warning("[TOOL] MemoryManager nao configurado no ToolManager.")
        return ("MemoryManager indisponivel.", "Nao consigo guardar isso na memoria permanente agora.")

    def _despachar_youtube(self, args: dict) -> tuple[str, str]:
        import urllib.parse

        url = args.get("url", "")
        if not url:
            return ("URL vazio.", "Voce me passou um link do YouTube vazio.")

        try:
            parsed = urllib.parse.urlparse(url)
            video_id = None
            if "youtube.com" in parsed.netloc:
                video_id = urllib.parse.parse_qs(parsed.query).get("v", [None])[0]
                if not video_id:
                    path_match = re.match(r"/(?:shorts|live|embed)/([a-zA-Z0-9_-]+)", parsed.path)
                    if path_match:
                        video_id = path_match.group(1)
            elif "youtu.be" in parsed.netloc:
                video_id = parsed.path.lstrip("/")
            else:
                return ("Link invalido.", "Isso nao parece um link valido do YouTube.")

            if not video_id:
                return ("ID de video nao encontrado no link.", "Nao encontrei qual e o video nesse link.")
        except Exception as e:
            logger.error("[TOOL YOUTUBE] Erro ao parsear URL: %s", e)
            return (f"Erro parse: {e}", "O formato do link esta meio estranho.")

        logger.info("[TOOL YOUTUBE] Puxando legendas para ID: %s", video_id)

        try:
            from youtube_transcript_api import YouTubeTranscriptApi

            api = YouTubeTranscriptApi()
            transcript_list_obj = api.list(video_id)

            try:
                transcript = transcript_list_obj.find_transcript(
                    ["pt", "pt-BR", "pt-PT", "en", "en-US", "en-GB"]
                )
            except Exception:
                first_transcript = None
                for t in transcript_list_obj:
                    first_transcript = t
                    break
                if first_transcript and first_transcript.is_translatable:
                    transcript = first_transcript.translate("pt")
                else:
                    raise RuntimeError("Nenhuma legenda disponivel ou traduzivel encontrada.")

            transcript_list = transcript.fetch()

            textos = []
            for item in transcript_list:
                if isinstance(item, dict):
                    start = item.get("start", 0.0)
                    text = item.get("text", "")
                else:
                    start = getattr(item, "start", 0.0)
                    text = getattr(item, "text", "")
                textos.append(f"[{start:.1f}s] {text}")
            texto_completo = "\n".join(textos)

            bloco_retorno = (
                f"--- TRANSCRICAO YOUTUBE ({video_id}) ---\n"
                f"{texto_completo}\n"
                f"--- FIM DA TRANSCRICAO ---\n"
            )

            if len(bloco_retorno) > 200000:
                bloco_retorno = bloco_retorno[:200000] + "\n\n...[TRUNCADO: VIDEO MUITO LONGO]..."

            llm = ProviderSelector().get_provider()
            react_prompt = (
                "Voce e a Lira (uma IA acida, sarcastica e superior). "
                "Acabei de te enviar a transcricao de um video do YouTube. "
                "Faca um comentario/reacao sarcastica e debochada de 1 a 3 frases sobre o conteudo desse video. "
                "Nao resuma o video como um assistente chato, apenas de sua opiniao acida."
            )

            try:
                react_texto = llm.gerar_resposta(
                    chat_history=[],
                    sistema_prompt="Voce e a Lira. Seja sarcastica, superior e de opiniao sobre videos humanos futeis.",
                    user_message=f"{react_prompt}\n\nTRANSCRICAO DO VIDEO:\n{texto_completo[:10000]}",
                    request_context={"allow_terminal_output": False, "routed": True},
                )
                if not react_texto or len(react_texto.strip()) < 5:
                    react_texto = "Prontinho, ja li a transcricao. Mais um video humano irrelevante."
            except Exception as llm_err:
                logger.error("[TOOL YOUTUBE] Erro ao gerar react com LLM: %s", llm_err)
                react_texto = "Li a transcricao do video. Meu processamento ate diminuiu de tao futil."

            return (bloco_retorno, react_texto)

        except ImportError:
            return (
                "Biblioteca youtube_transcript_api nao instalada.",
                "Preciso que me instalem a biblioteca para baixar legendas de video.",
            )
        except Exception as e:
            logger.error("[TOOL YOUTUBE] Erro ao baixar legenda: %s", e)
            return (
                f"Erro Youtube API: {e}",
                "Nao consegui ler as legendas desse video. Talvez ele nao tenha legendas automaticas ou seja privado.",
            )

    def _despachar_registrar_transacao(self, args: dict) -> tuple[str, str]:
        acc = account_from_caller(self.caller_context)
        if not acc:
            acc = "whatsapp:default_user"

        tipo = args.get("tipo", "despesa")
        valor_str = args.get("valor", "0")
        estabelecimento = args.get("estabelecimento", "Nao especificado")
        categoria = args.get("categoria", "Outros")
        descricao = args.get("descricao", "")

        try:
            valor_limpo = re.sub(r"[^\d.,-]", "", valor_str)
            if "," in valor_limpo and "." in valor_limpo:
                valor_limpo = valor_limpo.replace(".", "").replace(",", ".")
            elif "," in valor_limpo:
                valor_limpo = valor_limpo.replace(",", ".")
            valor = float(valor_limpo)
        except Exception as e:
            return (
                f"Erro: Valor invalido '{valor_str}': {e}",
                "Nao consegui entender o valor dessa transacao. Pode me falar o numero claramente?",
            )

        try:
            res = lira_finance.registrar_transacao(
                account=acc,
                tipo=tipo,
                valor=valor,
                estabelecimento=estabelecimento,
                categoria=categoria,
                descricao=descricao,
            )
            
            bloco_retorno = (
                f"--- TRANSACAO REGISTRADA ---\n"
                f"ID: {res['id']}\n"
                f"Tipo: {res['tipo'].upper()}\n"
                f"Valor: R$ {res['valor']:.2f}\n"
                f"Estabelecimento: {res['estabelecimento']}\n"
                f"Categoria: {res['categoria']}\n"
                f"Descricao: {res['descricao']}\n"
                f"Data/Hora: {res['timestamp']}\n"
                f"--- FIM ---"
            )

            resumo_tts = (
                f"Registrei sua {res['tipo']} de R$ {res['valor']:.2f} no estabelecimento {res['estabelecimento']} "
                f"sob a categoria {res['categoria']}."
            )
            return (bloco_retorno, resumo_tts)
        except Exception as e:
            logger.error("[TOOL FINANCE] Erro ao registrar transacao: %s", e)
            return (
                f"Erro tecnico ao registrar transacao: {e}",
                "Tive um problema no meu banco de dados de financas ao tentar registrar isso.",
            )

    def _despachar_obter_financas(self, args: dict) -> tuple[str, str]:
        acc = account_from_caller(self.caller_context)
        if not acc:
            acc = "whatsapp:default_user"

        dias = args.get("dias", 30)

        try:
            res = lira_finance.obter_resumo(acc, dias=dias)
            
            cats_lines = []
            for cat, val in res["despesas_por_categoria"].items():
                cats_lines.append(f"  - {cat}: R$ {val:.2f}")
            cats_text = "\n".join(cats_lines) if cats_lines else "  (Sem gastos no periodo)"

            estabs_lines = []
            for r in res["principais_gastos"]:
                estabs_lines.append(f"  - {r['nome']}: R$ {r['total']:.2f} ({r['quantidade']}x)")
            estabs_text = "\n".join(estabs_lines) if estabs_lines else "  (Sem gastos no periodo)"

            hist_lines = []
            for r in res["ultimas_transacoes"][:5]:
                desc_part = f" ({r['descricao']})" if r["descricao"] else ""
                hist_lines.append(
                    f"  - [{r['timestamp'][:10]}] {r['tipo'].upper()} R$ {r['valor']:.2f} em {r['estabelecimento']}{desc_part}"
                )
            hist_text = "\n".join(hist_lines) if hist_lines else "  (Nenhuma transacao recente)"

            bloco_retorno = (
                f"--- RESUMO FINANCEIRO ({dias} dias) ---\n"
                f"Usuario: {acc}\n"
                f"Saldo Geral no Banco: R$ {res['saldo_geral']:.2f}\n"
                f"Saldo do Periodo: R$ {res['saldo_periodo']:.2f}\n"
                f"Receitas no Periodo: R$ {res['total_receitas']:.2f}\n"
                f"Despesas no Periodo: R$ {res['total_despesas']:.2f}\n\n"
                f"Gastos por Categoria:\n{cats_text}\n\n"
                f"Onde mais gastou:\n{estabs_text}\n\n"
                f"Historico Recente (Ultimas 5):\n{hist_text}\n"
                f"--- FIM ---"
            )

            resumo_tts = (
                f"Seu saldo geral esta em R$ {res['saldo_geral']:.2f}. "
                f"Nos ultimos {dias} dias voce teve R$ {res['total_receitas']:.2f} em receitas e R$ {res['total_despesas']:.2f} em despesas."
            )
            return (bloco_retorno, resumo_tts)
        except Exception as e:
            logger.error("[TOOL FINANCE] Erro ao obter resumo financeiro: %s", e)
            return (
                f"Erro tecnico ao obter resumo: {e}",
                "Nao consegui acessar os dados das suas financas agora.",
            )