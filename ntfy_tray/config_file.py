"""Handle .ntfy configuration file import."""

from __future__ import annotations

import json
import logging

from ntfy_tray.database import Settings
from ntfy_tray.i18n import load_language

logger = logging.getLogger("ntfy-tray")
settings = Settings("ntfy-tray")

SUPPORTED_KEYS = {"server_url", "username", "password", "topics_url", "language"}


def apply_config_file(path: str) -> bool:
    """Read a .ntfy config file and apply supported settings. Returns True on success."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.error(f"Failed to read config file {path}: {e}")
        return False

    unknown = set(data.keys()) - SUPPORTED_KEYS
    if unknown:
        logger.warning(f"Config file contains unknown keys (ignored): {unknown}")

    if "server_url" in data:
        settings.setValue("Server/url", str(data["server_url"]).rstrip("/"))

    if "username" in data:
        settings.setValue("Server/username", str(data["username"]))

    if "password" in data:
        settings.setValue("Server/password", str(data["password"]))

    if "topics_url" in data:
        settings.setValue("Server/topics_url", str(data["topics_url"]))

    if "language" in data:
        lang = str(data["language"])
        settings.setValue("language", lang)
        load_language(lang)

    settings.sync()
    return True
