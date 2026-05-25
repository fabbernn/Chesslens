"""
Theme — centralized design tokens (colors, typography, spacing) + QSS templates.

This is the SINGLE SOURCE OF TRUTH for the application's visual design.
No widget should hardcode colors. Always import from here.

Inspired by Chess.com's dark palette but adapted for desktop density.
"""

from __future__ import annotations
from dataclasses import dataclass

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsDropShadowEffect


# ─────────────────────────────────────────────────────────────────────────────
#  COLOR SYSTEM
#  Warm dark grays (never pure black) — chess.com aesthetic.
#  Elevation hierarchy (darkest → lightest):
#    bg_input < bg_app < bg_panel < bg_card < bg_card_hi
# ─────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Palette:
    # Backgrounds — layered depth (each level clearly distinct from neighbors)
    bg_app:     str = "#131211"  # outermost frame (the title bar shoulder)
    bg_panel:   str = "#1c1b18"  # left/right panel surface
    bg_card:    str = "#272523"  # raised card surface — clearly lighter than panel
    bg_card_hi: str = "#302e2a"  # hover/focus card surface
    bg_input:   str = "#0f0e0d"  # text inputs / recessed surfaces (below bg_app)

    # Lines — sparse use; depth should come from tonal shifts, not borders
    border:        str = "#2a2824"
    border_subtle: str = "#1e1d1a"
    border_focus:  str = "#81b64c"

    # Text
    text:        str = "#ece8e0"  # primary
    text_muted:  str = "#a09a90"  # secondary
    text_dim:    str = "#65605a"  # tertiary
    text_disabled: str = "#3f3d39"

    # Accents — chess.com greens
    accent:        str = "#81b64c"  # primary green
    accent_hover:  str = "#a3d068"
    accent_pressed:str = "#6d9d3f"
    accent_dim:    str = "#5a7c34"
    on_accent:     str = "#0f1808"  # text/icon on accent-green surfaces

    # Semantic
    success:    str = "#81b64c"
    warning:    str = "#d4ac22"
    danger:     str = "#ca3431"
    info:       str = "#5d9bd5"

    # Move classification (chess.com style)
    cls_brilliant:  str = "#1baca6"  # teal
    cls_best:       str = "#6cb040"  # green
    cls_good:       str = "#81b64c"  # light green
    cls_inaccuracy: str = "#f0c040"  # yellow
    cls_mistake:    str = "#e68a30"  # orange
    cls_blunder:    str = "#cc2020"  # red

    # Board
    board_dark:  str = "#769656"
    board_light: str = "#eeeed2"
    board_from:  str = "#f6f669"   # last-move from-square
    board_to:    str = "#cdd16e"   # last-move to-square (neutral / good)
    # Per-classification destination square tints
    board_brilliant_to:  str = "#1baca6"
    board_best_to:       str = "#6cb040"
    board_good_to:       str = "#a3c870"
    board_inaccuracy_to: str = "#e8c840"
    board_mistake_to:    str = "#e89050"
    board_blunder_to:    str = "#cc3030"
    arrow_best:  str = "#15781b"   # engine best move arrow
    arrow_user:  str = "#f6a623"   # user-drawn arrow / circle

    # Eval bar — high-contrast fills so the bar is visible against dark UI
    eval_bar_dark:  str = "#0a0908"  # black-winning fill (near-black, clearly darker than bg)
    eval_bar_light: str = "#f0ece8"  # white-winning fill (near-white, clearly lighter)
    eval_bar_line:  str = "#555250"  # midline at zero

    # Eval graph
    graph_white: str = "#bdb89d"  # white-side background of the graph

    # Overlays
    bg_overlay: str = "rgba(18, 17, 14, 220)"  # subtitle pill / HUD background


@dataclass(frozen=True)
class Typography:
    # Font stack — Windows-first; degrades gracefully
    family_ui:   str = "Segoe UI Variable, Segoe UI, Inter, system-ui, sans-serif"
    family_mono: str = "Cascadia Code, Consolas, SF Mono, Menlo, monospace"

    # Type scale — refined for better hierarchy (was 10/11/12/14/18/28)
    xs:  int = 11   # captions, labels
    sm:  int = 12   # secondary text
    md:  int = 13   # body
    lg:  int = 15   # emphasized body
    xl:  int = 20   # section headers
    xxl: int = 32   # main title


@dataclass(frozen=True)
class Spacing:
    """8px base grid. Use these constants instead of ad-hoc padding."""
    xs:  int = 4
    sm:  int = 8
    md:  int = 12
    lg:  int = 16
    xl:  int = 24
    xxl: int = 32


@dataclass(frozen=True)
class Radius:
    sm:   int = 4
    md:   int = 6
    lg:   int = 10
    xl:   int = 14   # large modals / dialog containers
    pill: int = 999


