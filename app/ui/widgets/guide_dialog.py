"""
Quick-start guide dialog — animated walkthrough for getting a PGN.

Shows automatically on first launch (user_profile.guide_seen == False).
Accessible any time via the ? button in the left panel.
"""

from __future__ import annotations

from PySide6.QtCore import (
    Qt, QPoint, QTimer, QPropertyAnimation, QEasingCurve,
    QParallelAnimationGroup, Signal,
)
from PySide6.QtGui import QPainter, QColor
from PySide6.QtWidgets import (
    QDialog, QFrame, QGraphicsOpacityEffect, QHBoxLayout,
    QLabel, QPushButton, QVBoxLayout, QWidget,
)

from app.ui.theme import COLORS, FONTS, SPACE


_STEPS: dict[str, list[tuple[str, str]]] = {
    "Chess.com": [
        ("1", "Open any game you played → click <b>Share &amp; Export</b>"),
        ("2", "Click <b>Copy PGN</b>"),
        ("3", "Paste into ChessLens with <b>Ctrl+V</b>"),
    ],
    "Lichess": [
        ("1", "Open any game → click <b>Share &amp; FEN</b>"),
        ("2", "Click <b>Copy PGN</b>"),
        ("3", "Paste into ChessLens with <b>Ctrl+V</b>"),
    ],
}

_STEP_H    = 56   # px height per step row (enough for 2-line wrapping text)
_STEP_GAP  = 10   # px gap between steps
_SLIDE_PX  = 8    # px downward offset at animation start
_CARD_W    = 480
_CARD_PAD  = SPACE.xl   # 24px — matches card margin


