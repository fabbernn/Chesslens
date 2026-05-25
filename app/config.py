"""App-wide configuration: paths, constants, identifiers."""

from __future__ import annotations
from pathlib import Path

# ─── App identity ────────────────────────────────────────────────────────────
APP_NAME    = "ChessLens"
APP_VERSION = "1.0.0"
APP_VENDOR  = "ChessLens"
APP_ID      = "com.chesslens.app"

# ─── Paths ────────────────────────────────────────────────────────────────────
PROJECT_ROOT  = Path(__file__).resolve().parent.parent
RESOURCE_DIR  = PROJECT_ROOT / "app" / "resources"
SOUNDS_DIR    = RESOURCE_DIR / "sounds"
FONTS_DIR     = RESOURCE_DIR / "fonts"
ICONS_DIR     = RESOURCE_DIR / "icons"
PIECES_DIR    = PROJECT_ROOT / "assets" / "pieces"

# User data — engine, models, cache
USER_HOME    = Path.home() / ".chesslens"
USER_HOME.mkdir(exist_ok=True)
ENGINE_PATH  = USER_HOME / ("stockfish.exe" if Path("C:/").exists() else "stockfish")
MODELS_DIR   = USER_HOME / "models"
MODELS_DIR.mkdir(exist_ok=True)

# ─── Window defaults ──────────────────────────────────────────────────────────
WINDOW_DEFAULT_W = 1400
WINDOW_DEFAULT_H = 860
WINDOW_MIN_W     = 1180
WINDOW_MIN_H     = 720

# Panel widths (left, right). Center expands.
LEFT_PANEL_W   = 320
RIGHT_PANEL_W  = 320
TOPBAR_HEIGHT  = 56

# ─── Board defaults ───────────────────────────────────────────────────────────
SQUARE_PX        = 64               # one chess square in pixels
BOARD_PX         = SQUARE_PX * 8    # 512
EVAL_BAR_W       = 12

# Animation timing — premium feel (chess.com mirrors these closely)
ANIM_MOVE_MS     = 180   # piece movement
ANIM_HOVER_MS    = 120   # button hover transitions
ANIM_FADE_MS     = 220   # general fade-in
ANIM_FRAME_MS    = 16    # ~60fps

# ─── Engine ───────────────────────────────────────────────────────────────────
ENGINE_DEPTH = 16
ENGINE_HASH_MB = 128
ENGINE_THREADS = 2