# Singleton instances — import these everywhere
COLORS  = Palette()
FONTS   = Typography()
SPACE   = Spacing()
RADIUS  = Radius()


# ─────────────────────────────────────────────────────────────────────────────
#  ELEVATION SHADOWS
#  Three levels: ambient (cards), raised (panels), floating (modals).
# ─────────────────────────────────────────────────────────────────────────────
def elevation_shadow(level: int, parent=None) -> QGraphicsDropShadowEffect:
    """Return a drop-shadow effect for the given elevation level.

    level 1 — ambient  : coach cards, subtle depth (4-6px blur)
    level 2 — raised   : top bar, panel headers (12-16px blur)
    level 3 — floating : modals, dialogs (20-28px blur)
    """
    shadow = QGraphicsDropShadowEffect(parent)
    if level == 1:
        shadow.setBlurRadius(6)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(0, 0, 0, 90))
    elif level == 2:
        shadow.setBlurRadius(16)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 130))
    else:
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 170))
    return shadow


# ─────────────────────────────────────────────────────────────────────────────
#  QSS — Qt Stylesheets
#  Composed from the tokens above so colors update everywhere from one place.
# ─────────────────────────────────────────────────────────────────────────────
def build_global_qss() -> str:
    c = COLORS
    f = FONTS
    s = SPACE
    r = RADIUS

    return f"""
    /* ─────────────────────────────────────────────────────────────────────
       GLOBAL — applies to every QWidget
       ───────────────────────────────────────────────────────────────────── */
    QWidget {{
        background-color: {c.bg_panel};
        color: {c.text};
        font-family: "{f.family_ui.split(',')[0].strip()}";
        font-size: {f.md}pt;
        selection-background-color: {c.accent};
        selection-color: {c.on_accent};
    }}

    QMainWindow {{
        background-color: {c.bg_app};
    }}

    /* ─────────────────────────────────────────────────────────────────────
       BUTTONS — premium feel: rounded, subtle hover, pressed feedback
       ───────────────────────────────────────────────────────────────────── */
    QPushButton {{
        background-color: {c.bg_card};
        color: {c.text_muted};
        border: 1px solid {c.border_subtle};
        border-radius: {r.md}px;
        padding: 8px 14px;
        font-size: {f.md}pt;
    }}
    QPushButton:hover {{
        background-color: {c.bg_card_hi};
        color: {c.text};
        border-color: {c.border};
    }}
    QPushButton:pressed {{
        background-color: {c.bg_input};
    }}
    QPushButton:disabled {{
        color: {c.text_disabled};
        background-color: {c.bg_panel};
        border-color: {c.border_subtle};
    }}

    /* Primary action button — class="primary" */
    QPushButton[variant="primary"] {{
        background-color: {c.accent};
        color: {c.on_accent};
        border: 1px solid {c.accent};
        font-weight: 600;
    }}
    QPushButton[variant="primary"]:hover {{
        background-color: {c.accent_hover};
        border-color: {c.accent_hover};
    }}
    QPushButton[variant="primary"]:pressed {{
        background-color: {c.accent_pressed};
    }}

    /* Subtle "ghost" button — class="ghost" */
    QPushButton[variant="ghost"] {{
        background-color: transparent;
        color: {c.text_muted};
        border: none;
        padding: 4px 8px;
    }}
    QPushButton[variant="ghost"]:hover {{
        color: {c.accent};
        background-color: transparent;
    }}

    /* ─────────────────────────────────────────────────────────────────────
       LABELS
       ───────────────────────────────────────────────────────────────────── */
    QLabel {{
        background-color: transparent;
        color: {c.text};
    }}
    QLabel[role="title"] {{
        font-size: {f.xl}pt;
        font-weight: 600;
        color: {c.text};
    }}
    QLabel[role="section"] {{
        font-size: {f.sm}pt;
        font-weight: 600;
        color: {c.text_dim};
        text-transform: uppercase;
        letter-spacing: 1px;
    }}
    QLabel[role="muted"] {{
        color: {c.text_muted};
    }}
    QLabel[role="dim"] {{
        color: {c.text_dim};
    }}

    /* ─────────────────────────────────────────────────────────────────────
       TEXT INPUTS
       ───────────────────────────────────────────────────────────────────── */
    QTextEdit, QPlainTextEdit, QLineEdit {{
        background-color: {c.bg_input};
        color: {c.text};
        border: 1px solid {c.border_subtle};
        border-radius: {r.md}px;
        padding: {s.sm}px {s.md}px;
        selection-background-color: {c.accent};
        selection-color: {c.on_accent};
    }}
    QTextEdit:focus, QPlainTextEdit:focus, QLineEdit:focus {{
        border-color: {c.border_focus};
    }}

    /* ─────────────────────────────────────────────────────────────────────
       SCROLLBARS — minimal modern style
       ───────────────────────────────────────────────────────────────────── */
    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {c.border};
        border-radius: 4px;
        min-height: 24px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {c.text_dim};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: transparent;
    }}

    QScrollBar:horizontal {{
        background: transparent;
        height: 8px;
        margin: 0;
    }}
    QScrollBar::handle:horizontal {{
        background: {c.border};
        border-radius: 4px;
        min-width: 24px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: {c.text_dim};
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0;
    }}
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
        background: transparent;
    }}

    /* ─────────────────────────────────────────────────────────────────────
       FRAMES — depth via subtle border-bottom
       ───────────────────────────────────────────────────────────────────── */
    QFrame[role="divider"] {{
        background-color: {c.border_subtle};
        max-height: 1px;
        min-height: 1px;
    }}

    QFrame[role="card"] {{
        background-color: {c.bg_card};
        border: 1px solid {c.border_subtle};
        border-radius: {r.lg}px;
    }}

    /* ─────────────────────────────────────────────────────────────────────
       SLIDERS — thin modern
       ───────────────────────────────────────────────────────────────────── */
    QSlider::groove:horizontal {{
        height: 4px;
        background: {c.bg_card};
        border-radius: 2px;
    }}
    QSlider::handle:horizontal {{
        background: {c.accent};
        width: 14px;
        height: 14px;
        margin: -5px 0;
        border-radius: 7px;
    }}
    QSlider::handle:horizontal:hover {{
        background: {c.accent_hover};
    }}
    QSlider::sub-page:horizontal {{
        background: {c.accent};
        border-radius: 2px;
    }}

    /* ─────────────────────────────────────────────────────────────────────
       COMBOBOX
       ───────────────────────────────────────────────────────────────────── */
    QComboBox {{
        background-color: {c.bg_card};
        color: {c.text};
        border: 1px solid {c.border_subtle};
        border-radius: {r.md}px;
        padding: 6px 10px;
    }}
    QComboBox:hover {{
        border-color: {c.border};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {c.bg_card};
        color: {c.text};
        border: 1px solid {c.border};
        selection-background-color: {c.accent};
        selection-color: {c.on_accent};
        outline: 0;
    }}

    /* ─────────────────────────────────────────────────────────────────────
       CHECKBOX
       ───────────────────────────────────────────────────────────────────── */
    QCheckBox {{
        background-color: transparent;
        color: {c.text_muted};
        spacing: 6px;
    }}
    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border-radius: 4px;
        background-color: {c.bg_card};
        border: 1px solid {c.border};
    }}
    QCheckBox::indicator:hover {{
        border-color: {c.text_dim};
    }}
    QCheckBox::indicator:checked {{
        background-color: {c.accent};
        border-color: {c.accent};
    }}

    /* ─────────────────────────────────────────────────────────────────────
       TOOLTIP
       ───────────────────────────────────────────────────────────────────── */
    QToolTip {{
        background-color: {c.bg_card};
        color: {c.text};
        border: 1px solid {c.border};
        border-radius: {r.sm}px;
        padding: 4px 8px;
    }}
    """


