import sqlite3
import os
import math
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

DB_PATH = "data/gamification.db"

class LiraGamification:
    def __init__(self):
        os.makedirs("data", exist_ok=True)
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_stats (
                user_id TEXT,
                platform TEXT,
                username TEXT,
                xp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1,
                coins INTEGER DEFAULT 0,
                last_daily TEXT,
                last_weekly TEXT,
                banner_url TEXT,
                bank_coins INTEGER DEFAULT 0,
                shields INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, platform)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS game_limits (
                user_id TEXT,
                platform TEXT,
                game_name TEXT,
                rounds_today INTEGER DEFAULT 0,
                last_played TEXT,
                PRIMARY KEY (user_id, platform, game_name)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS marriages (
                user_id_1 TEXT,
                user_id_2 TEXT,
                platform TEXT,
                married_at TEXT,
                PRIMARY KEY (user_id_1, platform)
            )
        """)
        conn.commit()
        conn.close()

    def get_marriage(self, user_id, platform):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM marriages 
            WHERE (user_id_1 = ? OR user_id_2 = ?) AND platform = ?
        """, (user_id, user_id, platform))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def marry(self, user_id_1, user_id_2, platform):
        if self.get_marriage(user_id_1, platform) or self.get_marriage(user_id_2, platform):
            return False
        
        now = datetime.now().isoformat()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO marriages (user_id_1, user_id_2, platform, married_at)
            VALUES (?, ?, ?, ?)
        """, (user_id_1, user_id_2, platform, now))
        conn.commit()
        conn.close()
        return True

    def divorce(self, user_id, platform):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM marriages 
            WHERE (user_id_1 = ? OR user_id_2 = ?) AND platform = ?
        """, (user_id, user_id, platform))
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success

    def get_user(self, user_id, platform, username="Player"):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM user_stats WHERE user_id = ? AND platform = ?", (user_id, platform))
        user = cursor.fetchone()
        
        if not user:
            cursor.execute("""
                INSERT INTO user_stats (user_id, platform, username) 
                VALUES (?, ?, ?)
            """, (user_id, platform, username))
            conn.commit()
            cursor.execute("SELECT * FROM user_stats WHERE user_id = ? AND platform = ?", (user_id, platform))
            user = cursor.fetchone()
            
        conn.close()
        return dict(user)

    def add_xp(self, user_id, platform, amount=10):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Pega estado atual
        cursor.execute("SELECT xp, level FROM user_stats WHERE user_id = ? AND platform = ?", (user_id, platform))
        row = cursor.fetchone()
        if not row: return False
        
        current_xp, current_level = row
        new_xp = current_xp + amount
        
        # Lógica de nível: lvl * 100 * (lvl * 0.5)
        needed_xp = self.get_xp_for_level(current_level + 1)
        
        leveled_up = False
        if new_xp >= needed_xp:
            current_level += 1
            leveled_up = True
            
        cursor.execute("""
            UPDATE user_stats 
            SET xp = ?, level = ? 
            WHERE user_id = ? AND platform = ?
        """, (new_xp, current_level, user_id, platform))
        
        conn.commit()
        conn.close()
        return leveled_up

    def get_xp_for_level(self, level):
        if level <= 1: return 0
        return int(100 * (level - 1) * (1 + (level - 1) * 0.2))

    def claim_daily(self, user_id, platform):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT last_daily, coins, xp FROM user_stats WHERE user_id = ? AND platform = ?", (user_id, platform))
        row = cursor.fetchone()
        
        if not row: return {"success": False, "message": "Usuário não encontrado."}
        
        last_daily_str, coins, xp = row
        now = datetime.now()
        
        if last_daily_str:
            last_daily = datetime.fromisoformat(last_daily_str)
            if now < last_daily + timedelta(days=1):
                wait_time = (last_daily + timedelta(days=1)) - now
                hours = int(wait_time.total_seconds() // 3600)
                return {"success": False, "message": f"Calma! Volte em {hours}h."}
        
        reward_coins = 100
        reward_xp = 50
        
        cursor.execute("""
            UPDATE user_stats 
            SET last_daily = ?, coins = coins + ?, xp = xp + ? 
            WHERE user_id = ? AND platform = ?
        """, (now.isoformat(), reward_coins, reward_xp, user_id, platform))
        
        conn.commit()
        conn.close()
        return {"success": True, "coins": reward_coins, "xp": reward_xp}

    def bank_action(self, user_id, platform, action, amount):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT coins, bank_coins FROM user_stats WHERE user_id = ? AND platform = ?", (user_id, platform))
        row = cursor.fetchone()
        if not row: return {"success": False, "message": "Usuário não encontrado."}
        
        coins, bank_coins = row
        
        if action == "deposit":
            if amount > coins: return {"success": False, "message": "Você não tem moedas suficientes."}
            cursor.execute("UPDATE user_stats SET coins = coins - ?, bank_coins = bank_coins + ? WHERE user_id = ? AND platform = ?", (amount, amount, user_id, platform))
        elif action == "withdraw":
            if amount > bank_coins: return {"success": False, "message": "Você não tem isso tudo no banco."}
            cursor.execute("UPDATE user_stats SET coins = coins + ?, bank_coins = bank_coins - ? WHERE user_id = ? AND platform = ?", (amount, amount, user_id, platform))
            
        conn.commit()
        conn.close()
        return {"success": True}

    def steal(self, attacker_id, target_id, platform):
        import random
        if attacker_id == target_id: return {"success": False, "message": "Você não pode roubar a si mesmo!"}
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Pega dados do alvo
        cursor.execute("SELECT coins, shields, username FROM user_stats WHERE user_id = ? AND platform = ?", (target_id, platform))
        target = cursor.fetchone()
        if not target or target[0] < 50: return {"success": False, "message": "O alvo está muito pobre para ser roubado!"}
        
        t_coins, t_shields, t_name = target
        
        # Se o alvo tiver escudo, o roubo falha e consome 1 escudo
        if t_shields > 0:
            cursor.execute("UPDATE user_stats SET shields = shields - 1 WHERE user_id = ? AND platform = ?", (target_id, platform))
            conn.commit()
            conn.close()
            return {"success": False, "message": f"O roubo falhou! **{t_name}** estava com um escudo ativado! 🛡️"}

        # Chance de sucesso: 45%
        success = random.random() < 0.45
        if success:
            stolen = int(t_coins * random.uniform(0.1, 0.3))
            cursor.execute("UPDATE user_stats SET coins = coins - ? WHERE user_id = ? AND platform = ?", (stolen, target_id, platform))
            cursor.execute("UPDATE user_stats SET coins = coins + ? WHERE user_id = ? AND platform = ?", (stolen, attacker_id, platform))
            res = {"success": True, "stolen": stolen, "target_name": t_name}
        else:
            penalty = 50
            cursor.execute("UPDATE user_stats SET coins = MAX(0, coins - ?) WHERE user_id = ? AND platform = ?", (penalty, attacker_id, platform))
            res = {"success": False, "message": f"Você foi pego e pagou uma multa de **{penalty}** moedas! 🚔"}
            
        conn.commit()
        conn.close()
        return res

    def can_play_game(self, user_id, platform, game_name):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT rounds_today, last_played FROM game_limits WHERE user_id = ? AND platform = ? AND game_name = ?", (user_id, platform, game_name))
        row = cursor.fetchone()
        
        now = datetime.now().date().isoformat()
        
        if not row:
            cursor.execute("INSERT INTO game_limits (user_id, platform, game_name, last_played) VALUES (?, ?, ?, ?)", (user_id, platform, game_name, now))
            conn.commit()
            conn.close()
            return True
            
        rounds, last_date = row
        if last_date != now:
            cursor.execute("UPDATE game_limits SET rounds_today = 0, last_played = ? WHERE user_id = ? AND platform = ? AND game_name = ?", (now, user_id, platform, game_name))
            conn.commit()
            conn.close()
            return True
            
        conn.close()
        return rounds < 3

    def increment_game_count(self, user_id, platform, game_name):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("UPDATE game_limits SET rounds_today = rounds_today + 1 WHERE user_id = ? AND platform = ? AND game_name = ?", (user_id, platform, game_name))
        conn.commit()
        conn.close()

    def get_leaderboard(self, platform=None, limit=10):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        if platform:
            cursor.execute("SELECT * FROM user_stats WHERE platform = ? ORDER BY xp DESC LIMIT ?", (platform, limit))
        else:
            cursor.execute("SELECT * FROM user_stats ORDER BY xp DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

# Instância global
lira_gamification = LiraGamification()
