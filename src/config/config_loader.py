import json
import logging
import os

from dotenv import load_dotenv

load_dotenv(encoding="utf-8-sig")
logger = logging.getLogger(__name__)

ENV_KEYS = (
    "GROQ_API_KEY",
    "GEMINI_API_KEY",
    "CEREBRAS_API_KEY",
    "OPENROUTER_API_KEY",
    "OPENAI_API_KEY",
    "ELEVENLABS_API_KEY",
    "TAVILY_API_KEY",
    "GOOGLE_APPLICATION_CREDENTIALS",
)


class ConfigLoader:
    """Gerenciador de configurações com suporte a leitura, escrita e hot-reload."""

    def __init__(self, config_path="src/config/config.json"):
        self.config_path = config_path
        self.example_path = os.path.join(os.path.dirname(config_path), "config.example.json")
        self._config = {}
        self._last_mtime = 0
        self._example_last_mtime = 0
        self.load()

    def load(self):
        """Carrega defaults publicos, config local e variaveis de ambiente."""
        self._config = {}
        if os.path.exists(self.example_path):
            with open(self.example_path, "r", encoding="utf-8") as file:
                self._config.update(json.load(file))
            self._example_last_mtime = os.path.getmtime(self.example_path)

        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as file:
                self._config.update(json.load(file))
            self._last_mtime = os.path.getmtime(self.config_path)
        else:
            self._last_mtime = 0

        for key in ENV_KEYS:
            value = os.getenv(key)
            if value:
                self._config[key] = value

    def reload(self):
        """Recarrega do disco se o arquivo foi modificado. Retorna True se houve mudança."""
        config_mtime = os.path.getmtime(self.config_path) if os.path.exists(self.config_path) else 0
        example_mtime = os.path.getmtime(self.example_path) if os.path.exists(self.example_path) else 0
        if config_mtime > self._last_mtime or example_mtime > self._example_last_mtime:
            self.load()
            logger.info("[CONFIG] config.json recarregado (modificação detectada).")
            return True
        return False

    def save(self):
        """Salva o estado atual no config.json, excluindo chaves vindas do ambiente."""
        dados = {key: value for key, value in self._config.items() if key not in ENV_KEYS}
        os.makedirs(os.path.dirname(self.config_path) or ".", exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as file:
            json.dump(dados, file, ensure_ascii=False, indent=4)
        self._last_mtime = os.path.getmtime(self.config_path)
        logger.info("[CONFIG] config.json salvo com sucesso.")

    def get(self, key, default=None):
        return self._config.get(key, os.getenv(key, default))

    def __getitem__(self, key):
        return self._config[key]

    def __setitem__(self, key, value):
        self._config[key] = value

    def __contains__(self, key):
        return key in self._config

    def setdefault(self, key, default=None):
        return self._config.setdefault(key, default)

    def clear(self):
        self._config.clear()

    def update(self, data):
        self._config.update(data)

    def items(self):
        return self._config.items()

    def keys(self):
        return self._config.keys()


CONFIG = ConfigLoader()


def salvar_configuracoes(config):
    """Função global para salvar configurações, compatível com a interface da Nyra."""
    if isinstance(config, ConfigLoader):
        config.save()
    else:
        CONFIG._config.update(config)
        CONFIG.save()
