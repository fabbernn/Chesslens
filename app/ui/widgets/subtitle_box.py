"""
SubtitleBox — status bar showing the current voice line below the board.

Styled as a contained full-width bar (not a pill): always-visible dark
background with a top border, speaker icon, and elided single-line text.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy

from app.config import ICONS_DIR
from app.ui.icon_utils import svg_pixmap
from app.ui.theme import COLORS, FONTS, SPACE


class SubtitleBox(QFrame):
    """A single-line status bar that mirrors the active voice line.

    Reserves a fixed 42px height at all times so the board layout never
    shifts. Styled as a bar with a permanent background and top border.
    """

    FIXED_HEIGHT = 42

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(self.FIXED_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(
            "SubtitleBox {"
            " background-color: #1e1d1a;"
            " border: none;"
            " border-top: 1px solid #2a2825;"
            " border-radius: 0px;"
            "}"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACE.lg, 0, SPACE.lg, 0)
        layout.setSpacing(SPACE.sm)

        # Speaker icon — always visible, green accent
        self._icon = QLabel()
        try:
            _px = svg_pixmap(ICONS_DIR / "volume.svg", 14, COLORS.accent)
            self._icon.setPixmap(_px)
        except Exception:
            self._icon.setText("🔊")
        self._icon.setFixedSize(18, 18)
        self._icon.hide()
        layout.addWidget(self._icon, alignment=Qt.AlignmentFlag.AlignVCenter)

        self._label = QLabel("")
        self._label.setWordWrap(False)
        self._label.setTextFormat(Qt.TextFormat.PlainText)
        self._label.setStyleSheet(
            f"color: #c8c4be; font-size: {FONTS.md}pt;"
            f"background: transparent; border: none;"
        )
        self._label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(self._label, 1)

        self._current_text = ""

    def set_text(self, text: str) -> None:
        text = (text or "").strip()
        if text == self._current_text:
            return
        self._current_text = text

        if text:
            self._icon.show()
            self._label.setText(self._elide(text))
        else:
            self._icon.hide()
            self._label.setText("")

    def clear(self) -> None:
        self.set_text("")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._current_text:
            self._label.setText(self._elide(self._current_text))

    def _elide(self, text: str) -> str:
        if not text:
            return ""
        avail = max(50, self._label.width() - 6)
        fm = QFontMetrics(self._label.font())
        return fm.elidedText(text, Qt.TextElideMode.ElideRight, avail)
