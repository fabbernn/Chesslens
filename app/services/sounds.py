"""
SoundService — low-latency move sound effects via QSoundEffect.

QSoundEffect is part of QtMultimedia (already included with PySide6 Essentials).
It's purpose-built for short sound effects with minimal latency, unlike
QMediaPlayer which is designed for streaming media.

Sound files are bundled in app/resources/sounds/.

Usage:
    sounds = SoundService()
    sounds.play_for_move(board_before, played_move)
    sounds.set_volume(0.6)
    sounds.set_enabled(True)
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional

import chess

from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QSoundEffect

from app.config import RESOURCE_DIR


SOUNDS_DIR = RESOURCE_DIR / "sounds"


class SoundService:
    """Plays short chess move sounds. Safe to call from main thread only."""

    # Sound IDs mapped to filenames (relative to SOUNDS_DIR)
    SOUND_FILES = {
        "move":     "move.wav",
        "capture":  "capture.wav",
        "check":    "check.wav",
        "castle":   "castle.wav",
        "promote":  "promote.wav",
        "end":      "end.wav",
        "ready":    "ready.wav",
    }

    def __init__(self) -> None:
        self._enabled = True
        self._volume = 0.6
        self._effects: dict[str, QSoundEffect] = {}
        self._load_all()

    # ─────────────────────────────────────────────────────────────────────
    def _load_all(self) -> None:
        """Pre-load every sound so the first play has no startup latency."""
        for sound_id, filename in self.SOUND_FILES.items():
            path = SOUNDS_DIR / filename
            if not path.exists():
                continue
            try:
                effect = QSoundEffect()
                effect.setSource(QUrl.fromLocalFile(str(path)))
                effect.setVolume(self._volume)
                self._effects[sound_id] = effect
            except Exception:
                # Audio system not available — degrade silently
                pass

    def is_available(self) -> bool:
        return len(self._effects) > 0

    # ─────────────────────────────────────────────────────────────────────
    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled

    def set_volume(self, v: float) -> None:
        self._volume = max(0.0, min(1.0, float(v)))
        for effect in self._effects.values():
            try:
                effect.setVolume(self._volume)
            except Exception:
                pass

    # ─────────────────────────────────────────────────────────────────────
    def play(self, sound_id: str) -> None:
        """Play a specific sound by id."""
        if not self._enabled:
            return
        effect = self._effects.get(sound_id)
        if effect is None:
            return
        try:
            effect.play()
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────────────────
    def play_for_move(self, board_before: chess.Board,
                      move: chess.Move,
                      gives_check: Optional[bool] = None) -> None:
        """Inspect the move and play the most appropriate sound.

        Priority: check > checkmate > capture/castle/promote > regular move.
        If gives_check is given, use it; otherwise compute from board.
        """
        if not self._enabled or move is None:
            return

        # Determine attributes — make sure we don't mutate the input board
        is_capture  = board_before.is_capture(move)
        is_castle   = board_before.is_castling(move)
        is_promote  = move.promotion is not None

        # Compute check on a temp board (or use cached value)
        if gives_check is None:
            tmp = board_before.copy(stack=False)
            tmp.push(move)
            is_check = tmp.is_check()
            is_mate  = tmp.is_checkmate()
        else:
            is_check = gives_check
            is_mate  = False  # caller must signal endgame separately

        # Priority order — check overrides everything
        if is_mate:
            self.play("end")
            return
        if is_check:
            self.play("check")
            return
        if is_promote:
            self.play("promote")
            return
        if is_castle:
            self.play("castle")
            return
        if is_capture:
            self.play("capture")
            return
        self.play("move")
