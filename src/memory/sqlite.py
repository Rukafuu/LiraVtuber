import sqlite3

class SQLite:
    def __init__(self, db_path):
        self.db_path = db_path

    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()
        conn.close()

    def save_message(self, role, content):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO messages (role, content) VALUES (?, ?)", (role, content))
        conn.commit()
        conn.close()

    def load_messages(self, limit=None):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if limit:
            # Busca os últimos N registros em ordem decrescente
            cursor.execute("SELECT role, content FROM messages ORDER BY timestamp DESC LIMIT ?", (limit,))
            raw_messages = cursor.fetchall()
            # Inverte para ficarem em ordem cronológica (mais antigo primeiro)
            raw_messages.reverse()
        else:
            # Caso contrário, busca tudo normalmente
            cursor.execute("SELECT role, content FROM messages ORDER BY timestamp ASC")
            raw_messages = cursor.fetchall()
            
        conn.close()

        formatted_messages = []
        for role, content in raw_messages:
            formatted_messages.append({"role": role, "content": content})
        return formatted_messages