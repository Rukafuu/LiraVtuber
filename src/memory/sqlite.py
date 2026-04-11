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
        columns = "role, content, timestamp" if include_timestamp else "role, content"
        cursor.execute("INSERT INTO messages (role, content) VALUES (?, ?)", (role, content))
        conn.commit()
        conn.close()

    def load_messages(self, limit=None, include_timestamp=False):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if limit:
            # Busca os últimos N registros em ordem decrescente
            cursor.execute(f"SELECT {columns} FROM messages ORDER BY timestamp DESC LIMIT ?", (limit,))
            raw_messages = cursor.fetchall()
            # Inverte para ficarem em ordem cronológica (mais antigo primeiro)
            raw_messages.reverse()
        else:
            # Caso contrário, busca tudo normalmente
            cursor.execute(f"SELECT {columns} FROM messages ORDER BY timestamp ASC")
            raw_messages = cursor.fetchall()
            
        conn.close()

        formatted_messages = []
        for row in raw_messages:
            role, content = row[0], row[1]
            item = {"role": role, "content": content}
            if include_timestamp:
                item["timestamp"] = row[2]
            formatted_messages.append(item)
        return formatted_messages
