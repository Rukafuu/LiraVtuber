import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List

from src.memory.knowledge_graph import HanaKnowledgeGraph
from src.memory.memory import memory as SQLiteMemory
from src.memory.rag_engine import HanaRAGEngine
from src.utils.hana_tags import sanitize_history_message

logger = logging.getLogger(__name__)


class HanaMemoryManager:
    def __init__(self, db_path: str = "data/hana_memory.db"):
        # Camada 1: Curto Prazo (Existente)
        self.sqlite = SQLiteMemory(db_path)

        # Camada 2: Semantica (Busca Vetorial)
        self.rag = HanaRAGEngine()

        # Camada 3: Logica (Grafo de Conhecimento)
        self.graph = HanaKnowledgeGraph()

        # Sincroniza os fatos permanentes na base de dados de vetores
        self._sincronizar_grafo_rag()

        logger.info("[MEMORY MANAGER] Sistema de memoria hibrida inicializado.")

    def _sincronizar_grafo_rag(self):
        """Itera os nos do grafo atual e injeta no RAG (com Upsert) para busca vetorial livre."""
        count = 0
        import hashlib

        for s, o, data in self.graph.graph.edges(data=True):
            r = data.get("relation", "?").replace("_", " ")
            frase = f"O {s} tem {r} como {o}."
            # Cria ID baseado nas chaves unicas do fato para nao duplicar no RAG
            mem_id = hashlib.md5(f"{s}{r}{o}".encode("utf-8")).hexdigest()
            self.rag.upsert_memory(mem_id, frase, metadata={"source": "knowledge_graph"})
            count += 1
        if count > 0:
            logger.info(f"[MEMORY MANAGER] {count} fatos do Grafo foram sincronizados com o RAG.")

    # Padroes de extracao automatica de fatos (PT-BR)
    FACT_PATTERNS = [
        # "meu nome e X" / "me chamo X"
        (r"(?:meu nome (?:e|eh)|me chamo|pode me chamar de)\s+(\S+)", "nakamura", "tem_nome", 1),
        # "eu gosto de X" / "adoro X" / "amo X"
        (r"(?:eu (?:gosto|adoro|amo|curto) (?:de |muito (?:de )?)?)(.+?)(?:\.|,|!|$)", "nakamura", "gosta_de", 1),
        # "eu moro em X" / "sou de X"
        (r"(?:eu moro em|moro em|sou de|vivo em)\s+(.+?)(?:\.|,|!|$)", "nakamura", "mora_em", 1),
        # "meu aniversario e X" / "nasci em X"
        (r"(?:meu anivers[aá]rio (?:e|eh)|nasci (?:em|dia)|fa[cç]o anivers[aá]rio (?:em |dia )?)\s*(.+?)(?:\.|,|!|$)", "nakamura", "aniversario_em", 1),
        # "minha cor favorita e X"
        (r"minha cor favorita (?:e|eh)\s+(.+?)(?:\.|,|!|$)", "nakamura", "cor_favorita", 1),
        # "meu pet se chama X" / "meu gato e X"
        (r"(?:meu (?:pet|gato|cachorro|cao) (?:se chama|e|eh)|tenho um (?:gato|cachorro) chamado)\s+(.+?)(?:\.|,|!|$)", "nakamura", "pet_nome", 1),
    ]

    def add_interaction(self, role: str, content: str):
        """Salva a interacao em todas as camadas apropriadas."""
        clean_content = sanitize_history_message(role, content)
        if not clean_content:
            logger.debug("[MEMORY MANAGER] Interacao vazia ignorada para %s.", role)
            return

        # Salva no Historico Cronologico (SQLite)
        self.sqlite.add_message(role, clean_content)

        # Salva na Memoria Semantica (RAG) para recuperacao futura
        if role.lower() != "system":
            self.rag.add_memory(clean_content, metadata={"role": role})

        # Extracao automatica de fatos do texto do usuario
        if role.lower() in ("nakamura", "user"):
            self._extrair_fatos_auto(clean_content)

        logger.debug("[MEMORY MANAGER] Interacao salva para %s.", role)

    def _extrair_fatos_auto(self, text: str):
        """Extrai fatos automaticamente do texto do usuario usando padroes."""
        text_lower = text.lower().strip()

        # 1. Padroes estruturados (nome, gosto, cidade, etc.)
        for pattern, subject, relation, group_idx in self.FACT_PATTERNS:
            match = re.search(pattern, text_lower, re.IGNORECASE)
            if match:
                value = match.group(group_idx).strip()
                if 1 < len(value) < 100:
                    self.add_fact(subject, relation, value)
                    logger.info(f"[MEMORY MANAGER] Fato extraido: {subject} --[{relation}]--> {value}")

        # 2. Comando explicito de "decore/guarda/lembra/anota"
        # Para esses, capturamos a mensagem INTEIRA como contexto
        decore_trigger = re.search(
            r"(?:guarda|decore|lembr[ae]|anot[ae]|memoriz[ae]|nunca esquec[ea]|salv[ae]|grav[ae])",
            text_lower,
        )
        if decore_trigger:
            # Procura numeros na mensagem
            numeros = re.findall(r"\b\d{2,}\b", text)
            for num in numeros:
                self.add_fact("nakamura", "numero_importante", num)
                logger.info(f"[MEMORY MANAGER] Numero memorizado: {num}")

            # Se nao encontrou numeros, salva o conteudo relevante
            if not numeros:
                # Remove a parte do comando e salva o restante
                conteudo = re.sub(
                    r".*?(?:guarda|decore|lembr[ae]|anot[ae]|memoriz[ae]|nunca esquec[ea]|salv[ae]|grav[ae])[\s,.:]*(?:que|isso|esse|essa|este)?[\s,.:]*",
                    "",
                    text_lower,
                    count=1,
                ).strip()
                if len(conteudo) > 3:
                    self.add_fact("hana_nota", "deve_lembrar", conteudo)
                    logger.info(f"[MEMORY MANAGER] Nota memorizada: {conteudo}")

    def get_context(self, user_query: str, recent_limit: int = 100):
        """
        Gera o contexto completo para o LLM combinando as 3 camadas.
        """
        # 1. Busca Semantica (RAG) - O que conversamos antes sobre isso?
        sem_context = self.rag.get_context_string(user_query)

        # 2. Busca no Grafo - Fatos estruturados relacionados as entidades citadas
        potential_entities = self._extrair_entidades(user_query)
        graph_context = self.graph.get_graph_context_string(potential_entities)

        # Combina tudo
        combined_context = f"{sem_context}{graph_context}"
        return combined_context

    def _extrair_entidades(self, text: str) -> list:
        """
        Extrai entidades do texto para buscar no grafo.
        Combina: palavras capitalizadas + busca por nos existentes no grafo.
        """
        entities = set()

        # Metodo 1: Palavras com letra maiuscula (nomes proprios)
        capitalized = re.findall(r"\b[A-Z][a-zà-ú0-9]+\b", text)
        entities.update(capitalized)

        # Metodo 2: Busca por nos conhecidos no grafo dentro do texto
        # Isso garante que "qual meu numero da sorte?" encontre "numero da sorte"
        text_lower = text.lower()
        for node in self.graph.graph.nodes():
            if node in text_lower:
                entities.add(node)

        # Metodo 3: resolve perguntas em primeira pessoa para o usuario principal
        if re.search(r"\b(eu|meu|minha|meus|minhas|mim)\b", text_lower):
            for alias in ("nakamura", "criador", "mestre", "usuario", "usuário", "user"):
                if alias in self.graph.graph.nodes():
                    entities.add(alias)
            if not any(alias in entities for alias in ("nakamura", "criador", "mestre", "usuario", "usuário", "user")):
                entities.add("nakamura")

        # Metodo 4: resolve perguntas sobre a propria Hana
        if re.search(r"\b(voc[eê]|vc|hana)\b", text_lower):
            if "hana" in self.graph.graph.nodes():
                entities.add("hana")

        return list(entities)

    def add_fact(self, s, r, o):
        """Atalho para adicionar fatos permanentes ao grafo e ao RAG."""
        self.graph.add_fact(s, r, o)

        import hashlib

        r_limpo = r.replace("_", " ")
        frase = f"O {s} tem {r_limpo} como {o}."
        mem_id = hashlib.md5(f"{s}{r}{o}".encode("utf-8")).hexdigest()
        self.rag.upsert_memory(mem_id, frase, metadata={"source": "knowledge_graph"})

    def get_messages(self, limit: int = 100):
        """Retorna o historico recente do SQLite."""
        mensagens = []
        for msg in self.sqlite.get_messages(limit):
            role = msg.get("role", "")
            content = sanitize_history_message(role, msg.get("content", ""))
            if not content:
                continue
            mensagens.append({"role": role, "content": content})
        return mensagens

    def get_terminal_context_state(self, history_limit: int = 30, stale_after_minutes: int = 45):
        """Retorna historico seguro para voz e um resumo temporal da ultima interacao."""
        messages = self.sqlite.get_messages(history_limit, include_timestamp=True)
        now_utc = datetime.now(timezone.utc)
        last_timestamp = None
        last_role = ""

        if messages:
            last = messages[-1]
            last_role = str(last.get("role", ""))
            try:
                parsed = datetime.strptime(str(last.get("timestamp")), "%Y-%m-%d %H:%M:%S")
                last_timestamp = parsed.replace(tzinfo=timezone.utc)
            except Exception:
                last_timestamp = None

        elapsed_minutes = None
        is_stale = False
        if last_timestamp is not None:
            elapsed_minutes = max(0, int((now_utc - last_timestamp).total_seconds() // 60))
            is_stale = elapsed_minutes >= stale_after_minutes

        safe_history = [] if is_stale else [
            {"role": msg.get("role", ""), "content": sanitize_history_message(msg.get("role", ""), msg.get("content", ""))}
            for msg in messages
            if sanitize_history_message(msg.get("role", ""), msg.get("content", ""))
        ]

        if elapsed_minutes is None:
            timing_text = "Sem interacao anterior registrada nesta memoria cronologica."
        elif elapsed_minutes < 1:
            timing_text = f"A ultima interacao foi agora ha menos de 1 minuto. Ultimo autor: {last_role}."
        elif elapsed_minutes < 60:
            timing_text = f"A ultima interacao foi ha {elapsed_minutes} minutos. Ultimo autor: {last_role}."
        else:
            hours = elapsed_minutes // 60
            minutes = elapsed_minutes % 60
            timing_text = f"A ultima interacao foi ha {hours}h{minutes:02d}. Ultimo autor: {last_role}."

        if is_stale:
            timing_text += " Houve pausa longa: trate a mensagem atual como novo contexto e nao continue tarefas antigas sem pedido explicito."

        return {
            "history": safe_history,
            "timing_text": timing_text,
            "elapsed_minutes": elapsed_minutes,
            "is_stale": is_stale,
        }
