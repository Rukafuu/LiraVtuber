import random

class LiraGames:
    FORCA_WORDS = {
        "Anime": ["NARUTO", "SASUKE", "LUFFY", "ZORO", "GOKU", "VEGETA", "TANJIRO", "NEZUKO", "EREN", "MIKASA"],
        "Games": ["MARIO", "ZELDA", "KRATOS", "LINK", "SONIC", "PIKACHU", "ALOY", "MASTER CHIEF"],
        "Tech": ["PYTHON", "JAVASCRIPT", "DISCORD", "WHATSAPP", "LINUX", "WINDOWS", "ARDUINO", "RASPBERRY"]
    }

    CHARACTER_GUESS = [
        {"desc": "Uso um chapéu de palha e quero ser o Rei dos Piratas.", "name": "Luffy"},
        {"desc": "Sou um ninja que tem uma raposa selada dentro de mim.", "name": "Naruto"},
        {"desc": "Sou um encanador italiano que resgata princesas.", "name": "Mario"},
        {"desc": "Sou o Deus da Guerra e tenho um filho chamado Atreus.", "name": "Kratos"},
        {"desc": "Sou uma inteligência artificial lilás que serve ao Amarinth.", "name": "Lira"}
    ]

    def start_hangman(self):
        category = random.choice(list(self.FORCA_WORDS.keys()))
        word = random.choice(self.FORCA_WORDS[category])
        return {
            "word": word,
            "category": category,
            "display": "_" * len(word),
            "tries": 6,
            "guessed": []
        }

    def start_guess_char(self):
        char = random.choice(self.CHARACTER_GUESS)
        return char

# Instância global
lira_games = LiraGames()
