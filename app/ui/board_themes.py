"""Board color themes — six selectable square-color pairs.

Usage:
    from app.ui.board_themes import BOARD_THEMES, load_board_theme, save_board_theme
"""

from __future__ import annotations
import json
from pathlib import Path

from app.config import USER_HOME


# ── Theme registry (ordered: display order in the picker) ─────────────────
BOARD_THEMES: dict[str, dict[str, str]] = {
    "Classic":  {"dark": "#b58863", "light": "#f0d9b5"},
    "Ocean":    {"dark": "#4b9ca8", "light": "#e8f4f8"},
    "Midnight": {"dark": "#2c3e6b", "light": "#7b8eb4"},
    "Forest":   {"dark": "#4a6741", "light": "#d8cfa8"},
    "Rose":     {"dark": "#b87070", "light": "#f5eee6"},
    "Slate":    {"dark": "#5a6470", "light": "#e8e8e0"},
}

DEFAULT_THEME = "Classic"

_PREFS_FILE = USER_HOME / "board_theme.json"


def load_board_theme() -> str:
    try:
        name = json.loads(_PREFS_FILE.read_text()).get("theme", DEFAULT_THEME)
        return name if name in BOARD_THEMES else DEFAULT_THEME
    except Exception:
        return DEFAULT_THEME


def save_board_theme(name: str) -> None:
    try:
        _PREFS_FILE.write_text(json.dumps({"theme": name}))
    except Exception:
        pass