class GuideDialog(QDialog):
    """Dark overlay + centered card with animated per-tab steps."""

    got_it = Signal()   # emitted only when user clicks "Got it"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self._active_tab  = 0
        self._anim_refs: list = []  # keep QPropertyAnimation objects alive

        self._card = self._build_card()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(self._card, 0, Qt.AlignmentFlag.AlignVCenter)
        row.addStretch()
        outer.addStretch()
        outer.addLayout(row)
        outer.addStretch()

    # ── Overlay ───────────────────────────────────────────────────────────────
    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(0, 0, 0, 170))
        p.end()

    def showEvent(self, event) -> None:
        if self.parent():
            self.resize(self.parent().size())
            self.move(self.parent().mapToGlobal(QPoint(0, 0)))
        super().showEvent(event)
        QTimer.singleShot(60, lambda: self._switch_tab(0))

    # ── Card ──────────────────────────────────────────────────────────────────
    def _build_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("GuideCard")
        card.setFixedWidth(_CARD_W)
        card.setStyleSheet(
            f"QFrame#GuideCard {{ background-color: {COLORS.bg_card};"
            f" border-radius: 12px; border: 1px solid {COLORS.border}; }}"
        )

        vbox = QVBoxLayout(card)
        vbox.setContentsMargins(_CARD_PAD, _CARD_PAD, _CARD_PAD, _CARD_PAD)
        vbox.setSpacing(SPACE.lg)

        # Title
        title = QLabel("How to get your PGN")
        title.setStyleSheet(
            f"color: {COLORS.text}; font-size: {FONTS.lg}pt; font-weight: 700;"
            f" background: transparent; border: none;"
        )
        vbox.addWidget(title)

        # Tab row
        tab_row = QHBoxLayout()
        tab_row.setContentsMargins(0, 0, 0, 0)
        tab_row.setSpacing(0)
        self._tab_btns: list[QPushButton] = []
        for i, label in enumerate(_STEPS.keys()):
            btn = QPushButton(label)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setCheckable(True)
            btn.setChecked(i == 0)
            btn.setFixedHeight(34)
            btn.clicked.connect(lambda _checked, idx=i: self._switch_tab(idx))
            self._tab_btns.append(btn)
            tab_row.addWidget(btn)
        tab_row.addStretch()
        vbox.addLayout(tab_row)

        self._apply_tab_styles()

        # Steps container — absolute-positioned children so pos() animations work
        container_h = 3 * _STEP_H + 2 * _STEP_GAP
        self._steps_container = QWidget()
        self._steps_container.setFixedHeight(container_h)
        self._steps_container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        vbox.addWidget(self._steps_container)

        # Divider
        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet(f"background-color: {COLORS.border};")
        vbox.addWidget(div)

        # "Got it" button
        btn_ok = QPushButton("Got it")
        btn_ok.setFixedHeight(40)
        btn_ok.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_ok.setStyleSheet(
            f"QPushButton {{ background-color: {COLORS.accent}; color: {COLORS.on_accent};"
            f" font-size: {FONTS.md}pt; font-weight: 600; border-radius: 6px; border: none; }}"
            f"QPushButton:hover {{ background-color: {COLORS.accent_hover}; }}"
            f"QPushButton:pressed {{ background-color: {COLORS.accent_pressed}; }}"
        )
        btn_ok.clicked.connect(self._on_got_it)
        vbox.addWidget(btn_ok)

        # Hint text
        hint = QLabel("Show again anytime with the ? button")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet(
            f"color: {COLORS.text_dim}; font-size: {FONTS.xs}pt;"
            f" background: transparent; border: none;"
        )
        vbox.addWidget(hint)

        return card

    def _apply_tab_styles(self) -> None:
        for i, btn in enumerate(self._tab_btns):
            active = (i == self._active_tab)
            btn.setStyleSheet(
                f"QPushButton {{ background-color: transparent;"
                f" color: {COLORS.text if active else COLORS.text_muted};"
                f" font-size: {FONTS.sm}pt; font-weight: {'600' if active else '400'};"
                f" border: none;"
                f" border-bottom: 2px solid {COLORS.accent if active else 'transparent'};"
                f" padding: 4px 16px; border-radius: 0px; }}"
                f"QPushButton:hover {{ color: {COLORS.text}; }}"
            )

    # ── Tab switching ─────────────────────────────────────────────────────────
    def _switch_tab(self, idx: int) -> None:
        self._active_tab = idx
        self._apply_tab_styles()
        for i, btn in enumerate(self._tab_btns):
            btn.setChecked(i == idx)

        # Remove old step widgets
        for child in list(self._steps_container.findChildren(QWidget)):
            child.hide()
            child.deleteLater()
        self._anim_refs.clear()

        tab_name  = list(_STEPS.keys())[idx]
        cont_w    = self._steps_container.width() or (_CARD_W - 2 * _CARD_PAD)
        placements: list[tuple[QWidget, QPoint]] = []

        for i, (num, text) in enumerate(_STEPS[tab_name]):
            row = self._make_step(num, text, cont_w)
            y_final = i * (_STEP_H + _STEP_GAP)
            row.setParent(self._steps_container)
            row.move(0, y_final + _SLIDE_PX)   # start below final position
            row.resize(cont_w, _STEP_H)
            row.show()
            placements.append((row, QPoint(0, y_final)))

        self._animate_steps(placements)

    def _make_step(self, num: str, text: str, width: int) -> QWidget:
        row = QWidget()
        row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        hl = QHBoxLayout(row)
        hl.setContentsMargins(0, 4, 0, 4)
        hl.setSpacing(SPACE.md)

        circle = QLabel(num)
        circle.setFixedSize(26, 26)
        circle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        circle.setStyleSheet(
            f"background-color: {COLORS.accent}; color: {COLORS.on_accent};"
            f" font-size: {FONTS.sm}pt; font-weight: 700; border-radius: 13px;"
        )
        hl.addWidget(circle, 0, Qt.AlignmentFlag.AlignVCenter)

        # Highlight <b> words in accent color
        styled = text.replace(
            "<b>", f"<b style='color:{COLORS.accent}; font-weight:600'>"
        )
        lbl = QLabel(styled)
        lbl.setTextFormat(Qt.TextFormat.RichText)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(
            f"color: {COLORS.text_muted}; font-size: {FONTS.md}pt;"
            f" background: transparent;"
        )
        hl.addWidget(lbl, 1)
        return row

    # ── Animation ─────────────────────────────────────────────────────────────
    def _animate_steps(self, placements: list[tuple[QWidget, QPoint]]) -> None:
        for i, (w, final_pos) in enumerate(placements):
            eff = QGraphicsOpacityEffect(w)
            w.setGraphicsEffect(eff)
            eff.setOpacity(0.0)

            op_anim = QPropertyAnimation(eff, b"opacity")
            op_anim.setDuration(200)
            op_anim.setStartValue(0.0)
            op_anim.setEndValue(1.0)
            op_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

            pos_anim = QPropertyAnimation(w, b"pos")
            pos_anim.setDuration(200)
            pos_anim.setStartValue(w.pos())
            pos_anim.setEndValue(final_pos)
            pos_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

            grp = QParallelAnimationGroup()
            grp.addAnimation(op_anim)
            grp.addAnimation(pos_anim)
            self._anim_refs.append(grp)   # prevent GC

            QTimer.singleShot(i * 150, grp.start)

    # ── Dismiss ───────────────────────────────────────────────────────────────
    def _on_got_it(self) -> None:
        self.got_it.emit()
        self.accept()
