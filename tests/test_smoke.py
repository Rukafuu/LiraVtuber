from chromadb.utils import embedding_functions

from src.memory.rag_engine import HanaRAGEngine


def test_rag_engine_fallback_roundtrip(monkeypatch, tmp_path):
    def raise_embedding_error(*_args, **_kwargs):
        raise RuntimeError("embedding unavailable for test")

    monkeypatch.setattr(
        embedding_functions,
        "SentenceTransformerEmbeddingFunction",
        raise_embedding_error,
    )

    engine = HanaRAGEngine(persist_directory=str(tmp_path / "chroma"))
    engine.upsert_memory(
        "cat-memory",
        "Meu gato Mimi dorme na janela da sala toda tarde.",
        {"source": "test"},
    )

    results = engine.query_memories("gato mimi janela", n_results=3)

    assert results
    assert any("Mimi" in item for item in results)
