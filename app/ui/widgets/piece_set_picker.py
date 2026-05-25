"""PieceSetPicker — a row of clickable piece-set thumbnails.

Each swatch renders the white king from that set at ~40×40px.
Clicking emits `set_selected(name)`.
"""

from __future__ import annotations

import chess
import chess.svg

from PySide6.QtCore import QByteArray, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QSizePolicy, QWidget

from app.config import PIECES_DIR
from app.ui.piece_sets import PIECE_SETS
from app.ui.theme import COLORS

_WHITE_KING = chess.Piece(chess.KING, chess.WHITE)
_SWATCH_W = 44
_SWATCH_H = 44
_DPR = 2.0


def _render_king_pixmap(set_folder: str | None) -> QPixmap:
    """Render a white king at _SWATCH_W×_SWATCH_H for the given set (None = Default)."""
    physical = int(_SWATCH_W * _DPR)
    if set_folder is None:
        svg_bytes = chess.svg.piece(_WHITE_KING, size=physical).encode("utf-8")
    else:
        path = PIECES_DIR / set_folder / "wK.svg"
        svg_bytes = path.read_bytes()

    renderer = QSvgRenderer(QByteArray(svg_bytes))
    pm = QPixmap(physical, physical)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    renderer.render(painter)
    painter.end()
    pm.setDevicePixelRatio(_DPR)
    return pm


class _PieceSwatch(QFrame):
    """Single piece-set thumbnail with label underneath."""

    clicked = Signal(str)

    def __init__(self, name: str, folder: str | None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._name   = name
        self._active = False
        self._pm     = _render_king_pixmap(folder)
        self.setFixedSize(_SWATCH_W + 4, _SWATCH_H + 4)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(name)

    def set_active(self, active: bool) -> None:
        self._active = active
        self.update()

    def paintEvent(self, _) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()
        r = 5

        # Background fill
        bg = QColor(COLORS.bg_panel if self._active else COLORS.bg_input)
        clip = QPainterPath()
        clip.addRoundedRect(0, 0, w, h, r, r)
        p.setClipPath(clip)
        p.fillRect(0, 0, w, h, bg)
        p.setClipping(False)

        # Piece pixmap — centred
        pm_w = int(self._pm.width()  / _DPR)
        pm_h = int(self._pm.height() / _DPR)
        ox = (w - pm_w) // 2
        oy = (h - pm_h) // 2
        p.drawPixmap(ox, oy, self._pm)

        # Border — accent ring when selected
        if self._active:
            p.setPen(QPen(QColor(COLORS.accent), 2.0))
            p.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), r - 1, r - 1)
        else:
            p.setPen(QPen(QColor(COLORS.border), 1.0))
            p.drawRoundedRect(QRectF(0, 0, w - 1, h - 1), r, r)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._name)
        super().mousePressEvent(event)


class PieceSetPicker(QWidget):
    """Horizontal row of piece-set swatches."""

    set_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._swatches: dict[str, _PieceSwatch] = {}
        for name, folder in PIECE_SETS.items():
            sw = _PieceSwatch(name, folder)
            sw.clicked.connect(self._on_click)
            layout.addWidget(sw)
            self._swatches[name] = sw

        layout.addStretch(1)
        self._active: str | None = None
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    def set_active_set(self, name: str) -> None:
        if self._active and self._active in self._swatches:
            self._swatches[self._active].set_active(False)
        self._active = name
        if name in self._swatches:
            self._swatches[name].set_active(True)

    def _on_click(self, name: str) -> None:
        self.set_active_set(name)
        self.set_selected.emit(name)
