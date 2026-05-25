"""
Coach panel widget — displays per-move coaching cards.

Shows up to 3 cards per position:
  1. Move quality summary (classification + delta)
  2. Position-aware reasoning (from MoveExplainer)
  3. Engine plan (next moves from PV) — optional

Each card fades in with a slight stagger (Framer-Motion-style entry).
"""

from __future__ import annotations
from typing import Optional

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)

from app.config import ICONS_DIR
from app.ui.icon_utils import svg_pixmap
from app.ui.theme import COLORS, FONTS, SPACE, elevation_shadow
from app.ui.animations import fade_in
from app.ui.widgets.move_list import CLS_COLOR, CLS_ICON


def _hex_to_rgba(hex_color: str, alpha: int) -> str:
    """'#rrggbb' → 'rgba(r,g,b,alpha)' for QSS gradients and HTML spans."""
    h = hex_color.lstrip('#')
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


CLS_LABEL = {
    "brilliant":  "Brilliant!",
    "best":       "Best Move",
    "good":       "Good Move",
    "inaccuracy": "Inaccuracy",
    "mistake":    "Mistake",
    "blunder":    "Blunder",
}


# ═════════════════════════════════════════════════════════════════════════════
#  OPENING STRIP — one-line book icon + name + ECO code
# ═════════════════════════════════════════════════════════════════════════════
class OpeningStrip(QFrame):
    """Shows the detected opening name and ECO code above the coaching cards."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            f"OpeningStrip {{ background-color: {COLORS.bg_card};"
            f" border-radius: 6px; }}"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACE.md, SPACE.sm, SPACE.md, SPACE.sm)
        layout.setSpacing(SPACE.sm)

        self._icon_lbl = QLabel()
        self._icon_lbl.setFixedSize(14, 14)
        try:
            px = svg_pixmap(ICONS_DIR / "book.svg", 14, COLORS.text_dim)
            self._icon_lbl.setPixmap(px)
        except Exception:
            self._icon_lbl.setText("📖")
        layout.addWidget(self._icon_lbl, alignment=Qt.AlignmentFlag.AlignVCenter)

        self._name_lbl = QLabel("—")
        self._name_lbl.setStyleSheet(
            f"color: {COLORS.text}; font-size: {FONTS.sm}pt; font-weight: 600;"
            f" background: transparent;"
        )
        layout.addWidget(self._name_lbl, 1)

        self._eco_lbl = QLabel("")
        self._eco_lbl.setStyleSheet(
            f"color: {COLORS.text_dim}; font-size: {FONTS.xs}pt;"
            f" background: transparent;"
        )
        layout.addWidget(self._eco_lbl)

        self.setVisible(False)

    def set_opening(self, eco: str, name: str) -> None:
        self._name_lbl.setText(name)
        self._name_lbl.setStyleSheet(
            f"color: {COLORS.text}; font-size: {FONTS.sm}pt; font-weight: 600;"
            f" background: transparent;"
        )
        self._eco_lbl.setText(eco)
        self.setVisible(True)

    def set_out_of_book(self) -> None:
        self._name_lbl.setText("Out of book")
        self._name_lbl.setStyleSheet(
            f"color: {COLORS.text_dim}; font-size: {FONTS.sm}pt; font-weight: 400;"
            f" background: transparent;"
        )
        self._eco_lbl.setText("")
        self.setVisible(True)

    def clear(self) -> None:
        self.setVisible(False)


# ═════════════════════════════════════════════════════════════════════════════
#  QUICK-ACTION BAR — chess.com-style "Best | Explain | Next" buttons
# ═════════════════════════════════════════════════════════════════════════════
class QuickActionBar(QFrame):
    """Three buttons mirroring chess.com's Game Review:
      Best    → emphasize the engine's alternative on the board
      Explain → read the full "Why" explanation aloud (uses voice service)
      Next    → navigate forward one move
    The bar lives between the COACH header and the coaching cards.
    """
    best_clicked    = Signal()
    explain_clicked = Signal()
    next_clicked    = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE.xs)

        self.btn_best    = self._make_btn("⊕  Best")
        self.btn_explain = self._make_btn("💡  Explain")
        # Next gets the primary-action treatment so it stands out, like
        # chess.com's green Next button.
        self.btn_next    = self._make_btn("Next  ▶", primary=True)

        self.btn_best.clicked.connect(self.best_clicked.emit)
        self.btn_explain.clicked.connect(self.explain_clicked.emit)
        self.btn_next.clicked.connect(self.next_clicked.emit)

        for b in (self.btn_best, self.btn_explain, self.btn_next):
            layout.addWidget(b, 1)

    def _make_btn(self, text: str, primary: bool = False) -> QPushButton:
        b = QPushButton(text)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setFixedHeight(32)
        if primary:
            b.setStyleSheet(
                f"QPushButton {{"
                f"  background-color: {COLORS.accent};"
                f"  color: {COLORS.on_accent};"
                f"  border: 1px solid {COLORS.accent};"
                f"  border-radius: 6px;"
                f"  font-size: {FONTS.sm}pt; font-weight: 700;"
                f"}}"
                f"QPushButton:hover  {{ background-color: {COLORS.accent_hover};"
                f"                       border-color: {COLORS.accent_hover}; }}"
                f"QPushButton:pressed{{ background-color: {COLORS.accent_pressed}; }}"
                f"QPushButton:disabled{{ background-color: {COLORS.bg_card};"
                f"                       color: {COLORS.text_disabled};"
                f"                       border-color: {COLORS.border_subtle}; }}"
            )
        else:
            b.setStyleSheet(
                f"QPushButton {{"
                f"  background-color: {COLORS.bg_card};"
                f"  color: {COLORS.text_muted};"
                f"  border: 1px solid {COLORS.border_subtle};"
                f"  border-radius: 6px;"
                f"  font-size: {FONTS.sm}pt; font-weight: 600;"
                f"}}"
                f"QPushButton:hover  {{ background-color: {COLORS.bg_card_hi};"
                f"                       color: {COLORS.text}; }}"
                f"QPushButton:pressed{{ background-color: {COLORS.bg_input}; }}"
                f"QPushButton:disabled{{ color: {COLORS.text_disabled};"
                f"                       border-color: {COLORS.border_subtle}; }}"
            )
        return b

    def set_enabled_for(self, has_alternative: bool, has_explanation: bool,
                        has_next: bool) -> None:
        """Grey-out buttons that wouldn't do anything for the current move."""
        self.btn_best.setEnabled(has_alternative)
        self.btn_explain.setEnabled(has_explanation)
        self.btn_next.setEnabled(has_next)


