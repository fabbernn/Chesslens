"""
Move list widget — chess.com-style two-column display with classification icons.

Built on QListWidget with a custom item delegate for full styling control
without dropping all the way down to QAbstractItemModel.
"""

from __future__ import annotations
from typing import Optional

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Property, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QScrollArea, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QWidget,
)

from app.ui.theme import COLORS, FONTS, SPACE


# Classification → standard chess annotation glyph + color.
# Uses the conventional notation: !! brilliant, ! good, ? mistake, ?! inaccuracy,
# ?? blunder. Brilliant/best/good get blue tones; mistakes/blunders escalate
# to red.
CLS_ICON = {
    "brilliant":  "!!",
    "best":       "★",      # star — distinguishes from "good" while staying positive
    "good":       "!",
    "inaccuracy": "?!",     # dubious move
    "mistake":    "?",      # mistake
    "blunder":    "??",     # blunder
}
CLS_COLOR = {
    "brilliant":  COLORS.cls_brilliant,
    "best":       COLORS.cls_best,
    "good":       COLORS.cls_good,
    "inaccuracy": COLORS.cls_inaccuracy,
    "mistake":    COLORS.cls_mistake,
    "blunder":    COLORS.cls_blunder,
}

# Alternating row background colors
_ROW_BG_EVEN = "#1e1d1b"
_ROW_BG_ODD  = "#1a1918"

# Piece symbols inline in move text (chess.com style)
PIECE_SYM_WHITE = {"N":"♘","B":"♗","R":"♖","Q":"♕","K":"♔"}
PIECE_SYM_BLACK = {"N":"♞","B":"♝","R":"♜","Q":"♛","K":"♚"}


def _format_time(seconds: Optional[float]) -> str:
    if seconds is None:  return ""
    if seconds < 60:     return f"{seconds:.1f}s"
    m, s = int(seconds // 60), int(seconds % 60)
    return f"{m}m{s:02d}s"


def _format_san_with_piece(san: str, is_white: bool) -> str:
    """Prepend a unicode piece glyph for non-pawn moves."""
    if not san or not san[0].isupper():
        return san
    syms = PIECE_SYM_WHITE if is_white else PIECE_SYM_BLACK
    sym = syms.get(san[0])
    return f"{sym}{san}" if sym else san


# ═════════════════════════════════════════════════════════════════════════════
#  ROW WIDGET — one move-pair row
# ═════════════════════════════════════════════════════════════════════════════
class _MoveCell(QFrame):
    """One half of a move pair. Clickable, smoothly hover-animated, classification-styled."""

    clicked = Signal(int)

    def __init__(self, move_index: int, san: str, classification: str,
                 time_seconds: Optional[float], is_white: bool,
                 row_bg: str = _ROW_BG_ODD,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.move_index = move_index
        self._active = False
        self._t = 0.0           # hover progress: 0.0 = idle, 1.0 = hovered
        self._row_bg = row_bg   # base background for this cell's row
        self._anim: QPropertyAnimation | None = None
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(34)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 8, 0)
        layout.setSpacing(6)

        # Active accent stripe — always occupies 3px; transparent when not active
        self._stripe = QFrame()
        self._stripe.setFixedWidth(3)
        layout.addWidget(self._stripe)

        # Classification icon with 15%-opacity pill background
        cls_color = CLS_COLOR.get(classification, COLORS.text_dim)
        h = cls_color.lstrip('#')
        r_, g_, b_ = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        icon = QLabel(CLS_ICON.get(classification, "·"))
        icon.setStyleSheet(
            f"color: {cls_color}; font-size: {FONTS.xs}pt; font-weight: 700;"
            f"background-color: rgba({r_},{g_},{b_},40); border-radius: 3px; padding: 0 2px;"
        )
        icon.setFixedWidth(22)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon)

        # Move text
        self._san_label = QLabel(_format_san_with_piece(san, is_white))
        layout.addWidget(self._san_label)
        layout.addStretch(1)

        # Clock time
        time_str = _format_time(time_seconds)
        if time_str:
            lbl = QLabel(time_str)
            lbl.setStyleSheet(f"color: {COLORS.text_dim}; font-size: {FONTS.xs}pt;")
            layout.addWidget(lbl)

        self._refresh_bg()

    # ── Qt property for QPropertyAnimation-driven hover ───────────────────────
    def _get_t(self) -> float: return self._t
    def _set_t(self, v: float) -> None:
        self._t = v
        self._refresh_bg()
    _hover_t = Property(float, _get_t, _set_t)

    # ─────────────────────────────────────────────────────────────────────
    def set_active(self, active: bool) -> None:
        self._active = active
        if active:
            self._t = 0.0   # clear hover state when activating
        self._refresh_bg()

    def _refresh_bg(self) -> None:
        if self._active:
            self._stripe.setStyleSheet(f"background-color: {COLORS.accent};")
            self.setStyleSheet("_MoveCell { background-color: #2a3d2a; }")
            self._san_label.setStyleSheet(
                f"color: {COLORS.text}; font-size: {FONTS.md}pt;"
                f"font-weight: 600; background-color: transparent;"
            )
        else:
            # Hover: animate from row bg toward #242220
            a = QColor(self._row_bg)
            b = QColor("#242220")
            rv = int(a.red()   + self._t * (b.red()   - a.red()))
            gv = int(a.green() + self._t * (b.green() - a.green()))
            bv = int(a.blue()  + self._t * (b.blue()  - a.blue()))
            self._stripe.setStyleSheet("background-color: transparent;")
            self.setStyleSheet(f"_MoveCell {{ background-color: #{rv:02x}{gv:02x}{bv:02x}; }}")
            self._san_label.setStyleSheet(
                f"color: {COLORS.text}; font-size: {FONTS.md}pt;"
                f"font-weight: 400; background-color: transparent;"
            )

    def _animate_to(self, target: float) -> None:
        if self._anim is not None:
            try: self._anim.stop()
            except RuntimeError: pass
            self._anim = None
        anim = QPropertyAnimation(self, b"_hover_t", self)
        anim.setDuration(120)
        anim.setStartValue(self._t)
        anim.setEndValue(target)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.finished.connect(lambda: setattr(self, "_anim", None))
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
        self._anim = anim

    def enterEvent(self, event) -> None:
        if not self._active:
            self._animate_to(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        if not self._active:
            self._animate_to(0.0)
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.move_index)
        super().mousePressEvent(event)


