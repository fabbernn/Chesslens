"""
Board graphics items — the things drawn inside the QGraphicsScene.

PieceItem    — a chess piece. Inherits from QGraphicsObject (NOT Pixmap-
               Item) so QPropertyAnimation can drive its `pos` property
               for smooth GPU-accelerated movement.

ArrowItem    — a chess.com-style arrow between two squares. Used by both
               the engine best-move arrow and user-drawn arrows.

CircleItem   — a hollow ring on a square — user's right-click highlight.

These are pure presentation objects. They don't know about chess rules.
"""

from __future__ import annotations
import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QGraphicsItem, QGraphicsObject

from app.ui.theme import COLORS


# ═════════════════════════════════════════════════════════════════════════════
#  PIECE ITEM
# ═════════════════════════════════════════════════════════════════════════════
class PieceItem(QGraphicsObject):
    """
    A chess piece that can be animated via QPropertyAnimation on `pos`.

    Owns its pixmap. Repaint when pixmap is swapped (e.g. on flip/resize).
    """

    Z_VALUE = 30

    def __init__(self, pixmap: QPixmap, size_px: int,
                 square: int) -> None:
        super().__init__()
        self._pixmap = pixmap
        self._size = size_px
        self.square = square              # current chess square (logical)
        self.setZValue(self.Z_VALUE)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        # Smooth transformations during animation
        self.setTransformationMode(Qt.TransformationMode.SmoothTransformation) \
            if hasattr(self, "setTransformationMode") else None
        # Cache mode helps if the item is animated a lot
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)

    # ─────────────────────────────────────────────────────────────────────
    def set_pixmap(self, pixmap: QPixmap) -> None:
        self._pixmap = pixmap
        self.update()

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self._size, self._size)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.drawPixmap(QRectF(0, 0, self._size, self._size), self._pixmap,
                           QRectF(self._pixmap.rect()))


