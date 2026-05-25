"""
PGN input widget — paste area + Analyze button + secondary actions.

Emits `analyze_requested(pgn_text)` when the user clicks Analyze.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QTextEdit,
    QVBoxLayout, QWidget,
)

from app.ui.theme import COLORS, FONTS, SPACE


# Bundled sample game so first-time users have something to try
SAMPLE_PGN = """[Event "London"]
[Site "London ENG"]
[Date "1851.06.21"]
[White "Adolf Anderssen"]
[Black "Lionel Kieseritzky"]
[Result "1-0"]

1.e4 e5 2.f4 exf4 3.Bc4 Qh4+ 4.Kf1 b5 5.Bxb5 Nf6 6.Nf3 Qh6 7.d3 Nh5
8.Nh4 Qg5 9.Nf5 c6 10.g4 Nf6 11.Rg1 cxb5 12.h4 Qg6 13.h5 Qg5 14.Qf3 Ng8
15.Bxf4 Qf6 16.Nc3 Bc5 17.Nd5 Qxb2 18.Bd6 Bxg1 19.e5 Qxa1+ 20.Ke2 Na6
21.Nxg7+ Kd8 22.Qf6+ Nxf6 23.Be7# 1-0"""


PLACEHOLDER = "Paste a PGN here…\n\nFrom chess.com: Archive → game → ⋮ → Download PGN\nFrom Lichess: game page → Share → Copy PGN"


class PgnInput(QFrame):
    analyze_requested = Signal(str)   # emits the PGN text
    cancel_requested  = Signal()      # user clicked Cancel during analysis
    cleared           = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {COLORS.bg_panel};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE.sm)

        # Text area
        self._editor = QTextEdit()
        self._editor.setPlaceholderText(PLACEHOLDER)
        self._editor.setMinimumHeight(110)
        self._editor.setStyleSheet(
            f"QTextEdit {{"
            f"  background-color: {COLORS.bg_input};"
            f"  color: {COLORS.text};"
            f"  border: 1px solid {COLORS.border_subtle};"
            f"  border-radius: 6px;"
            f"  padding: 8px 10px;"
            f"  font-family: 'Cascadia Code','Consolas',monospace;"
            f"  font-size: {FONTS.sm}pt;"
            f"  selection-background-color: {COLORS.accent};"
            f"  selection-color: {COLORS.on_accent};"
            f"}}"
            f"QTextEdit:focus {{ border-color: {COLORS.border_focus}; }}"
        )
        layout.addWidget(self._editor)

        # Primary action — full-width
        # NOTE: setProperty("variant", "primary") wasn't being picked up
        # consistently by QSS — using explicit stylesheet to guarantee styling.
        self._analyze_btn = QPushButton("Analyze Game")
        self._analyze_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._analyze_btn.setMinimumHeight(38)
        self._analyze_btn.setStyleSheet(
            f"QPushButton {{"
            f"  background-color: {COLORS.accent};"
            f"  color: {COLORS.on_accent};"
            f"  border: none;"
            f"  border-radius: 6px;"
            f"  padding: 9px 14px;"
            f"  font-size: {FONTS.md}pt;"
            f"  font-weight: 600;"
            f"}}"
            f"QPushButton:hover {{ background-color: {COLORS.accent_hover}; }}"
            f"QPushButton:pressed {{ background-color: {COLORS.accent_pressed}; }}"
            f"QPushButton:disabled {{"
            f"  background-color: {COLORS.bg_card};"
            f"  color: {COLORS.text_disabled};"
            f"}}"
        )
        self._analyze_btn.clicked.connect(self._emit_analyze)
        layout.addWidget(self._analyze_btn)

        # Secondary row — ghost links in one inline strip
        sec_row = QHBoxLayout()
        sec_row.setContentsMargins(0, 0, 0, 0)
        sec_row.setSpacing(4)

        self._open_btn   = self._link_btn("Open file",     self._open_file)
        self._sample_btn = self._link_btn("Sample",        self._load_sample)
        self._clear_btn  = self._link_btn("Clear",         self._clear)

        for i, b in enumerate([self._open_btn, self._sample_btn, self._clear_btn]):
            sec_row.addWidget(b)
            if i < 2:
                dot = QLabel("·")
                dot.setStyleSheet(f"color: {COLORS.text_dim};")
                sec_row.addWidget(dot)
        sec_row.addStretch(1)
        layout.addLayout(sec_row)

    # ─────────────────────────────────────────────────────────────────────
    def _link_btn(self, label: str, slot) -> QPushButton:
        b = QPushButton(label)
        b.setProperty("variant", "ghost")
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.clicked.connect(slot)
        return b

    # ─────────────────────────────────────────────────────────────────────
    def _emit_analyze(self) -> None:
        text = self._editor.toPlainText().strip()
        if not text:
            return
        self.analyze_requested.emit(text)

    def _load_sample(self) -> None:
        self._editor.setPlainText(SAMPLE_PGN)

    def _open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open PGN", "", "PGN files (*.pgn);;All files (*.*)"
        )
        if not path:
            return
        # Try UTF-8 first (standard), fall back to latin-1 for
        # Windows-1252 encoded files exported by older chess software.
        text = None
        for enc in ("utf-8", "latin-1"):
            try:
                with open(path, "r", encoding=enc) as f:
                    text = f.read()
                break
            except (UnicodeDecodeError, OSError):
                continue
        if text is not None:
            self._editor.setPlainText(text)

    def _clear(self) -> None:
        self._editor.clear()
        self.cleared.emit()

    # ─────────────────────────────────────────────────────────────────────
    def set_enabled_during_analysis(self, enabled: bool) -> None:
        """Toggle between Analyze and Cancel states while analysis runs."""
        self._editor.setReadOnly(not enabled)
        # Rewire the button: during analysis it becomes a Cancel button;
        # after analysis it reverts to the Analyze button.
        try:
            self._analyze_btn.clicked.disconnect()
        except RuntimeError:
            pass
        if not enabled:
            self._analyze_btn.setEnabled(True)
            self._analyze_btn.setText("Cancel Analysis")
            self._analyze_btn.setStyleSheet(
                f"QPushButton {{"
                f"  background-color: {COLORS.bg_card};"
                f"  color: {COLORS.danger};"
                f"  border: 1px solid {COLORS.danger};"
                f"  border-radius: 6px;"
                f"  padding: 9px 14px;"
                f"  font-size: {FONTS.md}pt;"
                f"  font-weight: 600;"
                f"}}"
                f"QPushButton:hover {{ background-color: {COLORS.danger};"
                f"  color: white; }}"
            )
            self._analyze_btn.clicked.connect(self.cancel_requested.emit)
        else:
            self._analyze_btn.setEnabled(True)
            self._analyze_btn.setText("Analyze Game")
            self._analyze_btn.setStyleSheet(
                f"QPushButton {{"
                f"  background-color: {COLORS.accent};"
                f"  color: {COLORS.on_accent};"
                f"  border: none;"
                f"  border-radius: 6px;"
                f"  padding: 9px 14px;"
                f"  font-size: {FONTS.md}pt;"
                f"  font-weight: 600;"
                f"}}"
                f"QPushButton:hover {{ background-color: {COLORS.accent_hover}; }}"
                f"QPushButton:pressed {{ background-color: {COLORS.accent_pressed}; }}"
                f"QPushButton:disabled {{"
                f"  background-color: {COLORS.bg_card};"
                f"  color: {COLORS.text_disabled};"
                f"}}"
            )
            self._analyze_btn.clicked.connect(self._emit_analyze)
