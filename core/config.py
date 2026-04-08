"""
Nova App Builder Configuration
With self-verification for autonomous operation
"""

import json
from pathlib import Path
from core.errors import NovaConfigError
from core.logger import session_logger, LogLevel


class NovaConfig:
    REQUIRED_KEYS = ["engine", "model", "temperature", "max_tokens"]

    def __init__(self):
        self.config_path = Path("nova_config.json")
        self.config = None
        self._load()

    def _load(self):
        session_logger.log("Loading configuration...", LogLevel.SYSTEM)

        if not self.config_path.exists():
            raise NovaConfigError(f"Configuration file not found: {self.config_path}")

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                self.config = json.load(f)

            missing = [k for k in self.REQUIRED_KEYS if k not in self.config]
            if missing:
                raise NovaConfigError(f"Missing required config keys: {missing}")

            if self.config["engine"] not in ["local", "openai"]:
                raise NovaConfigError(f"Invalid engine: {self.config['engine']}")

            session_logger.log(
                "Configuration loaded successfully",
                LogLevel.SYSTEM,
                {"engine": self.config["engine"], "model": self.config["model"]}
            )

        except json.JSONDecodeError as e:
            raise NovaConfigError(f"Invalid JSON in config: {e}")

    def get(self, key, default=None):
        return self.config.get(key, default)

    def __getitem__(self, key):
        return self.config[key]


# Single global instance
config = NovaConfig()


# ── Public API ───────────────────────────────────────────────
def load_config() -> dict:
    """Return the current configuration as a dictionary."""
    return config.config

