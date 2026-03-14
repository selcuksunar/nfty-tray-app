"""Internationalization module for ntfy-tray."""
from __future__ import annotations

import json
import os
from pathlib import Path

_translations: dict[str, str] = {}
_current_lang: str = "en"
_translations_dir = Path(__file__).parent / "translations"


def load_language(lang: str):
    """Load a language file and set it as active."""
    global _translations, _current_lang

    lang_file = _translations_dir / f"{lang}.json"
    if not lang_file.exists():
        lang_file = _translations_dir / "en.json"
        lang = "en"

    with open(lang_file, "r", encoding="utf-8") as f:
        _translations = json.load(f)

    _current_lang = lang


def tr(key: str) -> str:
    """Return the translated string for the given key."""
    return _translations.get(key, key)


def current_language() -> str:
    """Return the current language code."""
    return _current_lang


def available_languages() -> dict[str, str]:
    """Return dict of available languages {code: display_name}."""
    languages = {}
    for f in sorted(_translations_dir.glob("*.json")):
        code = f.stem
        try:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            languages[code] = data.get("_language_name", code)
        except (json.JSONDecodeError, OSError):
            languages[code] = code
    return languages