# Specialty stylesheets (applied to specific containers)

def topbar_qss() -> str:
    c = COLORS
    f = FONTS
    r = RADIUS
    return f"""
        QFrame#TopBar {{
            background-color: {c.bg_app};
            border-bottom: 1px solid {c.border_subtle};
        }}
        QFrame#TopBar QLabel#Logo {{
            font-size: 18pt;
            font-weight: 700;
            color: {c.accent};
            letter-spacing: -0.5px;
        }}
        QFrame#TopBar QPushButton {{
            background-color: transparent;
            color: {c.text_muted};
            border: 1px solid {c.border_subtle};
            border-radius: {r.md}px;
            padding: 0px 12px;
            min-height: 32px;
            max-height: 32px;
            font-size: {f.sm}pt;
            font-weight: 500;
        }}
        QFrame#TopBar QPushButton:hover {{
            background-color: {c.bg_card};
            color: {c.text};
            border-color: {c.border};
        }}
        QFrame#TopBar QPushButton:pressed {{
            background-color: {c.bg_input};
        }}
        QFrame#TopBar QPushButton:disabled {{
            color: {c.text_disabled};
            border-color: {c.border_subtle};
        }}
    """


def panel_qss(side: str = "left") -> str:
    c = COLORS
    border = "border-right" if side == "left" else "border-left"
    return f"""
        QFrame#SidePanel {{
            background-color: {c.bg_panel};
            {border}: 1px solid {c.border_subtle};
        }}
    """


def board_holder_qss() -> str:
    c = COLORS
    return f"""
        QFrame#BoardHolder {{
            background-color: {c.bg_app};
        }}
    """
