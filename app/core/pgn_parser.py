"""
PGN parser — pure Python, no Qt deps.

Parses a PGN string into a structured ParsedGame:
  - headers (White, Black, Date, etc.)
  - moves (chess.Move objects)
  - clock_times (seconds remaining per move, parsed from %clk comments)

This module is intentionally Qt-free so it can be tested in isolation.
"""

from __future__ import annotations
import io
import re
from dataclasses import dataclass, field
from typing import Optional

import chess
import chess.pgn


_CLK_RE = re.compile(r"\[%clk\s+(\d+):(\d+):(\d+(?:\.\d+)?)\]")


@dataclass
class ParsedGame:
    headers:     dict[str, str]              = field(default_factory=dict)
    moves:       list[chess.Move]            = field(default_factory=list)
    sans:        list[str]                   = field(default_factory=list)
    clock_times: list[Optional[float]]       = field(default_factory=list)
    starting_fen: str = chess.STARTING_FEN

    @property
    def white(self) -> str:  return self.headers.get("White", "White")
    @property
    def black(self) -> str:  return self.headers.get("Black", "Black")
    @property
    def result(self) -> str: return self.headers.get("Result", "*")
    @property
    def date(self) -> str:   return self.headers.get("Date", "")
    @property
    def white_elo(self) -> Optional[str]:
        v = self.headers.get("WhiteElo", "").strip()
        return v if v and v != "?" else None
    @property
    def black_elo(self) -> Optional[str]:
        v = self.headers.get("BlackElo", "").strip()
        return v if v and v != "?" else None


def parse_pgn(pgn_text: str) -> ParsedGame:
    """Parse a single-game PGN string."""
    game = chess.pgn.read_game(io.StringIO(pgn_text))
    if game is None:
        raise ValueError("Could not parse PGN")

    parsed = ParsedGame()
    parsed.headers = dict(game.headers)

    # Handle non-standard starting position (FEN header)
    fen = parsed.headers.get("FEN")
    if fen:
        parsed.starting_fen = fen
        board = chess.Board(fen)
    else:
        board = chess.Board()

    node = game
    while node.variations:
        node = node.variation(0)
        move = node.move
        if move is None:
            continue

        # Compute SAN before pushing
        try:
            san = board.san(move)
        except Exception:
            san = move.uci()

        parsed.moves.append(move)
        parsed.sans.append(san)
        board.push(move)

        # Parse clock annotation from this move's comment
        m = _CLK_RE.search(node.comment or "")
        if m:
            h, mn, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
            parsed.clock_times.append(h * 3600 + mn * 60 + s)
        else:
            parsed.clock_times.append(None)

    return parsed


def time_taken_per_move(clocks: list[Optional[float]]) -> list[Optional[float]]:
    """
    Given clock-remaining times per move, return the time each player
    spent on each move (None if unknown).

    For move i played by player P: time = clocks[i-2] - clocks[i]
    """
    out: list[Optional[float]] = [None] * len(clocks)
    for i, cur in enumerate(clocks):
        if cur is None:
            continue
        prev = clocks[i - 2] if i >= 2 else None
        if prev is None:
            continue
        out[i] = max(0.0, prev - cur)
    return out
