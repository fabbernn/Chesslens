"""
Piece renderer — converts SVG pieces into QPixmaps.

Supports two modes:
  * Default — uses python-chess chess.svg.piece() (built-in vector pieces)
  * Named set — loads SVG files from assets/pieces/{set_name}/

Pieces are rendered at 2× the target pixel size, then the devicePixelRatio
is set to 2.0 so Qt scales them down with proper antialiasing on all DPIs.
"""

from __future__ import annotations

import chess
import chess.svg

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from app.ui.piece_sets import PIECE_SETS, svg_path


class PieceRenderer:
    """Caches rendered piece pixmaps keyed by symbol + size."""

    _DPR = 2.0

    def __init__(self, square_px: int) -> None:
        self._size      = square_px
        self._set_name: str | None = None   # None until first set_piece_set call
        self._cache: dict[str, QPixmap] = {}

    # ─────────────────────────────────────────────────────────────────────
    def set_size(self, square_px: int) -> None:
        if square_px != self._size:
            self._size = square_px
            self._cache.clear()

    def set_piece_set(self, name: str) -> None:
        """Switch piece set by name (key from PIECE_SETS). Clears the cache."""
        folder = PIECE_SETS.get(name)
        if folder != self._set_name:
            self._set_name = folder
            self._cache.clear()

    @property
    def size(self) -> int:
        return self._size

    # ─────────────────────────────────────────────────────────────────────
    def pixmap_for(self, piece: chess.Piece) -> QPixmap:
        key = piece.symbol()
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        physical = int(self._size * self._DPR)

        if self._set_name is None:
            svg_bytes = chess.svg.piece(piece, size=physical).encode("utf-8")
        else:
            path = svg_path(self._set_name, piece.color, piece.piece_type)
            svg_bytes = path.read_bytes()

        renderer = QSvgRenderer(QByteArray(svg_bytes))
        pm = QPixmap(physical, physical)
        pm.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        renderer.render(painter)
        painter.end()

        pm.setDevicePixelRatio(self._DPR)
        self._cache[key] = pm
        return pm

    def warmup(self) -> None:
        for color in (chess.WHITE, chess.BLACK):
            for ptype in (chess.PAWN, chess.KNIGHT, chess.BISHOP,
                          chess.ROOK, chess.QUEEN, chess.KING):
                self.pixmap_for(chess.Piece(ptype, color))
