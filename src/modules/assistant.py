import sqlite3
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class LiraAssistant:
    def __init__(self, db_path="data/assistant.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''
                CREATE TABLE IF NOT EXISTS user_lists (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    list_type TEXT NOT NULL,
                    item_text TEXT NOT NULL,
                    status TEXT DEFAULT 'pendente',
                    created_at TIMESTAMP
                )
            ''')
            conn.commit()

    def add_item(self, user_id: str, platform: str, list_type: str, item_text: str) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute(
                    "INSERT INTO user_lists (user_id, platform, list_type, item_text, created_at) VALUES (?, ?, ?, ?, ?)",
                    (user_id, platform, list_type.lower(), item_text, datetime.now())
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"[ASSISTANT] Erro ao adicionar item: {e}")
            return False

    def get_list(self, user_id: str, platform: str, list_type: str = None) -> list:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                if list_type:
                    c.execute(
                        "SELECT * FROM user_lists WHERE user_id = ? AND platform = ? AND list_type = ? AND status = 'pendente' ORDER BY created_at ASC",
                        (user_id, platform, list_type.lower())
                    )
                else:
                    c.execute(
                        "SELECT * FROM user_lists WHERE user_id = ? AND platform = ? AND status = 'pendente' ORDER BY list_type, created_at ASC",
                        (user_id, platform)
                    )
                return [dict(row) for row in c.fetchall()]
        except Exception as e:
            logger.error(f"[ASSISTANT] Erro ao buscar lista: {e}")
            return []

    def complete_item_by_text(self, user_id: str, platform: str, list_type: str, item_text: str) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                # Usa LIKE para achar o item que contenha o texto (case insensitive)
                c.execute(
                    "UPDATE user_lists SET status = 'concluido' WHERE user_id = ? AND platform = ? AND list_type = ? AND item_text LIKE ? AND status = 'pendente'",
                    (user_id, platform, list_type.lower(), f"%{item_text}%")
                )
                conn.commit()
                return c.rowcount > 0
        except Exception as e:
            logger.error(f"[ASSISTANT] Erro ao concluir item por texto: {e}")
            return False

    def remove_item_by_text(self, user_id: str, platform: str, list_type: str, item_text: str) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute(
                    "DELETE FROM user_lists WHERE user_id = ? AND platform = ? AND list_type = ? AND item_text LIKE ?",
                    (user_id, platform, list_type.lower(), f"%{item_text}%")
                )
                conn.commit()
                return c.rowcount > 0
        except Exception as e:
            logger.error(f"[ASSISTANT] Erro ao remover item por texto: {e}")
            return False

    def clear_list(self, user_id: str, platform: str, list_type: str) -> int:
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                if list_type.lower() == "todas":
                    c.execute("DELETE FROM user_lists WHERE user_id = ? AND platform = ?", (user_id, platform))
                else:
                    c.execute("DELETE FROM user_lists WHERE user_id = ? AND platform = ? AND list_type = ?", (user_id, platform, list_type.lower()))
                conn.commit()
                return c.rowcount
        except Exception as e:
            logger.error(f"[ASSISTANT] Erro ao limpar lista: {e}")
            return 0

lira_assistant = LiraAssistant()