# ═════════════════════════════════════════════════════════════════════════════
#  ARROW ITEM — chess.com-style fat arrow
# ═════════════════════════════════════════════════════════════════════════════
class ArrowItem(QGraphicsObject):
    """
    A directional arrow drawn between two square centers.
    Coordinates are in scene space (square center pixels).
    """

    Z_VALUE_USER   = 40   # above pieces
    Z_VALUE_ENGINE = 20   # below pieces

    def __init__(self,
                 from_center: QPointF,
                 to_center: QPointF,
                 square_px: int,
                 color: str | None = None,
                 opacity: float = 0.85,
                 above_pieces: bool = True,
                 corner: QPointF | None = None) -> None:
        super().__init__()
        self._from = QPointF(from_center)
        self._to   = QPointF(to_center)
        self._corner = QPointF(corner) if corner is not None else None
        self._sq   = square_px
        self._color = QColor(color if color is not None else COLORS.arrow_best)
        self._color.setAlphaF(opacity)
        self.setZValue(self.Z_VALUE_USER if above_pieces else self.Z_VALUE_ENGINE)
        self._build_path()

    # ─────────────────────────────────────────────────────────────────────
    def _build_path(self) -> None:
        """Compute the arrow polygon. Straight line OR L-shaped via corner."""
        if self._corner is not None:
            self._build_l_path()
        else:
            self._build_straight_path()

    def _build_straight_path(self) -> None:
        s = self._sq
        x1, y1 = self._from.x(), self._from.y()
        x2, y2 = self._to.x(),   self._to.y()
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy)
        if length < 1:
            self._path = QPainterPath()
            return

        ux, uy = dx / length, dy / length     # forward unit vector
        px, py = -uy, ux                       # perpendicular

        shaft_half = s * 0.16                 # half-width of the shaft
        head_half  = s * 0.36                 # half-width of arrowhead
        head_len   = s * 0.36                 # arrowhead length
        start_inset = s * 0.30                # don't start at exact center

        sx = x1 + ux * start_inset
        sy = y1 + uy * start_inset
        ex = x2 - ux * head_len
        ey = y2 - uy * head_len

        path = QPainterPath()
        # Shaft (quad)
        path.moveTo(sx + px * shaft_half, sy + py * shaft_half)
        path.lineTo(sx - px * shaft_half, sy - py * shaft_half)
        path.lineTo(ex - px * shaft_half, ey - py * shaft_half)
        path.lineTo(ex + px * shaft_half, ey + py * shaft_half)
        path.closeSubpath()
        # Arrowhead (triangle)
        path.moveTo(x2, y2)
        path.lineTo(ex + px * head_half, ey + py * head_half)
        path.lineTo(ex - px * head_half, ey - py * head_half)
        path.closeSubpath()

        self._path = path

    def _build_l_path(self) -> None:
        """Build an L-shaped arrow: from → corner → to. Used for knight moves."""
        s = self._sq
        shaft_half = s * 0.16
        head_half  = s * 0.36
        head_len   = s * 0.36
        start_inset = s * 0.30

        x0, y0 = self._from.x(),   self._from.y()
        xc, yc = self._corner.x(), self._corner.y()
        x2, y2 = self._to.x(),     self._to.y()

        # Segment 1 direction: from -> corner
        d1x, d1y = xc - x0, yc - y0
        l1 = math.hypot(d1x, d1y)
        if l1 < 1:
            self._path = QPainterPath()
            return
        u1x, u1y = d1x / l1, d1y / l1
        p1x, p1y = -u1y, u1x

        # Segment 2 direction: corner -> to
        d2x, d2y = x2 - xc, y2 - yc
        l2 = math.hypot(d2x, d2y)
        if l2 < 1:
            self._build_straight_path()
            return
        u2x, u2y = d2x / l2, d2y / l2
        p2x, p2y = -u2y, u2x

        # Start point (inset from "from")
        sx = x0 + u1x * start_inset
        sy = y0 + u1y * start_inset

        # Tail end of arrowhead (inset from "to")
        ex = x2 - u2x * head_len
        ey = y2 - u2y * head_len

        # Determine which side of the L the corner bulges on.
        # cross product of u1 × u2; sign tells direction of bend.
        cross = u1x * u2y - u1y * u2x
        bend_sign = 1.0 if cross > 0 else -1.0

        path = QPainterPath()
        # Outer corner (away from bend direction)
        c_out_x = xc - p1x * shaft_half * bend_sign + u1x * shaft_half * bend_sign
        c_out_y = yc - p1y * shaft_half * bend_sign + u1y * shaft_half * bend_sign
        # Use a simpler approach: two rectangles meeting at the corner.

        # Segment 1 rectangle: from (sx,sy) to (xc,yc)
        path.moveTo(sx + p1x * shaft_half, sy + p1y * shaft_half)
        path.lineTo(sx - p1x * shaft_half, sy - p1y * shaft_half)
        # Extend slightly past corner so we miter-join
        path.lineTo(xc - p1x * shaft_half, yc - p1y * shaft_half)
        path.lineTo(xc + p1x * shaft_half, yc + p1y * shaft_half)
        path.closeSubpath()

        # Segment 2 rectangle: from (xc,yc) to (ex,ey)
        path.moveTo(xc + p2x * shaft_half, yc + p2y * shaft_half)
        path.lineTo(xc - p2x * shaft_half, yc - p2y * shaft_half)
        path.lineTo(ex - p2x * shaft_half, ey - p2y * shaft_half)
        path.lineTo(ex + p2x * shaft_half, ey + p2y * shaft_half)
        path.closeSubpath()

        # Corner fill — small square around the corner to hide the gap
        path.moveTo(xc - shaft_half, yc - shaft_half)
        path.lineTo(xc + shaft_half, yc - shaft_half)
        path.lineTo(xc + shaft_half, yc + shaft_half)
        path.lineTo(xc - shaft_half, yc + shaft_half)
        path.closeSubpath()

        # Arrowhead at (x2, y2), pointing along u2
        path.moveTo(x2, y2)
        path.lineTo(ex + p2x * head_half, ey + p2y * head_half)
        path.lineTo(ex - p2x * head_half, ey - p2y * head_half)
        path.closeSubpath()

        self._path = path

    def update_endpoints(self, from_center: QPointF, to_center: QPointF) -> None:
        """Re-target the arrow (used for live preview during drag)."""
        # CRITICAL: bounding rect is about to change. Without this call Qt's
        # scene index gets corrupted and segfaults during rapid mouse drags.
        self.prepareGeometryChange()
        self._from = QPointF(from_center)
        self._to   = QPointF(to_center)
        self._build_path()
        self.update()

    # ─────────────────────────────────────────────────────────────────────
    def boundingRect(self) -> QRectF:
        return self._path.boundingRect().adjusted(-4, -4, 4, 4)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self._color))
        painter.drawPath(self._path)


# ═════════════════════════════════════════════════════════════════════════════
#  CIRCLE ITEM — user right-click highlight on a square
# ═════════════════════════════════════════════════════════════════════════════
class CircleItem(QGraphicsObject):
    """Hollow ring drawn on a square — chess.com's right-click highlight."""

    Z_VALUE = 41

    def __init__(self, center: QPointF, square_px: int,
                 color: str | None = None, opacity: float = 0.85) -> None:
        super().__init__()
        self._center = center
        self._sq = square_px
        self._color = QColor(color if color is not None else COLORS.arrow_user)
        self._color.setAlphaF(opacity)
        self.setZValue(self.Z_VALUE)

    def boundingRect(self) -> QRectF:
        s = self._sq
        return QRectF(self._center.x() - s/2 - 4, self._center.y() - s/2 - 4,
                      s + 8, s + 8)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        s = self._sq
        # Ring thickness ~ 9% of square
        pen = QPen(self._color, s * 0.09)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        r = s * 0.39
        painter.drawEllipse(self._center, r, r)
