import re
import time

class LiraAutoMod:
    def __init__(self):
        # Lista básica (pode ser expandida no .env ou banco)
        self.banned_words = ["ofensa1", "ofensa2", "spamlink.com"] 
        self.user_history = {} # Para anti-spam
        self.user_warns = {} # user_id -> int
        
        # Interruptores de Módulo
        self.settings = {
            "games": True,
            "automod": True,
            "economy": True
        }

    def set_module(self, module, state: bool):
        if module in self.settings:
            self.settings[module] = state
            return True
        return False

    def add_warn(self, user_id):
        self.user_warns[user_id] = self.user_warns.get(user_id, 0) + 1
        return self.user_warns[user_id]

    def check_message(self, user_id, content):
        """
        Retorna (is_clean, reason)
        """
        lowered = content.lower()
        
        # 1. Filtro de palavras banidas
        for word in self.banned_words:
            if word in lowered:
                return False, f"Palavra proibida detectada: {word}"

        # 2. Anti-Spam (3 mensagens iguais em 10 segundos)
        now = time.time()
        if user_id not in self.user_history:
            self.user_history[user_id] = []
        
        history = self.user_history[user_id]
        history.append({"time": now, "content": lowered})
        
        # Limpa histórico antigo (> 30s)
        self.user_history[user_id] = [h for h in history if now - h["time"] < 30]
        
        recent = self.user_history[user_id]
        if len(recent) >= 3:
            # Verifica se as 3 últimas são iguais
            last_three = [h["content"] for h in recent[-3:]]
            if len(set(last_three)) == 1:
                return False, "Spam detectado (mensagens repetidas)"

        return True, None

# Instância global
lira_automod = LiraAutoMod()
