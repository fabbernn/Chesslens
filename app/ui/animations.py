"""
Animations — reusable QPropertyAnimation factories.

Keep all animation timing/easing/curves in ONE place so the app feels
consistent. Never hardcode an easing curve in a widget — import from here.
"""

from __future__ import annotations
from typing import Callable

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QObject,
    QPropertyAnimation,
    QPoint,
    QPointF,
    QRect,
    Qt,
    Property,
)
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget


# ─────────────────────────────────────────────────────────────────────────────
#  EASING — one curve per intent
# ─────────────────────────────────────────────────────────────────────────────
class Curves:
    """Premium-feel easing curves. Use these, don't roll your own."""

    # Standard UI motion — material-style
    STANDARD = QEasingCurve.Type.InOutCubic

    # Snappy entrance (UI element appearing)
    ENTER = QEasingCurve.Type.OutCubic

    # Soft exit (UI element disappearing)
    EXIT = QEasingCurve.Type.InCubic

    # Piece movement on board — chess.com-ish
    PIECE = QEasingCurve.Type.OutQuint

    # Settle/snap into place
    SETTLE = QEasingCurve.Type.OutBack


# ─────────────────────────────────────────────────────────────────────────────
#  OPACITY FADE
# ─────────────────────────────────────────────────────────────────────────────
def fade_in(widget: QWidget, duration_ms: int = 220,
            curve: QEasingCurve.Type = Curves.ENTER,
            on_finished: Callable | None = None) -> QPropertyAnimation:
    """Fade a widget from invisible → visible. Reuses existing effect if present."""
    effect = widget.graphicsEffect()
    if not isinstance(effect, QGraphicsOpacityEffect):
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration_ms)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(curve)
    if on_finished:
        anim.finished.connect(on_finished)
    anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    return anim


def fade_out(widget: QWidget, duration_ms: int = 180,
             curve: QEasingCurve.Type = Curves.EXIT,
             on_finished: Callable | None = None) -> QPropertyAnimation:
    effect = widget.graphicsEffect()
    if not isinstance(effect, QGraphicsOpacityEffect):
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration_ms)
    anim.setStartValue(1.0)
    anim.setEndValue(0.0)
    anim.setEasingCurve(curve)
    if on_finished:
        anim.finished.connect(on_finished)
    anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    return anim


# ─────────────────────────────────────────────────────────────────────────────
#  SLIDE / GEOMETRY
# ─────────────────────────────────────────────────────────────────────────────
def slide_to(widget: QWidget, end_pos: QPoint,
             duration_ms: int = 220,
             curve: QEasingCurve.Type = Curves.STANDARD) -> QPropertyAnimation:
    """Animate widget position from current to end_pos."""
    anim = QPropertyAnimation(widget, b"pos", widget)
    anim.setDuration(duration_ms)
    anim.setStartValue(widget.pos())
    anim.setEndValue(end_pos)
    anim.setEasingCurve(curve)
    anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    return anim


def animate_geometry(widget: QWidget, end_rect: QRect,
                     duration_ms: int = 220,
                     curve: QEasingCurve.Type = Curves.STANDARD) -> QPropertyAnimation:
    anim = QPropertyAnimation(widget, b"geometry", widget)
    anim.setDuration(duration_ms)
    anim.setStartValue(widget.geometry())
    anim.setEndValue(end_rect)
    anim.setEasingCurve(curve)
    anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    return anim


# ─────────────────────────────────────────────────────────────────────────────
#  STAGGERED REVEAL — fade in a list of widgets one after another
# ─────────────────────────────────────────────────────────────────────────────
def stagger_fade_in(widgets: list[QWidget],
                    stagger_ms: int = 60,
                    duration_ms: int = 220) -> None:
    """Fade in multiple widgets with a stagger between each."""
    for idx, w in enumerate(widgets):
        delay = idx * stagger_ms
        # Set opacity 0 immediately so they don't flash
        effect = QGraphicsOpacityEffect(w)
        effect.setOpacity(0.0)
        w.setGraphicsEffect(effect)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(delay, lambda w=w: fade_in(w, duration_ms))


# ─────────────────────────────────────────────────────────────────────────────
#  HOVER COLOR TRANSITION
#  Attach to any QWidget / QFrame to get smooth background interpolation.
# ─────────────────────────────────────────────────────────────────────────────
class HoverFade(QObject):
    """Smooth background-color hover transition for any QWidget.

    Installs itself as an event filter; no subclassing required.

    Usage::
        self._hover = HoverFade(self,
                                normal=COLORS.bg_card,
                                hover=COLORS.bg_card_hi)
    """

    def __init__(self, widget: QWidget, *,
                 normal: str,
                 hover: str,
                 duration_ms: int = 120,
                 css_class: str = "") -> None:
        super().__init__(widget)
        self._widget = widget
        self._normal = QColor(normal)
        self._hovered = QColor(hover)
        self._duration = duration_ms
        # If css_class is empty we fall back to the Python class name so
        # the selector targets only this widget type (avoids bleed-through).
        self._cls = css_class or type(widget).__name__
        self._t: float = 0.0
        self._anim: QPropertyAnimation | None = None
        widget.installEventFilter(self)
        self._apply()

    # Qt property — QPropertyAnimation drives this 0.0 → 1.0
    def _get_t(self) -> float:
        return self._t

    def _set_t(self, v: float) -> None:
        self._t = v
        self._apply()

    _progress = Property(float, _get_t, _set_t)

    def _lerp(self, t: float) -> str:
        a, b = self._normal, self._hovered
        r = int(a.red()   + t * (b.red()   - a.red()))
        g = int(a.green() + t * (b.green() - a.green()))
        bv = int(a.blue()  + t * (b.blue()  - a.blue()))
        return f"#{r:02x}{g:02x}{bv:02x}"

    def _apply(self) -> None:
        color = self._lerp(self._t)
        self._widget.setStyleSheet(
            f"{self._cls} {{ background-color: {color}; }}"
        )

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if obj is self._widget:
            if event.type() == QEvent.Type.Enter:
                self._animate(1.0)
            elif event.type() == QEvent.Type.Leave:
                self._animate(0.0)
        return False

    def _animate(self, target: float) -> None:
        if self._anim is not None:
            try:
                self._anim.stop()
            except RuntimeError:
                pass
            self._anim = None
        anim = QPropertyAnimation(self, b"_progress", self)
        anim.setDuration(self._duration)
        anim.setStartValue(self._t)
        anim.setEndValue(target)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.finished.connect(lambda: setattr(self, "_anim", None))
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
        self._anim = anim
