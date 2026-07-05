"""
utils/config_manager.py

Loads/saves config/user_config.json, falling back to
config/default_config.json for any missing keys. This is the backing
store for the Settings screen.
"""

from __future__ import annotations

import json
from pathlib import Path

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
DEFAULT_CONFIG_PATH = CONFIG_DIR / "default_config.json"
USER_CONFIG_PATH = CONFIG_DIR / "user_config.json"


def load_defaults() -> dict:
    with open(DEFAULT_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_config() -> dict:
    config = load_defaults()
    if USER_CONFIG_PATH.exists():
        with open(USER_CONFIG_PATH, "r", encoding="utf-8") as f:
            user_overrides = json.load(f)
        config.update(user_overrides)
    return config


def save_config(config: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(USER_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def update_config(**kwargs) -> dict:
    config = load_config()
    config.update(kwargs)
    save_config(config)
    return config
