"""Piece set registry — three Lichess open-source SVG sets (Cburnett, Merida, Alpha).

Prefs are stored alongside board theme in ~/.chesslens/board_theme.json so
both customization options live in one file.
"""

from __future__ import annotations
import json
from pathlib import Path

from app.config import USER_HOME, PIECES_DIR

# ── Registry ──────────────────────────────────────────────────────────────────
# All sets load from assets/pieces/. python-chess built-in SVG is cburnett,
# so a separate "Default" entry would be visually identical to Cburnett.
PIECE_SETS: dict[str, str] = {
    "Cburnett": "cburnett",
    "Merida":   "merida",
    "Alpha":    "alpha",
}

DEFAULT_PIECE_SET = "Cburnett"

_PREFS_FILE = USER_HOME / "board_theme.json"

# ── Helpers ───────────────────────────────────────────────────────────────────
_COLOR_PREFIX = {True: "w", False: "b"}   # chess.WHITE → "w"
_PIECE_LETTER = {1: "P", 2: "N", 3: "B", 4: "R", 5: "Q", 6: "K"}


def svg_path(set_folder: str, piece_color: bool, piece_type: int) -> Path:
    """Return the Path to an SVG file for a given piece in a named set."""
    name = _COLOR_PREFIX[piece_color] + _PIECE_LETTER[piece_type]
    return PIECES_DIR / set_folder / f"{name}.svg"


def load_piece_set() -> str:
    try:
        name = json.loads(_PREFS_FILE.read_text()).get("piece_set", DEFAULT_PIECE_SET)
        return name if name in PIECE_SETS else DEFAULT_PIECE_SET
    except Exception:
        return DEFAULT_PIECE_SET


def save_piece_set(name: str) -> None:
    try:
        try:
            data = json.loads(_PREFS_FILE.read_text())
        except Exception:
            data = {}
        data["piece_set"] = name
        _PREFS_FILE.write_text(json.dumps(data))
    except Exception:
        pass
