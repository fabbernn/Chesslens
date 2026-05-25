"""
Opening detector — longest-prefix match against the lichess ECO database.

The TSV at assets/openings/openings.tsv contains 3,704 openings in the format:
    eco<TAB>name<TAB>pgn

detect(move_sans) returns (eco_code, name) for the deepest matched opening,
or None if the position is out of book.
"""

from __future__ import annotations
import re
from pathlib import Path
from typing import Optional

_DB: dict[tuple[str, ...], tuple[str, str]] | None = None

_TSV = (Path(__file__).resolve().parent.parent.parent
        / "assets" / "openings" / "openings.tsv")


def _norm(san: str) -> str:
    """Strip check/mate suffixes so DB and analyzer SANs compare cleanly."""
    return san.rstrip('+#')


def _load() -> dict[tuple[str, ...], tuple[str, str]]:
    global _DB
    if _DB is not None:
        return _DB
    db: dict[tuple[str, ...], tuple[str, str]] = {}
    try:
        with _TSV.open(encoding="utf-8") as f:
            next(f)  # skip header row
            for line in f:
                parts = line.rstrip("\n").split("\t", 2)
                if len(parts) < 3:
                    continue
                eco, name, pgn = parts
                tokens = pgn.split()
                moves = tuple(
                    _norm(t) for t in tokens
                    if not re.match(r'^\d+\.', t)
                    and t not in {'1-0', '0-1', '1/2-1/2', '*'}
                )
                if moves:
                    db[moves] = (eco, name)
    except OSError:
        pass
    _DB = db
    return _DB


def detect(move_sans: list[str]) -> Optional[tuple[str, str]]:
    """Return (eco_code, opening_name) for the longest matching prefix, or None."""
    if not move_sans:
        return None
    db = _load()
    key = tuple(_norm(s) for s in move_sans)
    for length in range(len(key), 0, -1):
        match = db.get(key[:length])
        if match is not None:
            return match
    return None