class _CoachCard(QFrame):
    """A single coaching card with a colored left accent + title + body.

    `title_badge` (optional) renders a small pill on the right side of the
    title row — used to show the eval delta (e.g. "−0.8") next to a
    mistake/blunder label, chess.com-style.
    `body_rich` (optional) overrides `body` with HTML — used so we can
    highlight tactical keywords like "fork", "pin", "check".
    """

    def __init__(self, title: str, body: str, accent: str,
                 parent: QWidget | None = None,
                 title_badge: str | None = None,
                 badge_color: str | None = None,
                 body_rich: str | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            f"_CoachCard {{ background-color: {COLORS.bg_card}; "
            f"border-radius: 6px; }}"
        )

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Left accent stripe — gradient top:full → bottom:~40% opacity
        stripe = QFrame()
        stripe.setFixedWidth(3)
        bot = _hex_to_rgba(accent, 100)
        stripe.setStyleSheet(
            f"background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            f"stop:0 {accent}, stop:1 {bot}); border-radius: 0;"
        )
        outer.addWidget(stripe)

        # Body
        body_layout = QVBoxLayout()
        body_layout.setContentsMargins(SPACE.lg, SPACE.lg, SPACE.lg, SPACE.lg)
        body_layout.setSpacing(4)

        # Title row: label on left, optional delta badge on right
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(SPACE.sm)
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            f"color: {accent}; font-size: {FONTS.xs}pt; font-weight: 700;"
            f"letter-spacing: 0.5px; background-color: transparent;"
        )
        title_row.addWidget(title_lbl)
        title_row.addStretch(1)
        if title_badge:
            bcol = badge_color or accent
            badge = QLabel(title_badge)
            badge.setStyleSheet(
                f"color: white; background-color: {bcol};"
                f"font-size: {FONTS.xs}pt; font-weight: 700;"
                f"padding: 2px 7px; border-radius: 8px;"
            )
            title_row.addWidget(badge)
        body_layout.addLayout(title_row)

        body_lbl = QLabel(body_rich if body_rich else body)
        body_lbl.setWordWrap(True)
        if body_rich:
            body_lbl.setTextFormat(Qt.TextFormat.RichText)
        body_lbl.setStyleSheet(
            f"color: {COLORS.text_muted}; font-size: {FONTS.sm}pt;"
            f"background-color: transparent;"
        )
        body_layout.addWidget(body_lbl)

        wrap = QWidget()
        wrap.setStyleSheet("background-color: transparent;")
        wrap.setLayout(body_layout)
        outer.addWidget(wrap, 1)


