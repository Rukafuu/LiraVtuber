import logging
import os
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from lira_core.economy import lira_finance

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/finance", tags=["finance"])


class TransactionPayload(BaseModel):
    id: Optional[int] = None
    tipo: str  # 'receita' ou 'despesa'
    valor: float
    estabelecimento: Optional[str] = None
    categoria: Optional[str] = None
    descricao: Optional[str] = None


def _get_finance_account() -> str:
    owner = os.getenv("WPP_OWNER_JID") or os.getenv("WPP_OWNER_LID") or "5511981826659@s.whatsapp.net"
    clean = owner.split(":")[0]
    if "@" not in clean and "@" in owner:
        clean = f"{clean}@{owner.split('@', 1)[1]}"
    return f"whatsapp:{clean}"


@router.get("/summary")
async def get_finance_summary(dias: int = 30):
    account = _get_finance_account()
    try:
        summary = lira_finance.obter_resumo(account, dias=dias)
        return {"status": "ok", "summary": summary}
    except Exception as e:
        logger.error(f"[API] Erro ao obter resumo financeiro: {e}")
        return {"status": "error", "message": str(e)}


@router.post("/transactions")
async def save_finance_transaction(payload: TransactionPayload):
    account = _get_finance_account()
    try:
        if payload.id:
            success = lira_finance.atualizar_transacao(
                transaction_id=payload.id,
                account=account,
                tipo=payload.tipo,
                valor=payload.valor,
                estabelecimento=payload.estabelecimento,
                categoria=payload.categoria,
                descricao=payload.descricao,
            )
            if success:
                return {"status": "ok", "message": "Transacao atualizada."}
            return {"status": "error", "message": "Falha ao atualizar transacao ou transacao nao encontrada."}
        else:
            res = lira_finance.registrar_transacao(
                account=account,
                tipo=payload.tipo,
                valor=payload.valor,
                estabelecimento=payload.estabelecimento,
                categoria=payload.categoria,
                descricao=payload.descricao,
            )
            return {"status": "ok", "transaction": res}
    except Exception as e:
        logger.error(f"[API] Erro ao salvar transacao: {e}")
        return {"status": "error", "message": str(e)}


@router.delete("/transactions/{tx_id}")
async def delete_finance_transaction(tx_id: int):
    account = _get_finance_account()
    try:
        success = lira_finance.excluir_transacao(tx_id, account)
        if success:
            return {"status": "ok", "message": "Transacao excluida."}
        return {"status": "error", "message": "Falha ao excluir transacao ou transacao nao encontrada."}
    except Exception as e:
        logger.error(f"[API] Erro ao excluir transacao: {e}")
        return {"status": "error", "message": str(e)}
