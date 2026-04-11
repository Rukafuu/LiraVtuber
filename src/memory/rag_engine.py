import json
import logging
import os
import re
from difflib import SequenceMatcher
from typing import Any, Dict, List

import chromadb
from chromadb.utils import embedding_functions

logger = logging.getLogger(__name__)


class HanaRAGEngine:
    # Tamanho minimo para armazenar (evita salvar "Oi", "Ok", etc.)
    MIN_TEXT_LENGTH = 15
    # Distancia maxima aceitavel (cosine distance: 0=identico, 2=oposto).
    MAX_DISTANCE = 0.55

    def __init__(self, persist_directory: str = "data/memory/chroma_db"):
        self.persist_directory = persist_directory
        self.os_path = os.path.abspath(self.persist_directory)
        self.client = None
        self.collection = None
        self.embedding_fn = None
        self.model_name = "paraphrase-multilingual-MiniLM-L12-v2"
        self.fallback_store_path = os.path.join(self.os_path, "fallback_memories.json")
        self._fallback_entries: dict[str, dict[str, Any]] = {}

        if not os.path.exists(self.os_path):
            os.makedirs(self.os_path)

        self._load_fallback_entries()
        logger.info("[RAG ENGINE] Inicializando ChromaDB em: %s", self.os_path)

        # Se embeddings/download/cache falharem, mantemos o app vivo com um
        # fallback lexical persistido no disco.
        try:
            self.client = chromadb.PersistentClient(path=self.os_path)
            self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=self.model_name
            )
            self.collection = self.client.get_or_create_collection(
                name="hana_memories",
                embedding_function=self.embedding_fn,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info("[RAG ENGINE] ChromaDB pronto com embeddings SentenceTransformer.")
        except Exception as exc:
            self.client = None
            self.collection = None
            self.embedding_fn = None
            logger.warning(
                "[RAG ENGINE] ChromaDB/embeddings indisponiveis. Usando fallback lexical em %s. Motivo: %s",
                self.fallback_store_path,
                exc,
            )

    def _load_fallback_entries(self):
        if not os.path.exists(self.fallback_store_path):
            self._fallback_entries = {}
            return

        try:
            if os.path.getsize(self.fallback_store_path) == 0:
                self._fallback_entries = {}
                return
            with open(self.fallback_store_path, "r", encoding="utf-8") as file:
                payload = json.load(file)
            if not isinstance(payload, list):
                self._fallback_entries = {}
                return
            self._fallback_entries = {
                str(item.get("id")): {
                    "id": str(item.get("id")),
                    "text": str(item.get("text", "")),
                    "metadata": item.get("metadata") if isinstance(item.get("metadata"), dict) else {},
                }
                for item in payload
                if item.get("id") and item.get("text")
            }
        except Exception as exc:
            logger.warning("[RAG ENGINE] Falha ao carregar fallback lexical: %s", exc)
            self._fallback_entries = {}

    def _save_fallback_entries(self):
        try:
            payload = list(self._fallback_entries.values())
            temp_path = f"{self.fallback_store_path}.tmp"
            with open(temp_path, "w", encoding="utf-8") as file:
                json.dump(payload, file, ensure_ascii=False, indent=2)
            os.replace(temp_path, self.fallback_store_path)
        except Exception as exc:
            logger.error("[RAG ENGINE] Falha ao salvar fallback lexical: %s", exc)

    def _fallback_upsert(self, mem_id: str, text: str, metadata: Dict[str, Any] | None = None):
        self._fallback_entries[mem_id] = {
            "id": mem_id,
            "text": text,
            "metadata": metadata or {"source": "chat"},
        }
        self._save_fallback_entries()

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        return set(re.findall(r"\w+", (text or "").lower(), flags=re.UNICODE))

    def _fallback_query(self, query_text: str, n_results: int = 5) -> List[tuple[str, float]]:
        query_clean = (query_text or "").strip().lower()
        if not query_clean:
            return []

        query_tokens = self._tokenize(query_clean)
        ranked: list[tuple[str, float]] = []

        for entry in self._fallback_entries.values():
            doc_text = str(entry.get("text", ""))
            doc_clean = doc_text.lower()
            doc_tokens = self._tokenize(doc_clean)

            overlap = (len(query_tokens & doc_tokens) / len(query_tokens)) if query_tokens else 0.0
            ratio = SequenceMatcher(None, query_clean, doc_clean).ratio()
            contains_bonus = 0.25 if query_clean in doc_clean else 0.0
            score = min(1.0, max(overlap, ratio * 0.8) + contains_bonus)
            distance = 1.0 - score

            if score > 0:
                ranked.append((doc_text, distance))

        ranked.sort(key=lambda item: item[1])
        return ranked[:n_results]

    def add_memory(self, text: str, metadata: Dict[str, Any] = None):
        """Adiciona uma nova memoria ao banco vetorial com ID automatico."""
        if not text.strip() or len(text.strip()) < self.MIN_TEXT_LENGTH:
            return

        import uuid

        mem_id = str(uuid.uuid4())
        self.upsert_memory(mem_id, text, metadata)

    def upsert_memory(self, mem_id: str, text: str, metadata: Dict[str, Any] = None):
        """Atualiza ou insere uma memoria especifica com ID fixo."""
        if not text.strip() or len(text.strip()) < self.MIN_TEXT_LENGTH:
            return

        if self.collection is None:
            self._fallback_upsert(mem_id, text, metadata)
            return

        try:
            self.collection.upsert(
                documents=[text],
                metadatas=[metadata] if metadata else [{"source": "chat"}],
                ids=[mem_id],
            )
            logger.debug("[RAG ENGINE] Memoria upserted (ID: %s): %s...", mem_id, text[:50])
        except Exception as exc:
            logger.error("[RAG ENGINE] Erro no upsert_memory: %s", exc)
            self._fallback_upsert(mem_id, text, metadata)

    def query_memories(self, query_text: str, n_results: int = 5, max_distance: float = None) -> List[str]:
        """Busca memorias relacionadas ao texto fornecido."""
        if not query_text.strip() or len(query_text.strip()) < 3:
            return []

        if max_distance is None:
            max_distance = self.MAX_DISTANCE

        if self.collection is None:
            return [doc for doc, dist in self._fallback_query(query_text, n_results) if dist <= max_distance]

        try:
            results = self.collection.query(
                query_texts=[query_text],
                n_results=n_results,
                include=["documents", "distances"],
            )

            documents = results.get("documents", [[]])[0]
            distances = results.get("distances", [[]])[0]

            filtered = []
            for doc, dist in zip(documents, distances):
                if dist <= max_distance:
                    filtered.append(doc)

            return filtered
        except Exception as exc:
            logger.error("[RAG ENGINE] Erro na consulta RAG: %s", exc)
            return [doc for doc, dist in self._fallback_query(query_text, n_results) if dist <= max_distance]

    def query_memories_with_scores(self, query_text: str, n_results: int = 5) -> List[tuple]:
        """Retorna memorias com scores para exibicao na GUI."""
        if not query_text.strip() or len(query_text.strip()) < 3:
            return []

        if self.collection is None:
            return self._fallback_query(query_text, n_results)

        try:
            results = self.collection.query(
                query_texts=[query_text],
                n_results=n_results,
                include=["documents", "distances"],
            )

            documents = results.get("documents", [[]])[0]
            distances = results.get("distances", [[]])[0]

            return [(doc, dist) for doc, dist in zip(documents, distances)]
        except Exception as exc:
            logger.error("[RAG ENGINE] Erro na consulta RAG: %s", exc)
            return self._fallback_query(query_text, n_results)

    def get_context_string(self, query_text: str, n_results: int = 3) -> str:
        """Retorna uma string formatada com as memorias recuperadas."""
        memories = self.query_memories(query_text, n_results)
        if not memories:
            return ""

        context = "\n".join([f"- {memory}" for memory in memories])
        return f"\n=== MEMORIAS RECUPERADAS (CONTEXTO ANTIGO) ===\n{context}\n"