# ═════════════════════════════════════════════════════════════════════════════
#  COACH PANEL
# ═════════════════════════════════════════════════════════════════════════════
class CoachPanel(QScrollArea):
    """Container that swaps card stacks when the user navigates moves."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._inner = QWidget()
        self._inner.setStyleSheet(f"background-color: {COLORS.bg_panel};")
        self._layout = QVBoxLayout(self._inner)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(SPACE.md)
        self._layout.addStretch(1)
        self.setWidget(self._inner)

        self._pending_timers: list[QTimer] = []
        self._show_placeholder()

    # ─────────────────────────────────────────────────────────────────────
    def _clear(self) -> None:
        for t in self._pending_timers:
            try:
                t.stop()
            except RuntimeError:
                pass
        self._pending_timers.clear()
        while self._layout.count() > 1:
            item = self._layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

    def _add_card(self, title: str, body: str, accent: str,
                  delay_ms: int = 0,
                  title_badge: str | None = None,
                  badge_color: str | None = None,
                  body_rich: str | None = None) -> None:
        card = _CoachCard(title, body, accent,
                          title_badge=title_badge, badge_color=badge_color,
                          body_rich=body_rich)
        self._layout.insertWidget(self._layout.count() - 1, card)

        # Fade-in entrance, deferred so the widget is fully parented first.
        # After the opacity animation completes, swap to the elevation shadow
        # (Qt only allows one QGraphicsEffect per widget at a time).
        effect = QGraphicsOpacityEffect(card)
        effect.setOpacity(0.0)
        card.setGraphicsEffect(effect)

        def _start_anim(card=card, effect=effect):
            anim = QPropertyAnimation(effect, b"opacity", card)
            anim.setDuration(200)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)

            def _on_done(card=card):
                try:
                    card.setGraphicsEffect(elevation_shadow(1, card))
                except RuntimeError:
                    pass

            anim.finished.connect(_on_done)
            anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

        t = QTimer(self)
        t.setSingleShot(True)
        t.timeout.connect(_start_anim)
        t.start(delay_ms)
        self._pending_timers.append(t)

    # ─────────────────────────────────────────────────────────────────────
    def _show_placeholder(self) -> None:
        self._clear()
        lbl = QLabel("Analyze a game and navigate through it\nto see coaching here.")
        lbl.setStyleSheet(
            f"color: {COLORS.text_dim}; font-size: {FONTS.sm}pt;"
        )
        lbl.setAlignment(Qt.AlignmentFlag.AlignTop)
        lbl.setWordWrap(True)
        self._layout.insertWidget(self._layout.count() - 1, lbl)

    # ─────────────────────────────────────────────────────────────────────
    # ── Tactical keyword highlighting ──────────────────────────────────────────
    # Words that name a tactical pattern get wrapped in a colored pill,
    # chess.com-style. Matched case-insensitively, longest-first so e.g.
    # "discovered attack" beats "attack".
    _TACTIC_WORDS = [
        ("checkmate",         COLORS.cls_blunder),
        ("discovered attack", COLORS.warning),
        ("discovered check",  COLORS.warning),
        ("double attack",     COLORS.warning),
        ("skewer",            COLORS.warning),
        ("fork",              COLORS.cls_best),
        ("pin",               COLORS.cls_best),
        ("check",             COLORS.cls_inaccuracy),
        ("hanging",           COLORS.cls_mistake),
        ("undefended",        COLORS.cls_mistake),
        ("sacrifice",         COLORS.cls_brilliant),
    ]

    @classmethod
    def _highlight_tactics(cls, text: str) -> str | None:
        """Wrap tactical keywords in colored pills. Returns rich-HTML
        if anything matched, else None (caller should fall back to plain)."""
        if not text:
            return None
        import html, re
        out = html.escape(text)
        matched = False
        for word, color in cls._TACTIC_WORDS:
            pattern = re.compile(rf"\b({re.escape(word)})\b", re.IGNORECASE)
            def repl(m, c=color):
                bg = _hex_to_rgba(c, 38)  # ~15% opacity background pill
                return (f'<span style="color:{c}; font-weight:600;'
                        f' background-color:{bg};">'
                        f'{m.group(1)}</span>')
            new = pattern.sub(repl, out)
            if new != out:
                matched = True
                out = new
        return out if matched else None

    # ─────────────────────────────────────────────────────────────────────
    def show_for_move(self, analyzed_move, move_san_with_num: str) -> None:
        """analyzed_move: AnalyzedMove from core.analyzer."""
        self._clear()
        cls = analyzed_move.classification
        accent = CLS_COLOR.get(cls, COLORS.text_dim)
        label = CLS_LABEL.get(cls, "Move")
        d_abs = abs(analyzed_move.delta)
        explanation = analyzed_move.explanation or {}

        # Card 1 — quality summary with eval delta badge (chess.com style)
        delta = analyzed_move.delta
        is_game_end = isinstance(explanation, dict) and explanation.get("game_end")
        # Suppress the badge on game-end moves: "+9999" is meaningless for
        # checkmate and confusing for resignation/draw.
        badge_text = None
        badge_color = None
        if not is_game_end:
            if cls in ("inaccuracy", "mistake", "blunder") and d_abs >= 0.2:
                badge_text = f"−{d_abs:.1f}"   # unicode minus, cleaner than "-"
                badge_color = accent
            elif cls in ("brilliant",) and delta >= 0.2:
                badge_text = f"+{abs(delta):.1f}"
                badge_color = accent

        if cls == "blunder":
            summary = (f"{analyzed_move.san} was a blunder — a critical "
                       f"error that gave away significant ground.")
        elif cls == "mistake":
            summary = (f"{analyzed_move.san} was a mistake — there was a "
                       f"clearly better move available.")
        elif cls == "inaccuracy":
            summary = (f"{analyzed_move.san} was an inaccuracy — slightly "
                       f"off the best line.")
        elif cls == "brilliant":
            summary = (f"{analyzed_move.san} is the engine's top choice — "
                       f"and a great find in this position.")
        elif cls == "best":
            # Distinguish forced moves from chosen-best in the summary
            exp = analyzed_move.explanation or {}
            reasons = exp.get("reasons", []) if isinstance(exp, dict) else []
            if any("forced" in r for r in reasons):
                summary = (f"{analyzed_move.san} was the only legal move — "
                           f"a forced response.")
            else:
                summary = (f"{analyzed_move.san} matches the engine's top "
                           f"choice.")
        else:
            # 'good' — solid but not the top pick
            if analyzed_move.best_move:
                summary = (f"{analyzed_move.san} is solid. The engine "
                           f"slightly preferred a different move.")
            else:
                summary = f"{analyzed_move.san} is solid."
        self._add_card(f"{CLS_ICON.get(cls, '·')}  {label}", summary, accent,
                       delay_ms=0,
                       title_badge=badge_text, badge_color=badge_color)

        # Card 2 — position-aware reasoning, with tactical keywords highlighted
        card_text = explanation.get("card", "") if isinstance(explanation, dict) else ""
        if card_text:
            rich = self._highlight_tactics(card_text)
            self._add_card("Why", card_text, COLORS.info, delay_ms=80,
                           body_rich=rich)

        # Card 3 — engine continuation (PV) — skip for game-end positions
        if not is_game_end and analyzed_move.best_pv and len(analyzed_move.best_pv) >= 2:
            pv_str = self._format_pv(analyzed_move.best_pv[:4])
            if pv_str:
                self._add_card("Engine continuation", pv_str,
                               COLORS.text_dim, delay_ms=160)

    # ─────────────────────────────────────────────────────────────────────
    @staticmethod
    def _format_pv(pv) -> str:
        """Format moves as 'e4 e5 Nf3' — UCI to readable."""
        parts = []
        for m in pv:
            u = m.uci()
            parts.append(f"{u[:2]}–{u[2:4]}")
        return "  ›  ".join(parts)
