"""
Eval bar — thin vertical bar showing the engine's evaluation.

Animates smoothly between positions using QVariantAnimation.
"""

from __future__ import annotations

from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import QWidget

from app.config import BOARD_PX, EVAL_BAR_W
from app.ui.theme import COLORS


class EvalBar(QWidget):
    """White (bottom) fills against black (top). Center marks zero eval."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(EVAL_BAR_W, BOARD_PX)
        self._eval = 0.0
        self._displayed = 0.0      # animated value
        self._anim: QPropertyAnimation | None = None

    # Property used by QPropertyAnimation
    def _get_displayed(self) -> float: return self._displayed
    def _set_displayed(self, v: float) -> None:
        self._displayed = v
        self.update()
    displayed_eval = Property(float, _get_displayed, _set_displayed)

    # ─────────────────────────────────────────────────────────────────────
    def set_eval(self, score: float, animate: bool = True) -> None:
        # Clamp display to ±10 pawns (everything past that is "winning")
        clamped = max(-10.0, min(10.0, score))
        self._eval = clamped
        if not animate:
            self._displayed = clamped
            self.update()
            return
        # The previous animation may have been auto-deleted by DeleteWhenStopped.
        # Defensively check, then drop the reference if dead.
        if self._anim is not None:
            try:
                if self._anim.state() == QPropertyAnimation.State.Running:
                    self._anim.stop()
            except RuntimeError:
                # C++ object already deleted — that's fine, just clear ref
                pass
            self._anim = None

        anim = QPropertyAnimation(self, b"displayed_eval", self)
        anim.setDuration(280)
        anim.setStartValue(self._displayed)
        anim.setEndValue(clamped)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        # Clear the python reference when the underlying object is destroyed,
        # so we don't access a dead pointer next time.
        anim.finished.connect(lambda: setattr(self, "_anim", None))
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
        self._anim = anim

    # ─────────────────────────────────────────────────────────────────────
    def paintEvent(self, _) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()
        r = w / 2.0  # pill shape — radius = half the width

        # White's percentage — 0.5 == equal, 1.0 == white winning, 0.0 == black winning
        pct = 0.5 + (self._displayed / 10.0) * 0.45
        pct = max(0.03, min(0.97, pct))
        midline = int(h * (1.0 - pct))     # black on top → white on bottom

        # Clip all drawing to the pill shape
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(0, 0, w, h), r, r)
        p.setClipPath(clip)

        # Black top
        p.fillRect(0, 0, w, midline, QColor(COLORS.eval_bar_dark))
        # White bottom
        p.fillRect(0, midline, w, h - midline, QColor(COLORS.eval_bar_light))
        # Midline accent at the boundary
        p.fillRect(0, midline - 1, w, 2, QColor(COLORS.eval_bar_line))
