import logging
import sqlite3
import time
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parents[4] / "data" / "lira_finance.db"


class LiraFinance:
    def __init__(self):
        self._init_db()

    def _init_db(self):
        try:
            DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS transactions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        account TEXT NOT NULL,
                        tipo TEXT NOT NULL,
                        valor REAL NOT NULL,
                        estabelecimento TEXT,
                        categoria TEXT,
                        descricao TEXT,
                        timestamp INTEGER NOT NULL
                    )
                """)
                conn.commit()
        except Exception as e:
            logger.error("[FINANCE] Erro ao inicializar banco de dados: %s", e)

    def registrar_transacao(self, account, tipo, valor, estabelecimento=None, categoria=None, descricao=None):
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO transactions (account, tipo, valor, estabelecimento, categoria, descricao, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (account, tipo, float(valor), estabelecimento, categoria, descricao, int(time.time())),
                )
                conn.commit()
                tx_id = cursor.lastrowid
                return {
                    "id": tx_id,
                    "account": account,
                    "tipo": tipo,
                    "valor": valor,
                    "estabelecimento": estabelecimento,
                    "categoria": categoria,
                    "descricao": descricao,
                }
        except Exception as e:
            logger.error("[FINANCE] Erro ao registrar transacao: %s", e)
            return None

    def obter_resumo(self, account, dias=30):
        try:
            since = int(time.time()) - (dias * 24 * 3600)
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT * FROM transactions
                    WHERE account = ? AND timestamp >= ?
                    ORDER BY timestamp DESC
                """,
                    (account, since),
                )
                rows = cursor.fetchall()

                receitas = 0.0
                despesas = 0.0
                history = []

                for row in rows:
                    tx = dict(row)
                    val = tx["valor"]
                    if tx["tipo"] == "receita":
                        receitas += val
                    else:
                        despesas += val
                    history.append(tx)

                return {
                    "receitas": receitas,
                    "despesas": despesas,
                    "saldo": receitas - despesas,
                    "dias": dias,
                    "transacoes": history,
                }
        except Exception as e:
            logger.error("[FINANCE] Erro ao obter resumo: %s", e)
            return {"receitas": 0.0, "despesas": 0.0, "saldo": 0.0, "dias": dias, "transacoes": []}

    def atualizar_transacao(self, transaction_id, account, tipo, valor, estabelecimento=None, categoria=None, descricao=None):
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE transactions
                    SET tipo = ?, valor = ?, estabelecimento = ?, categoria = ?, descricao = ?
                    WHERE id = ? AND account = ?
                """,
                    (tipo, float(valor), estabelecimento, categoria, descricao, transaction_id, account),
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error("[FINANCE] Erro ao atualizar transacao: %s", e)
            return False

    def excluir_transacao(self, transaction_id, account):
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM transactions WHERE id = ? AND account = ?",
                    (transaction_id, account),
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error("[FINANCE] Erro ao excluir transacao: %s", e)
            return False


lira_finance = LiraFinance()