class _MovePairRow(QFrame):
    """One row containing a move number + (white move, black move)."""

    cell_clicked = Signal(int)

    def __init__(self, move_number: int, white_cell: QWidget,
                 black_cell: Optional[QWidget],
                 row_bg: str = _ROW_BG_ODD,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        num = QLabel(f"{move_number}")
        num.setStyleSheet(
            f"color: {COLORS.text_dim}; font-size: {FONTS.xs}pt; "
            f"background-color: {row_bg};"
        )
        num.setFixedWidth(34)
        num.setAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(num)

        layout.addWidget(white_cell, 1)

        sep = QFrame()
        sep.setFixedWidth(1)
        sep.setStyleSheet(f"background-color: {COLORS.border_subtle};")
        layout.addWidget(sep)

        if black_cell is not None:
            layout.addWidget(black_cell, 1)
        else:
            spacer = QFrame()
            spacer.setStyleSheet(f"background-color: {row_bg};")
            layout.addWidget(spacer, 1)

        # Connect cell clicks
        if hasattr(white_cell, "clicked"):
            white_cell.clicked.connect(self.cell_clicked)
        if black_cell is not None and hasattr(black_cell, "clicked"):
            black_cell.clicked.connect(self.cell_clicked)


# ═════════════════════════════════════════════════════════════════════════════
#  MOVE LIST WIDGET
# ═════════════════════════════════════════════════════════════════════════════
class MoveList(QScrollArea):
    """Vertical scrollable list of move pairs."""

    move_selected = Signal(int)   # 0-based move index

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._inner = QWidget()
        self._inner.setStyleSheet(f"background-color: {COLORS.bg_panel};")
        self._layout = QVBoxLayout(self._inner)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(1)
        self._layout.addStretch(1)
        self.setWidget(self._inner)

        self._cells: list[_MoveCell] = []     # indexed by move index
        self._active_idx: int = -1

    # ─────────────────────────────────────────────────────────────────────
    def set_moves(self, analyzed) -> None:
        """Replace contents with analyzed moves. `analyzed` is list[AnalyzedMove]."""
        self._clear()

        row_idx = 0
        i = 0
        while i < len(analyzed):
            white = analyzed[i]
            black = analyzed[i + 1] if (i + 1) < len(analyzed) else None
            row_bg = _ROW_BG_EVEN if row_idx % 2 == 0 else _ROW_BG_ODD

            white_cell = _MoveCell(
                move_index=white.index,
                san=white.san,
                classification=white.classification,
                time_seconds=white.time_taken,
                is_white=True,
                row_bg=row_bg,
            )
            white_cell.clicked.connect(self.move_selected)
            self._cells.append(white_cell)

            black_cell = None
            if black is not None:
                black_cell = _MoveCell(
                    move_index=black.index,
                    san=black.san,
                    classification=black.classification,
                    time_seconds=black.time_taken,
                    is_white=False,
                    row_bg=row_bg,
                )
                black_cell.clicked.connect(self.move_selected)
                self._cells.append(black_cell)

            row = _MovePairRow(white.move_number, white_cell, black_cell, row_bg)
            # Insert before the stretch at the end
            self._layout.insertWidget(self._layout.count() - 1, row)

            i += 2
            row_idx += 1

    def _clear(self) -> None:
        # Remove every widget except the final stretch
        while self._layout.count() > 1:
            item = self._layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        self._cells.clear()
        self._active_idx = -1

    # ─────────────────────────────────────────────────────────────────────
    def set_active_move(self, idx: int) -> None:
        """Highlight the given move index, scroll to it."""
        if 0 <= self._active_idx < len(self._cells):
            self._cells[self._active_idx].set_active(False)
        self._active_idx = idx
        if 0 <= idx < len(self._cells):
            cell = self._cells[idx]
            cell.set_active(True)
            self.ensureWidgetVisible(cell)
