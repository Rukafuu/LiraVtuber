import logging
import re
from typing import List, Dict, Any
from src.memory.memory import memory as SQLiteMemory
from src.memory.rag_engine import HanaRAGEngine
from src.memory.knowledge_graph import HanaKnowledgeGraph

logger = logging.getLogger(__name__)

class HanaMemoryManager:
    def __init__(self, db_path: str = "data/hana_memory.db"):
        # Camada 1: Curto Prazo (Existente)
        self.sqlite = SQLiteMemory(db_path)
        
        # Camada 2: Semântica (Busca Vetorial)
        self.rag = HanaRAGEngine()
        
        # Camada 3: Lógica (Grafo de Conhecimento)
        self.graph = HanaKnowledgeGraph()
        
        logger.info("[MEMORY MANAGER] Sistema de memória híbrida inicializado.")

    # Padrões de extração automática de fatos (PT-BR)
    FACT_PATTERNS = [
        # "meu nome é X" / "me chamo X"
        (r"(?:meu nome (?:é|eh)|me chamo|pode me chamar de)\s+(\S+)", "nakamura", "tem_nome", 1),
        # "eu gosto de X" / "adoro X" / "amo X"  
        (r"(?:eu (?:gosto|adoro|amo|curto) (?:de |muito (?:de )?)?)(.+?)(?:\.|,|!|$)", "nakamura", "gosta_de", 1),
        # "eu moro em X" / "sou de X"
        (r"(?:eu moro em|moro em|sou de|vivo em)\s+(.+?)(?:\.|,|!|$)", "nakamura", "mora_em", 1),
        # "meu aniversário é X" / "nasci em X"
        (r"(?:meu anivers[aá]rio (?:é|eh)|nasci (?:em|dia)|fa[cç]o anivers[aá]rio (?:em |dia )?)\s*(.+?)(?:\.|,|!|$)", "nakamura", "aniversario_em", 1),
        # "minha cor favorita é X"
        (r"minha cor favorita (?:é|eh)\s+(.+?)(?:\.|,|!|$)", "nakamura", "cor_favorita", 1),
        # "meu pet se chama X" / "meu gato é X"
        (r"(?:meu (?:pet|gato|cachorro|cão) (?:se chama|é|eh)|tenho um (?:gato|cachorro) chamado)\s+(.+?)(?:\.|,|!|$)", "nakamura", "pet_nome", 1),
    ]

    def add_interaction(self, role: str, content: str):
        """Salva a interação em todas as camadas apropriadas."""
        # Salva no Histórico Cronológico (SQLite)
        self.sqlite.add_message(role, content)
        
        # Salva na Memória Semântica (RAG) para recuperação futura
        if role.lower() != "system":
            self.rag.add_memory(content, metadata={"role": role})
        
        # Extração automática de fatos do texto do usuário
        if role.lower() in ("nakamura", "user"):
            self._extrair_fatos_auto(content)
            
        logger.debug(f"[MEMORY MANAGER] Interação salva para {role}.")

    def _extrair_fatos_auto(self, text: str):
        """Extrai fatos automaticamente do texto do usuário usando padrões."""
        text_lower = text.lower().strip()
        
        # 1. Padrões estruturados (nome, gosto, cidade, etc.)
        for pattern, subject, relation, group_idx in self.FACT_PATTERNS:
            match = re.search(pattern, text_lower, re.IGNORECASE)
            if match:
                value = match.group(group_idx).strip()
                if len(value) > 1 and len(value) < 100:
                    self.graph.add_fact(subject, relation, value)
                    logger.info(f"[MEMORY MANAGER] Fato extraído: {subject} --[{relation}]--> {value}")
        
        # 2. Comando explícito de "decore/guarda/lembra/anota"
        # Para esses, capturamos a mensagem INTEIRA como contexto
        decore_trigger = re.search(
            r"(?:guarda|decore|lembr[ae]|anot[ae]|memoriz[ae]|nunca esquec[ea]|salv[ae]|grav[ae])",
            text_lower
        )
        if decore_trigger:
            # Procura números na mensagem
            numeros = re.findall(r"\b\d{2,}\b", text)
            for num in numeros:
                self.graph.add_fact("nakamura", "número_importante", num)
                logger.info(f"[MEMORY MANAGER] Número memorizado: {num}")
            
            # Se não encontrou números, salva o conteúdo relevante
            if not numeros:
                # Remove a parte do comando e salva o restante
                conteudo = re.sub(
                    r".*?(?:guarda|decore|lembr[ae]|anot[ae]|memoriz[ae]|nunca esquec[ea]|salv[ae]|grav[ae])[\s,.:]*(?:que|isso|esse|essa|este)?[\s,.:]*",
                    "", text_lower, count=1
                ).strip()
                if len(conteudo) > 3:
                    self.graph.add_fact("hana_nota", "deve_lembrar", conteudo)
                    logger.info(f"[MEMORY MANAGER] Nota memorizada: {conteudo}")

    def get_context(self, user_query: str, recent_limit: int = 100) -> str:
        """
        Gera o contexto completo para o LLM combinando as 3 camadas.
        """
        # 1. Busca Semântica (RAG) - O que conversamos antes sobre isso?
        sem_context = self.rag.get_context_string(user_query)
        
        # 2. Busca no Grafo - Fatos estruturados relacionados às entidades citadas
        potential_entities = self._extrair_entidades(user_query)
        graph_context = self.graph.get_graph_context_string(potential_entities)
        
        # Combina tudo
        combined_context = f"{sem_context}{graph_context}"
        return combined_context

    def _extrair_entidades(self, text: str) -> list:
        """
        Extrai entidades do texto para buscar no grafo.
        Combina: palavras capitalizadas + busca por nós existentes no grafo.
        """
        entities = set()
        
        # Método 1: Palavras com letra maiúscula (nomes próprios)
        capitalized = re.findall(r"\b[A-Z][a-zà-ú0-9]+\b", text)
        entities.update(capitalized)
        
        # Método 2: Busca por nós conhecidos no grafo dentro do texto
        # Isso garante que "qual meu número da sorte?" encontre "número da sorte"
        text_lower = text.lower()
        for node in self.graph.graph.nodes():
            if node in text_lower:
                entities.add(node)
        
        return list(entities)

    def add_fact(self, s, r, o):
        """Atalho para adicionar fatos permanentes ao grafo."""
        self.graph.add_fact(s, r, o)

    def get_messages(self, limit: int = 100):
        """Retorna o histórico recente do SQLite."""
        return self.sqlite.get_messages(limit)
