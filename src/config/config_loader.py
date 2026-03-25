import json
import os

from dotenv import load_dotenv

load_dotenv()

ENV_KEYS = (
    "GROQ_API_KEY",
    "GEMINI_API_KEY",
    "CEREBRAS_API_KEY",
    "OPENROUTER_API_KEY",
    "TAVILY_API_KEY",
    "GOOGLE_APPLICATION_CREDENTIALS",
)


class ConfigLoader:
    def __init__(self, config_path="src/config/config.json"):
        self.config_path = config_path
        self._config = {}
        self.load()

    def load(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                self._config = json.load(f)

        # Environment variables should win, but only when they are actually set.
        for key in ENV_KEYS:
            value = os.getenv(key)
            if value:
                self._config[key] = value

    def get(self, key, default=None):
        return self._config.get(key, os.getenv(key, default))


CONFIG = ConfigLoader()
