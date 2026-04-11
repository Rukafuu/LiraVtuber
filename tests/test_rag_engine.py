from pathlib import Path

import src.memory.rag_engine as rag_module
from src.memory.rag_engine import HanaRAGEngine


def test_rag_engine_uses_persisted_lexical_fallback_when_embeddings_fail(tmp_path, monkeypatch):
    def fail_client(*args, **kwargs):
        raise RuntimeError("simulated chroma failure")

    monkeypatch.setattr(rag_module.chromadb, "PersistentClient", fail_client)

    engine = HanaRAGEngine(persist_directory=str(tmp_path))
    engine.upsert_memory("1", "Nakamura gosta de morango e cafe com leite.", metadata={"role": "user"})
    engine.upsert_memory("2", "Hana guarda fatos importantes para lembrar depois.", metadata={"role": "assistant"})

    results = engine.query_memories("morango", n_results=3, max_distance=0.95)
    scored = engine.query_memories_with_scores("lembrar fatos", n_results=3)

    assert any("morango" in item.lower() for item in results)
    assert scored
    assert Path(tmp_path, "fallback_memories.json").exists()
