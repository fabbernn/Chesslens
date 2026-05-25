"""BoardCustomizeDialog — modal for board theme + piece set selection.

Opened by a small "Customize" button in the board area.
Signals theme_selected and piece_set_selected whenever the user clicks a swatch;
the caller (main_window) applies them live and persists them.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from app.ui.theme import COLORS, FONTS, SPACE
from app.ui.widgets.board_theme_picker import BoardThemePicker
from app.ui.widgets.piece_set_picker import PieceSetPicker


class BoardCustomizeDialog(QDialog):
    """Modal for all board visual customization."""

    theme_selected    = Signal(str)
    piece_set_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Dialog)
        self.setWindowTitle("Customize Board")
        self.setModal(True)
        self.setFixedWidth(400)

        self._apply_style()
        self._build_ui()

    # ─────────────────────────────────────────────────────────────────────
    def _apply_style(self) -> None:
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS.bg_panel};
                border: 1px solid {COLORS.border};
                border-radius: 10px;
            }}
            QLabel[role="title"] {{
                color: {COLORS.text};
                font-size: {FONTS.lg}pt;
                font-weight: 600;
            }}
            QLabel[role="section"] {{
                color: {COLORS.text_dim};
                font-size: {FONTS.xs}pt;
                font-weight: 600;
                letter-spacing: 0.8px;
                text-transform: uppercase;
            }}
            QLabel[role="set-label"] {{
                color: {COLORS.text_dim};
                font-size: {FONTS.xs}pt;
                text-align: center;
            }}
            QPushButton#CloseBtn {{
                background-color: {COLORS.accent};
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 8px 24px;
                font-size: {FONTS.sm}pt;
                font-weight: 600;
            }}
            QPushButton#CloseBtn:hover {{
                background-color: {COLORS.accent_hover};
            }}
            QFrame[role="divider"] {{
                background-color: {COLORS.border};
                max-height: 1px;
                min-height: 1px;
            }}
        """)

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text.upper())
        lbl.setProperty("role", "section")
        lbl.style().unpolish(lbl)
        lbl.style().polish(lbl)
        return lbl

    def _divider(self) -> QFrame:
        d = QFrame()
        d.setProperty("role", "divider")
        return d

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(SPACE.xl, SPACE.xl, SPACE.xl, SPACE.xl)
        root.setSpacing(SPACE.lg)

        # ── Title row ─────────────────────────────────────────────────────
        title_row = QHBoxLayout()
        title = QLabel("Board Customization")
        title.setProperty("role", "title")
        title.style().unpolish(title); title.style().polish(title)
        title_row.addWidget(title)
        title_row.addStretch(1)
        root.addLayout(title_row)

        root.addWidget(self._divider())

        # ── Piece Set ─────────────────────────────────────────────────────
        root.addWidget(self._section_label("Piece Set"))

        self.piece_picker = PieceSetPicker()
        self.piece_picker.set_selected.connect(self.piece_set_selected)
        root.addWidget(self.piece_picker)

        # Set-name labels row (one per swatch, centred under each)
        labels_row = QHBoxLayout()
        labels_row.setContentsMargins(0, 0, 0, 0)
        labels_row.setSpacing(8)
        from app.ui.piece_sets import PIECE_SETS
        for name in PIECE_SETS:
            lbl = QLabel(name)
            lbl.setProperty("role", "set-label")
            lbl.setFixedWidth(56)
            lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            lbl.setStyleSheet(f"color: {COLORS.text_dim}; font-size: {FONTS.xs}pt;")
            labels_row.addWidget(lbl)
        labels_row.addStretch(1)
        root.addLayout(labels_row)

        root.addWidget(self._divider())

        # ── Board Theme ────────────────────────────────────────────────────
        root.addWidget(self._section_label("Board Theme"))

        self.theme_picker = BoardThemePicker()
        self.theme_picker.theme_selected.connect(self.theme_selected)
        root.addWidget(self.theme_picker)

        root.addStretch(1)

        # ── Close button ──────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        close_btn = QPushButton("Done")
        close_btn.setObjectName("CloseBtn")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        root.addLayout(btn_row)

    # ─────────────────────────────────────────────────────────────────────
    def set_active_theme(self, name: str) -> None:
        self.theme_picker.set_active_theme(name)

    def set_active_piece_set(self, name: str) -> None:
        self.piece_picker.set_active_set(name)
