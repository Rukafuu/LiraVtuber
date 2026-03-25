from src.memory.sqlite import SQLite # Importa o SQLite que você já tem!

class memory:
    def __init__(self, db_path):
        self.db = SQLite(db_path) # Inicializa o SQLite
        self.db.init_db() # Garante que o banco de dados esteja pronto

    def add_message(self, role, content):
        self.db.save_message(role, content) # Salva a mensagem no DB

    def get_messages(self, limit=None):
        return self.db.load_messages(limit) # Carrega as mensagens do DB com limite opcional

    def clear_messages(self):
        self.db.clear_messages() # Limpa o DB (se você criar essa função no SQLite.py)