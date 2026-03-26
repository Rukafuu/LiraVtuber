import json
import os
import logging

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

ENV_KEYS = (
    "GROQ_API_KEY",
    "GEMINI_API_KEY",
    "CEREBRAS_API_KEY",
    "OPENROUTER_API_KEY",
    "TAVILY_API_KEY",
    "GOOGLE_APPLICATION_CREDENTIALS",
)


class ConfigLoader:
    """Gerenciador de configurações com suporte a leitura, escrita e hot-reload."""

    def __init__(self, config_path="src/config/config.json"):
        self.config_path = config_path
        self._config = {}
        self._last_mtime = 0
        self.load()

    def load(self):
        """Carrega configurações do JSON e sobrepõe com variáveis de ambiente."""
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                self._config = json.load(f)
            self._last_mtime = os.path.getmtime(self.config_path)

        # Environment variables win when set
        for key in ENV_KEYS:
            value = os.getenv(key)
            if value:
                self._config[key] = value

    def reload(self):
        """Recarrega do disco se o arquivo foi modificado. Retorna True se houve mudança."""
        if not os.path.exists(self.config_path):
            return False
        current_mtime = os.path.getmtime(self.config_path)
        if current_mtime > self._last_mtime:
            self.load()
            logger.info("[CONFIG] config.json recarregado (modificação detectada).")
            return True
        return False

    def save(self):
        """Salva o estado atual no config.json, excluindo chaves de ambiente."""
        dados = {k: v for k, v in self._config.items() if k not in ENV_KEYS}
        os.makedirs(os.path.dirname(self.config_path) or ".", exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=4)
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
    """Função global para salvar configurações — compatível com a interface da Nyra."""
    if isinstance(config, ConfigLoader):
        config.save()
    else:
        # Se receber um dict puro, sobrescreve o CONFIG e salva
        CONFIG._config.update(config)
        CONFIG.save()
