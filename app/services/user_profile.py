"""
User profile service — tracks who the user is across analyzed games.

The user adds the chess usernames they play under (e.g. "hikaru" on
chess.com, "yourname" on lichess). When a PGN is loaded, ChessLens
checks the [White] and [Black] headers against this list and detects which
color the user played — used to:

  * Auto-flip the board so the user's pieces sit on the bottom
  * Auto-filter the voice coach to only narrate the user's own moves
  * Annotate player labels with "• you" so the user knows at a glance
    which side they were on

Stored at ~/.chesslens/user_profile.json so it persists across sessions.
"""

from __future__ import annotations
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Callable

from app.config import MODELS_DIR


PROFILE_PATH = MODELS_DIR.parent / "user_profile.json"

_log = logging.getLogger(__name__)


@dataclass
class UserProfile:
    """All identities the user goes by. Matched case-insensitively."""

    usernames: list = field(default_factory=list)
    guide_seen: bool = False
    # Listeners invoked whenever the username list changes — lets UI react
    # (e.g. refresh the player labels, re-evaluate auto color detection).
    _listeners: list = field(default_factory=list, repr=False)

    # ── Persistence ────────────────────────────────────────────────────
    @classmethod
    def load(cls) -> "UserProfile":
        """Read the profile from disk. Returns an empty profile if missing.

        Specific exceptions are caught and logged rather than swallowed
        with a bare `except: pass`, so a wiped profile is traceable via
        the application log rather than vanishing silently.
        """
        p = cls()
        if not PROFILE_PATH.exists():
            return p
        try:
            with open(PROFILE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError, ValueError) as e:
            _log.warning(
                "UserProfile: failed to load %s (%s) — starting fresh",
                PROFILE_PATH, e,
            )
            return p
        names = data.get("usernames", [])
        if not isinstance(names, list):
            _log.warning(
                "UserProfile: 'usernames' in %s is not a list — ignoring",
                PROFILE_PATH,
            )
            return p
        # Deduplicate (preserving order) and strip whitespace
        seen: set = set()
        for name in names:
            s = str(name).strip()
            if s and s.lower() not in seen:
                seen.add(s.lower())
                p.usernames.append(s)
        p.guide_seen = bool(data.get("guide_seen", False))
        return p

    def save(self) -> None:
        """Atomic write: tmp file then rename so a crash mid-write can't
        corrupt the JSON. OSError caught and logged; everything else
        bubbles up since it indicates a real bug.
        """
        try:
            PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
            tmp = PROFILE_PATH.with_suffix(".json.tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(
                    {"usernames": self.usernames, "guide_seen": self.guide_seen},
                    f, indent=2,
                )
            os.replace(tmp, PROFILE_PATH)
        except OSError as e:
            _log.warning(
                "UserProfile: failed to save %s (%s) — changes won't persist",
                PROFILE_PATH, e,
            )
        for cb in list(self._listeners):
            try:
                cb()
            except Exception as e:
                _log.warning("UserProfile listener raised: %s", e)

    # ── Mutation ───────────────────────────────────────────────────────
    def add(self, name: str) -> bool:
        """Add a username. Returns True if it was actually new."""
        name = (name or "").strip()
        if not name or self.has(name):
            return False
        self.usernames.append(name)
        self.save()
        return True

    def remove(self, name: str) -> bool:
        """Remove a username (case-insensitive). Returns True on success."""
        nl = name.lower()
        new = [u for u in self.usernames if u.lower() != nl]
        if len(new) == len(self.usernames):
            return False
        self.usernames = new
        self.save()
        return True

    # ── Lookups ────────────────────────────────────────────────────────
    def has(self, name: str) -> bool:
        """Case-insensitive membership test."""
        if not name:
            return False
        nl = name.lower()
        return any(u.lower() == nl for u in self.usernames)

    def detect_color(self, parsed) -> Optional[str]:
        """Return 'white' or 'black' if the PGN header matches one of the
        saved usernames. White takes precedence if (somehow) both match.
        """
        if parsed is None or not hasattr(parsed, "headers"):
            return None
        if self.has(parsed.headers.get("White", "")):
            return "white"
        if self.has(parsed.headers.get("Black", "")):
            return "black"
        return None

    # ── Listeners ──────────────────────────────────────────────────────
    def mark_guide_seen(self) -> None:
        self.guide_seen = True
        self.save()

    def on_change(self, callback: Callable[[], None]) -> None:
        self._listeners.append(callback)
