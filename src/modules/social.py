import random
import logging
import requests

logger = logging.getLogger(__name__)

class LiraSocial:
    def __init__(self):
        # Mapeamento de comandos para categorias da API nekos.best
        self.action_map = {
            "abracar": {"cat": "hug", "emoji": "🫂", "text": "{sender} deu um abraço carinhoso em {target}!"},
            "beijar": {"cat": "kiss", "emoji": "💋", "text": "{sender} beijou {target}!"},
            "cafune": {"cat": "pat", "emoji": "🌸", "text": "{sender} fez cafuné em {target}!"},
            "tapa": {"cat": "slap", "emoji": "🖐️", "text": "{sender} deu um tapa em {target}!"},
            "morder": {"cat": "bite", "emoji": "🦷", "text": "{sender} mordeu {target}!"},
            "aconchegar": {"cat": "cuddle", "emoji": "🥰", "text": "{sender} se aconchegou com {target}!"},
            "alimentar": {"cat": "feed", "emoji": "🍱", "text": "{sender} alimentou {target}!"},
            "mao": {"cat": "handhold", "emoji": "🤝", "text": "{sender} segurou a mão de {target}!"},
            "highfive": {"cat": "highfive", "emoji": "✋", "text": "{sender} deu um high-five em {target}!"},
            "chutar": {"cat": "kick", "emoji": "🦵", "text": "{sender} chutou {target}!"},
            "beijo_rapido": {"cat": "peck", "emoji": "😘", "text": "{sender} deu um beijinho em {target}!"},
            "cutucar": {"cat": "poke", "emoji": "👉", "text": "{sender} cutucou {target}!"},
            "socar": {"cat": "punch", "emoji": "🥊", "text": "{sender} socou {target}!"},
            "cocegas": {"cat": "tickle", "emoji": "🤣", "text": "{sender} fez cócegas em {target}!"},
            "acenar": {"cat": "wave", "emoji": "👋", "text": "{sender} acenou para {target}!"},
            "arremessar": {"cat": "yeet", "emoji": "🌀", "text": "{sender} arremessou {target}!"},
            "comer": {"cat": "nom", "emoji": "😋", "text": "{sender} comeu {target}!"},
            "xingar": {"cat": "baka", "emoji": "😤", "text": "{sender} chamou {target} de baka!"},
            "olhar": {"cat": "stare", "emoji": "👀", "text": "{sender} ficou encarando {target}!"},
            "matar": {"cat": "kill", "emoji": "⚔️", "text": "{sender} matou {target}!"},
            "apertar_mao": {"cat": "handshake", "emoji": "🤝", "text": "{sender} apertou a mão de {target}!"},
            # Expressões próprias (sem alvo)
            "corar": {"cat": "blush", "emoji": "😳", "text": "{sender} está corando!"},
            "entediado": {"cat": "bored", "emoji": "😒", "text": "{sender} está entediado(a)..."},
            "chorar": {"cat": "cry", "emoji": "😭", "text": "{sender} está chorando..."},
            "dancar": {"cat": "dance", "emoji": "💃", "text": "{sender} está dançando!"},
            "facepalm": {"cat": "facepalm", "emoji": "🤦", "text": "{sender} não acredita no que viu..."},
            "rir": {"cat": "laugh", "emoji": "😂", "text": "{sender} está rindo muito!"},
            "concordar": {"cat": "nod", "emoji": "😌", "text": "{sender} está concordando."},
            "recusar": {"cat": "nope", "emoji": "🙅", "text": "{sender} está recusando."},
            "fazer_bico": {"cat": "pout", "emoji": "😤", "text": "{sender} está fazendo bico."},
            "correr": {"cat": "run", "emoji": "🏃", "text": "{sender} está correndo!"},
            "triste": {"cat": "sad", "emoji": "😢", "text": "{sender} está triste..."},
            "dar_de_ombros": {"cat": "shrug", "emoji": "🤷", "text": "{sender} não sabe o que dizer."},
            "dormir": {"cat": "sleep", "emoji": "😴", "text": "{sender} foi dormir..."},
            "sorrir": {"cat": "smile", "emoji": "😊", "text": "{sender} está sorrindo!"},
            "satisfeito": {"cat": "smug", "emoji": "😏", "text": "{sender} está satisfeito(a)."},
            "pensar": {"cat": "think", "emoji": "🤔", "text": "{sender} está pensando..."},
            "joinha": {"cat": "thumbsup", "emoji": "👍", "text": "{sender} deu um joinha!"},
            "piscar": {"cat": "wink", "emoji": "😉", "text": "{sender} piscou!"},
            "bocejar": {"cat": "yawn", "emoji": "🥱", "text": "{sender} está com sono..."},
            "feliz": {"cat": "happy", "emoji": "😄", "text": "{sender} está feliz!"},
            "espreitar": {"cat": "lurk", "emoji": "👁️", "text": "{sender} está espiando..."}
        }

    def fetch_gif(self, category):
        try:
            resp = requests.get(f"https://nekos.best/api/v2/{category}", timeout=5)
            if resp.status_code == 200:
                return resp.json()["results"][0]["url"]
        except Exception as e:
            logger.error(f"[SOCIAL] Erro ao buscar GIF: {e}")
        return None

    def execute_action(self, action_name, sender, target=None):
        action = self.action_map.get(action_name)
        if not action:
            return None
            
        gif_url = self.fetch_gif(action["cat"])
        phrase = action["text"].format(sender=sender, target=target if target else "")
        
        return {
            "text": f"{action['emoji']} {phrase}",
            "gif": gif_url
        }

# Instância global
lira_social = LiraSocial()
