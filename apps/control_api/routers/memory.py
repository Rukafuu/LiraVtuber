import logging
import uuid
from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/memory", tags=["memory"])


@router.get("/graph")
async def get_memory_graph(request: Request):
    """Retorna todos os fatos do Knowledge Graph."""
    context = request.app.state.lira
    if not context or not context.memory_manager or not context.memory_manager.graph:
        return {"facts": []}
    return {"facts": context.memory_manager.graph.get_all_facts()}


@router.delete("/graph")
async def delete_memory_graph(request: Request, payload: dict):
    """Remove um fato do Knowledge Graph."""
    context = request.app.state.lira
    if not context or not context.memory_manager or not context.memory_manager.graph:
        return {"status": "error", "message": "Memoria indisponivel"}

    subject = payload.get("subject")
    relation = payload.get("relation")
    object_val = payload.get("object")

    success = context.memory_manager.graph.delete_fact(subject, relation, object_val)
    if success:
        return {"status": "ok"}
    return {"status": "error", "message": "Falha ao remover fato"}


@router.post("/graph")
async def create_memory_graph(request: Request, payload: dict):
    """Cria ou atualiza um fato no Knowledge Graph."""
    context = request.app.state.lira
    if not context or not context.memory_manager or not context.memory_manager.graph:
        return {"status": "error", "message": "Memoria indisponivel"}

    subject = str(payload.get("subject") or "").strip()
    relation = str(payload.get("relation") or "").strip()
    object_val = str(payload.get("object") or "").strip()
    if not subject or not relation or not object_val:
        return {"status": "error", "message": "Preencha subject, relation e object."}

    context.memory_manager.add_fact(subject, relation, object_val)
    return {"status": "ok", "fact": {"subject": subject, "relation": relation, "object": object_val}}


@router.get("/rag")
async def get_memory_rag(request: Request):
    """Retorna todas as memorias semanticas do RAG."""
    context = request.app.state.lira
    if not context or not context.memory_manager or not context.memory_manager.rag:
        return {"memories": []}
    return {"memories": context.memory_manager.rag.get_all_memories()}


@router.delete("/rag/{mem_id}")
async def delete_memory_rag(request: Request, mem_id: str):
    """Remove uma memoria semantica do RAG pelo ID."""
    context = request.app.state.lira
    if not context or not context.memory_manager or not context.memory_manager.rag:
        return {"status": "error", "message": "Memoria indisponivel"}

    success = context.memory_manager.rag.delete_memory(mem_id)
    if success:
        return {"status": "ok"}
    return {"status": "error", "message": "Falha ao remover memoria"}


@router.post("/rag")
async def create_memory_rag(request: Request, payload: dict):
    """Cria uma memoria semantica manual no RAG."""
    context = request.app.state.lira
    if not context or not context.memory_manager or not context.memory_manager.rag:
        return {"status": "error", "message": "Memoria indisponivel"}

    text = str(payload.get("text") or "").strip()
    if len(text) < 3:
        return {"status": "error", "message": "Texto muito curto."}

    mem_id = str(payload.get("id") or uuid.uuid4())
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    metadata.setdefault("source", "gui_memory_editor")
    context.memory_manager.rag.upsert_memory(mem_id, text, metadata=metadata)
    return {"status": "ok", "memory": {"id": mem_id, "text": text, "metadata": metadata}}


@router.put("/rag/{mem_id}")
async def update_memory_rag(request: Request, mem_id: str, payload: dict):
    """Atualiza uma memoria semantica existente no RAG."""
    context = request.app.state.lira
    if not context or not context.memory_manager or not context.memory_manager.rag:
        return {"status": "error", "message": "Memoria indisponivel"}

    text = str(payload.get("text") or "").strip()
    if len(text) < 3:
        return {"status": "error", "message": "Texto muito curto."}

    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    metadata.setdefault("source", "gui_memory_editor")
    context.memory_manager.rag.upsert_memory(mem_id, text, metadata=metadata)
    return {"status": "ok", "memory": {"id": mem_id, "text": text, "metadata": metadata}}
