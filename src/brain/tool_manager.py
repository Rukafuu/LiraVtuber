import logging
import os

from tavily import TavilyClient

from src.config.config_loader import CONFIG

logger = logging.getLogger(__name__)

FERRAMENTAS = [
    {
        "type": "function",
        "function": {
            "name": "pesquisar_na_web",
            "description": (
                "Busca fatos em tempo real na internet. Use esta ferramenta somente quando "
                "o usuario pedir explicitamente para pesquisar, buscar, verificar online ou "
                "consultar a web. Se houver duvida, pergunte antes e nao pesquise automaticamente."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "O termo de pesquisa otimizado em Ingles (Software/Hardware) "
                            "ou Portugues (Assuntos Globais)."
                        ),
                    }
                },
                "required": ["query"],
            },
        },
    },
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
        if nome_tool == "pesquisar_na_web":
            return self._despachar_pesquisa(args)
        
        if nome_tool == "anotar_fato":
            return self._despachar_anotacao(args)

        logger.warning(f"[TOOL MANAGER] Tool desconhecida: {nome_tool}")
        return ("Menu_Tool nao reconhecida pelo sistema.", "Nao reconheci essa acao.")

    def _despachar_pesquisa(self, args: dict) -> tuple:
        query = args.get("query", "")
        logger.info(f"[TOOL] Pesquisa: {query}")

        api_key = os.getenv("TAVILY_API_KEY") or CONFIG.get("TAVILY_API_KEY")
        if not api_key:
            logger.error("[TOOL] TAVILY_API_KEY nao encontrada.")
            return (
                "Erro: TAVILY_API_KEY nao configurada.",
                "Nao consigo pesquisar sem a TAVILY_API_KEY.",
            )

        try:
            client = TavilyClient(api_key=api_key)
            resposta = client.search(
                query=query,
                search_depth="advanced",
                include_raw_content=True,
                max_results=3,
            )

            resultados = []
            for item in resposta.get("results", []):
                titulo = item.get("title", "Sem titulo")
                url = item.get("url", "#")
                conteudo = item.get("raw_content") or item.get("content") or "Conteudo indisponivel."
                bloco = f"--- FONTE: {titulo} ({url}) ---\n{conteudo}\n"
                resultados.append(bloco)

            if not resultados:
                return (
                    "Nenhum resultado encontrado.",
                    "Procurei, mas nao encontrei nada relevante.",
                )

            string_gigante = "\n".join(resultados)
            max_chars = 15000
            if len(string_gigante) > max_chars:
                string_gigante = string_gigante[:max_chars] + "\n\n...[TRUNCADO]..."

            return (string_gigante, f"Pesquisando na web sobre {query}.")
        except Exception as e:
            logger.error(f"[TOOL] Erro na pesquisa Tavily: {e}")
            return (
                f"Erro na API Tavily: {str(e)}",
                "A pesquisa na web falhou.",
            )

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
