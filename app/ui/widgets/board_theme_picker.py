"""BoardThemePicker — a compact row of clickable mini-board swatches.

Each swatch shows a 2×2 chess-square pattern using the theme's dark/light
colors. Clicking a swatch emits `theme_selected(name)`.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QSizePolicy, QWidget

from app.ui.board_themes import BOARD_THEMES
from app.ui.theme import COLORS


class _ThemeSwatch(QFrame):
    """Mini 2×2 board pattern — one theme option."""

    clicked = Signal(str)

    def __init__(self, name: str, dark: str, light: str,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._name  = name
        self._dark  = dark
        self._light = light
        self._active = False
        self.setFixedSize(36, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(name)

    def set_active(self, active: bool) -> None:
        self._active = active
        self.update()

    def paintEvent(self, _) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()
        hw, hh = w // 2, h // 2
        r = 3  # corner radius

        # Clip to rounded rect so colors don't bleed past the corners
        from PySide6.QtGui import QPainterPath
        clip = QPainterPath()
        clip.addRoundedRect(0, 0, w, h, r, r)
        p.setClipPath(clip)

        # 2×2 chess pattern
        p.fillRect(0,   0,  hw,    hh,    QColor(self._dark))
        p.fillRect(hw,  0,  w-hw,  hh,    QColor(self._light))
        p.fillRect(0,   hh, hw,    h-hh,  QColor(self._light))
        p.fillRect(hw,  hh, w-hw,  h-hh,  QColor(self._dark))

        p.setClipping(False)

        # Border — white ring when selected (accent green blends into board colors)
        if self._active:
            p.setPen(QPen(QColor("#ffffff"), 2.5))
            p.drawRoundedRect(1, 1, w - 2, h - 2, r - 1, r - 1)
        else:
            p.setPen(QPen(QColor(COLORS.border), 1.0))
            p.drawRoundedRect(0, 0, w - 1, h - 1, r, r)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._name)
        super().mousePressEvent(event)


class BoardThemePicker(QWidget):
    """Horizontal row of theme swatches."""

    theme_selected = Signal(str)   # emits the theme name on click

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._swatches: dict[str, _ThemeSwatch] = {}
        for name, colors in BOARD_THEMES.items():
            sw = _ThemeSwatch(name, colors["dark"], colors["light"])
            sw.clicked.connect(self._on_click)
            layout.addWidget(sw)
            self._swatches[name] = sw

        layout.addStretch(1)
        self._active: str | None = None
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    # ─────────────────────────────────────────────────────────────────────
    def set_active_theme(self, name: str) -> None:
        if self._active and self._active in self._swatches:
            self._swatches[self._active].set_active(False)
        self._active = name
        if name in self._swatches:
            self._swatches[name].set_active(True)

    def _on_click(self, name: str) -> None:
        self.set_active_theme(name)
        self.theme_selected.emit(name)
