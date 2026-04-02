import os
import logging
from typing import List, Dict, Any
import chromadb
from chromadb.utils import embedding_functions
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

class HanaRAGEngine:
    def __init__(self, persist_directory: str = "data/memory/chroma_db"):
        self.persist_directory = persist_directory
        self.os_path = os.path.abspath(self.persist_directory)
        
        if not os.path.exists(self.os_path):
            os.makedirs(self.os_path)
            
        logger.info(f"[RAG ENGINE] Inicializando ChromaDB em: {self.os_path}")
        
        self.client = chromadb.PersistentClient(path=self.os_path)
        
        # Usando um modelo multilingue excelente para Português
        # O modelo será baixado na primeira execução (~100MB)
        self.model_name = "paraphrase-multilingual-MiniLM-L12-v2"
        
        # Configura a função de embedding para o ChromaDB
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=self.model_name
        )
        
        # Cria ou obtém a coleção de memórias da Hana
        self.collection = self.client.get_or_create_collection(
            name="hana_memories",
            embedding_function=self.embedding_fn,
            metadata={"hnsw:space": "cosine"}
        )

    # Tamanho mínimo para armazenar (evita salvar "Oi", "Ok", etc.)
    MIN_TEXT_LENGTH = 15
    # MAX_DISTANCE: Distância máxima aceitável (cosine distance: 0=idêntico, 2=oposto)
    # Aumentado para 0.55 para permitir correspondência de fatos com palavras ligeiramente diferentes.
    MAX_DISTANCE = 0.55

    def add_memory(self, text: str, metadata: Dict[str, Any] = None):
        """Adiciona uma nova memória ao banco vetorial com ID automático."""
        if not text.strip() or len(text.strip()) < self.MIN_TEXT_LENGTH:
            return
            
        import uuid
        mem_id = str(uuid.uuid4())
        self.upsert_memory(mem_id, text, metadata)

    def upsert_memory(self, mem_id: str, text: str, metadata: Dict[str, Any] = None):
        """Atualiza ou insere uma memória específica com ID fixo."""
        if not text.strip() or len(text.strip()) < self.MIN_TEXT_LENGTH:
            return
            
        try:
            self.collection.upsert(
                documents=[text],
                metadatas=[metadata] if metadata else [{"source": "chat"}],
                ids=[mem_id]
            )
            logger.debug(f"[RAG ENGINE] Memória upserted (ID: {mem_id}): {text[:50]}...")
        except Exception as e:
            logger.error(f"[RAG ENGINE] Erro no upsert_memory: {e}")

    def query_memories(self, query_text: str, n_results: int = 5, max_distance: float = None) -> List[str]:
        """
        Busca memórias relacionadas ao texto fornecido.
        Filtra resultados com distância acima de max_distance (padrão MemOS).
        """
        if not query_text.strip() or len(query_text.strip()) < 3:
            return []
        
        if max_distance is None:
            max_distance = self.MAX_DISTANCE
            
        try:
            results = self.collection.query(
                query_texts=[query_text],
                n_results=n_results,
                include=["documents", "distances"]
            )
            
            documents = results.get("documents", [[]])[0]
            distances = results.get("distances", [[]])[0]
            
            # Filtra: só retorna resultados com distância abaixo do threshold
            filtered = []
            for doc, dist in zip(documents, distances):
                if dist <= max_distance:
                    filtered.append(doc)
            
            return filtered
        except Exception as e:
            logger.error(f"[RAG ENGINE] Erro na consulta RAG: {e}")
            return []

    def query_memories_with_scores(self, query_text: str, n_results: int = 5) -> List[tuple]:
        """Retorna memórias COM scores para exibição na GUI."""
        if not query_text.strip() or len(query_text.strip()) < 3:
            return []
            
        try:
            results = self.collection.query(
                query_texts=[query_text],
                n_results=n_results,
                include=["documents", "distances"]
            )
            
            documents = results.get("documents", [[]])[0]
            distances = results.get("distances", [[]])[0]
            
            return [(doc, dist) for doc, dist in zip(documents, distances)]
        except Exception as e:
            logger.error(f"[RAG ENGINE] Erro na consulta RAG: {e}")
            return []

    def get_context_string(self, query_text: str, n_results: int = 3) -> str:
        """Retorna uma string formatada com as memórias recuperadas (filtradas)."""
        memories = self.query_memories(query_text, n_results)
        if not memories:
            return ""
            
        context = "\n".join([f"- {m}" for m in memories])
        return f"\n=== MEMÓRIAS RECUPERADAS (CONTEXTO ANTIGO) ===\n{context}\n"
