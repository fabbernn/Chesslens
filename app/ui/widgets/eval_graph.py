"""
Eval graph — line chart of evaluation across the game.

Click anywhere to jump to that move (emits move_clicked signal).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from app.ui.theme import COLORS


class EvalGraph(QWidget):
    """A small horizontal eval curve. Click selects a move position."""

    move_clicked = Signal(int)     # 0-based position index

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(60)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)
        self._scores: list[float] = []
        self._cursor_idx: int = 0
        self._classifications: list[str] = []
        self._hover_x: float | None = None   # raw mouse X for the cursor line

    # ─────────────────────────────────────────────────────────────────────
    def set_scores(self, scores: list[float], cursor_idx: int = 0,
                   classifications: list[str] | None = None) -> None:
        """Update the curve. `classifications` is one per move (len = len(scores)-1)
        and is used to draw colored dots on the curve, chess.com-style."""
        self._scores = list(scores)
        self._cursor_idx = cursor_idx
        self._classifications = list(classifications) if classifications else []
        self.update()

    def set_cursor(self, idx: int) -> None:
        self._cursor_idx = idx
        self.update()

    # ─────────────────────────────────────────────────────────────────────
    def mouseMoveEvent(self, event) -> None:
        self._hover_x = event.position().x()
        self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:
        self._hover_x = None
        self.update()
        super().leaveEvent(event)

    @staticmethod
    def _smooth_path(pts: list[tuple[float, float]]) -> QPainterPath:
        """Cubic bezier through pts via catmull-rom control points."""
        path = QPainterPath()
        if not pts:
            return path
        path.moveTo(pts[0][0], pts[0][1])
        n = len(pts)
        for i in range(n - 1):
            x0, y0 = pts[max(0, i - 1)]
            x1, y1 = pts[i]
            x2, y2 = pts[i + 1]
            x3, y3 = pts[min(n - 1, i + 2)]
            path.cubicTo(
                x1 + (x2 - x0) / 6, y1 + (y2 - y0) / 6,
                x2 - (x3 - x1) / 6, y2 - (y3 - y1) / 6,
                x2, y2,
            )
        return path

    # ─────────────────────────────────────────────────────────────────────
    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._scores:
            x = event.position().x()
            w = max(1, self.width())
            n = max(1, len(self._scores) - 1)
            idx = round((x / w) * n)
            idx = max(0, min(len(self._scores) - 1, int(idx)))
            self.move_clicked.emit(idx)
            event.accept()
            return
        super().mousePressEvent(event)

    # ─────────────────────────────────────────────────────────────────────
    def paintEvent(self, _) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            return

        # Two-tone inset background — bg_input for dark half (recessed feel)
        p.fillRect(0, 0, w, h // 2, QColor(COLORS.graph_white))
        p.fillRect(0, h // 2, w, h - h // 2, QColor(COLORS.bg_input))

        # Subtle midline — warm neutral visible on both halves
        p.setPen(QPen(QColor(120, 115, 105, 110), 1))
        p.drawLine(0, h // 2, w, h // 2)

        # 1px inner border for inset effect
        p.setPen(QPen(QColor(COLORS.border_subtle), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(0, 0, w - 1, h - 1)

        if not self._scores:
            return

        n = len(self._scores)

        def xy(i: int, s: float) -> tuple[float, float]:
            x = (i / max(1, n - 1)) * w
            y = (h / 2) - (max(-6.0, min(6.0, s)) / 6.0) * (h / 2 - 2)
            return x, y

        pts = [xy(i, s) for i, s in enumerate(self._scores)]

        # Smooth filled area under the curve (catmull-rom bezier)
        fill_path = self._smooth_path(pts)
        fill_path.lineTo(w, h / 2)
        fill_path.lineTo(0, h / 2)
        fill_path.closeSubpath()
        accent_fill = QColor(COLORS.accent)
        accent_fill.setAlpha(50)
        p.fillPath(fill_path, QBrush(accent_fill))

        # Smooth stroke
        stroke_path = self._smooth_path(pts)
        pen = QPen(QColor(COLORS.accent))
        pen.setWidth(2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(stroke_path)

        # Classification dots — halos on blunder/brilliant for emphasis
        if self._classifications:
            DOT_COLOR = {
                "brilliant":  QColor(COLORS.cls_brilliant),
                "best":       QColor(COLORS.cls_best),
                "inaccuracy": QColor(COLORS.cls_inaccuracy),
                "mistake":    QColor(COLORS.cls_mistake),
                "blunder":    QColor(COLORS.cls_blunder),
            }
            DOT_RADIUS = {
                "blunder": 4, "mistake": 4,
                "brilliant": 4, "best": 3, "inaccuracy": 3,
            }
            for move_i, cls in enumerate(self._classifications):
                color = DOT_COLOR.get(cls)
                if color is None:
                    continue
                pos = move_i + 1
                if pos >= n:
                    continue
                dx, dy = pts[pos]
                r = DOT_RADIUS.get(cls, 3)
                # Outer halo ring for the most critical classifications
                if cls in ("blunder", "brilliant"):
                    halo = QColor(color)
                    halo.setAlpha(65)
                    p.setPen(QPen(halo, 1.5))
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.drawEllipse(QPoint(int(dx), int(dy)), r + 2, r + 2)
                p.setPen(QPen(QColor(0, 0, 0, 90), 1))
                p.setBrush(QBrush(color))
                p.drawEllipse(QPoint(int(dx), int(dy)), r, r)

        # Hover cursor line — vertical guide at mouse position
        if self._hover_x is not None:
            p.setOpacity(0.45)
            p.setPen(QPen(QColor(COLORS.text_dim), 1))
            p.drawLine(int(self._hover_x), 0, int(self._hover_x), h)
            p.setOpacity(1.0)

        # Cursor dot — accent ring with white fill, slightly larger than dots
        if 0 <= self._cursor_idx < n:
            cx, cy = pts[self._cursor_idx]
            p.setPen(QPen(QColor(COLORS.accent), 2))
            p.setBrush(QBrush(QColor("white")))
            p.drawEllipse(QPoint(int(cx), int(cy)), 5, 5)
