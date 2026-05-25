"""
Main window — three-pane shell + board + real analysis pipeline (Session 3).

Session 3 wiring:
  * PgnInput widget (left panel) with sample/open/clear actions
  * MoveList (left panel) populated from analysis results
  * AnalyzerWorker runs Stockfish on a QThread, emits progress
  * Progress bar at bottom of left panel
  * EvalBar to the LEFT of the board
  * EvalGraph below the board, click-to-jump
  * Right panel shows eval number + move classification badge
  * Keyboard nav works as before
"""

from __future__ import annotations
from typing import Optional

import chess

from PySide6.QtCore import (
    Qt, QThread, QTimer, Signal,
    QPropertyAnimation, QEasingCurve, QSize,
)
from PySide6.QtGui import QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPushButton,
    QVBoxLayout, QWidget,
)

from app.config import (
    APP_NAME, BOARD_PX,
    LEFT_PANEL_W, RIGHT_PANEL_W, TOPBAR_HEIGHT,
    WINDOW_DEFAULT_W, WINDOW_DEFAULT_H, WINDOW_MIN_W, WINDOW_MIN_H,
    ENGINE_DEPTH, PIECES_DIR, ICONS_DIR,
)
from app.ui.icon_utils import svg_pixmap, svg_icon
from app.ui.theme import COLORS, FONTS, SPACE, topbar_qss, panel_qss, board_holder_qss
from app.ui.board_themes import BOARD_THEMES, load_board_theme, save_board_theme
from app.ui.piece_sets import load_piece_set, save_piece_set
from app.ui.widgets.board import BoardView
from app.ui.widgets.board_customize_dialog import BoardCustomizeDialog
from app.ui.widgets.coach_panel import CoachPanel, OpeningStrip, QuickActionBar
from app.core.opening_detector import detect as detect_opening
from app.ui.widgets.eval_bar import EvalBar
from app.ui.widgets.eval_graph import EvalGraph
from app.ui.widgets.move_list import MoveList, CLS_COLOR, CLS_ICON
from app.ui.widgets.pgn_input import PgnInput
from app.ui.widgets.profile_dialog import UserProfileDialog
from app.ui.widgets.subtitle_box import SubtitleBox
from app.core.pgn_parser import parse_pgn
from app.core.analyzer import AnalyzerWorker, AnalysisResult
from app.services.user_profile import UserProfile
from app.services.voice import Voice
from app.services.sounds import SoundService


# ═════════════════════════════════════════════════════════════════════════════
#  TOP BAR
# ═════════════════════════════════════════════════════════════════════════════
class TopBar(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("TopBar")
        self.setFixedHeight(TOPBAR_HEIGHT)
        self.setStyleSheet(topbar_qss())

        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACE.lg, 0, SPACE.lg, 0)
        layout.setSpacing(SPACE.sm)

        # Logo: SVG knight icon + "ChessLens" text
        logo_w = QWidget()
        logo_w.setStyleSheet("background: transparent;")
        logo_l = QHBoxLayout(logo_w)
        logo_l.setContentsMargins(0, 0, 0, 0)
        logo_l.setSpacing(8)
        _knight_lbl = QLabel()
        _knight_px = svg_pixmap(PIECES_DIR / "cburnett" / "wN.svg", 26, COLORS.accent)
        _knight_lbl.setPixmap(_knight_px)
        _knight_lbl.setFixedSize(26, 26)
        logo_l.addWidget(_knight_lbl)
        _title_lbl = QLabel("ChessLens")
        _title_lbl.setObjectName("Logo")
        logo_l.addWidget(_title_lbl)
        layout.addWidget(logo_w)
        layout.addStretch(1)

        _icon_sz = QSize(14, 14)
        self.btn_flip    = QPushButton("Flip")
        self.btn_flip.setIcon(svg_icon(ICONS_DIR / "flip.svg", 14, COLORS.text_muted))
        self.btn_flip.setIconSize(_icon_sz)
        self.btn_flip.setToolTip("Flip the board")
        self.btn_voice   = QPushButton("Voice")
        self.btn_voice.setIcon(svg_icon(ICONS_DIR / "volume-off.svg", 14, COLORS.text_muted))
        self.btn_voice.setIconSize(_icon_sz)
        self.btn_voice.setToolTip("Enable/disable voice coach")
        self.btn_pause   = QPushButton()
        self.btn_pause.setIcon(svg_icon(ICONS_DIR / "pause.svg", 14, COLORS.text_muted))
        self.btn_pause.setIconSize(_icon_sz)
        self.btn_pause.setToolTip("Pause coach voice (resumes on click)")
        self.btn_pause.setFixedWidth(38)
        self.btn_pause.setVisible(False)   # only shown when voice is enabled
        self.btn_profile = QPushButton()
        self.btn_profile.setIcon(svg_icon(ICONS_DIR / "user.svg", 14, COLORS.text_muted))
        self.btn_profile.setIconSize(_icon_sz)
        self.btn_profile.setToolTip("Your chess usernames — ChessLens uses these\n"
                                    "to recognize which side was you in a game.")
        self.btn_profile.setFixedWidth(38)
        for b in (self.btn_flip, self.btn_voice, self.btn_pause,
                  self.btn_profile):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            layout.addWidget(b)


# ═════════════════════════════════════════════════════════════════════════════
#  LEFT PANEL — PGN input + status + move list
# ═════════════════════════════════════════════════════════════════════════════
class LeftPanel(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("SidePanel")
        self.setFixedWidth(LEFT_PANEL_W)
        self.setStyleSheet(panel_qss("left"))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE.lg, SPACE.lg, SPACE.lg, SPACE.md)
        layout.setSpacing(SPACE.lg)

        title = QLabel("Game Review")
        title.setStyleSheet(
            f"font-size: {FONTS.xl}pt; font-weight: 600; color: {COLORS.text};"
            f" border-bottom: 1px solid {COLORS.border_subtle}; padding-bottom: 8px;"
        )
        layout.addWidget(title)

        self.pgn = PgnInput()
        layout.addWidget(self.pgn)

        # Progress bar
        self._progress_track = QFrame()
        self._progress_track.setFixedHeight(3)
        self._progress_track.setStyleSheet(f"background-color: {COLORS.bg_input};")
        self._progress_fill = QFrame(self._progress_track)
        self._progress_fill.setStyleSheet(f"background-color: {COLORS.accent};")
        self._progress_fill.setGeometry(0, 0, 0, 3)
        self._progress_anim: QPropertyAnimation | None = None
        layout.addWidget(self._progress_track)

        self.status_label = QLabel("Paste a PGN to begin")
        self.status_label.setStyleSheet(
            f"color: {COLORS.text_dim}; font-size: {FONTS.sm}pt;"
        )
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        # Per-player stats — two compact rows (white / black)
        self._stats_widget = QFrame()
        _stats_vbox = QVBoxLayout(self._stats_widget)
        _stats_vbox.setContentsMargins(0, 0, 0, 0)
        _stats_vbox.setSpacing(3)
        self._white_row = QHBoxLayout()
        self._white_row.setSpacing(SPACE.xs)
        self._black_row = QHBoxLayout()
        self._black_row.setSpacing(SPACE.xs)
        _stats_vbox.addLayout(self._white_row)
        _stats_vbox.addLayout(self._black_row)
        self._stats_widget.setVisible(False)
        layout.addWidget(self._stats_widget)

        div = QFrame()
        div.setProperty("role", "divider")
        div.style().unpolish(div); div.style().polish(div)
        layout.addWidget(div)

        moves_header = QLabel("Moves")
        moves_header.setProperty("role", "section")
        moves_header.style().unpolish(moves_header); moves_header.style().polish(moves_header)
        layout.addWidget(moves_header)

        self.move_list = MoveList()
        layout.addWidget(self.move_list, 1)


    # ─────────────────────────────────────────────────────────────────────
    def set_progress(self, pct: int, message: str) -> None:
        target_w = int(self._progress_track.width() * pct / 100)
        # Animate the width transition instead of jumping
        if self._progress_anim is not None:
            try:
                if self._progress_anim.state() == QPropertyAnimation.State.Running:
                    self._progress_anim.stop()
            except RuntimeError:
                pass
            self._progress_anim = None

        cur_geom = self._progress_fill.geometry()
        end_geom = cur_geom.adjusted(0, 0, target_w - cur_geom.width(), 0)
        end_geom.setWidth(target_w)
        end_geom.setHeight(3)

        anim = QPropertyAnimation(self._progress_fill, b"geometry", self._progress_fill)
        anim.setDuration(220)
        anim.setStartValue(cur_geom)
        anim.setEndValue(end_geom)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.finished.connect(lambda: setattr(self, "_progress_anim", None))
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
        self._progress_anim = anim

        self.status_label.setText(message)
        if pct >= 100:
            QTimer.singleShot(900, lambda: self._progress_fill.setGeometry(0, 0, 0, 3))

    def set_stats(self, white_stats: dict[str, int], black_stats: dict[str, int]) -> None:
        _CLS_BG = {
            "brilliant": "#2d1f4e", "best": "#1a2030", "good": "#1a2e1a",
            "inaccuracy": "#2e2a1a", "mistake": "#2e1f1a", "blunder": "#2e1a1a",
        }

        def _fill(row: QHBoxLayout, stats: dict[str, int], is_white: bool) -> None:
            while row.count():
                item = row.takeAt(0)
                w = item.widget()
                if w is not None:
                    w.setParent(None)
                    w.deleteLater()
            if not any(stats.values()):
                return
            king_lbl = QLabel()
            _king_svg = "wK.svg" if is_white else "bK.svg"
            _king_px = svg_pixmap(PIECES_DIR / "cburnett" / _king_svg, 18, COLORS.text_dim)
            king_lbl.setPixmap(_king_px)
            king_lbl.setFixedSize(18, 18)
            row.addWidget(king_lbl)
            for cls in ["brilliant", "best", "good", "inaccuracy", "mistake", "blunder"]:
                n = stats.get(cls, 0)
                if not n:
                    continue
                pill = QLabel(f"{CLS_ICON[cls]} {n}")
                pill.setStyleSheet(
                    f"color: {CLS_COLOR[cls]}; "
                    f"background-color: {_CLS_BG.get(cls, COLORS.bg_card)}; "
                    f"font-size: {FONTS.xs}pt; font-weight: 600;"
                    f"padding: 2px 6px; border-radius: 10px;"
                )
                row.addWidget(pill)
            row.addStretch(1)

        _fill(self._white_row, white_stats, True)
        _fill(self._black_row, black_stats, False)
        self._stats_widget.setVisible(
            any(white_stats.values()) or any(black_stats.values())
        )


# ═════════════════════════════════════════════════════════════════════════════
#  CENTER
# ═════════════════════════════════════════════════════════════════════════════
class CenterArea(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("BoardHolder")
        self.setStyleSheet(board_holder_qss())

        outer = QVBoxLayout(self)
        outer.setContentsMargins(SPACE.sm, SPACE.sm, SPACE.sm, SPACE.sm)
        outer.setSpacing(SPACE.sm)

        self.top_label = QLabel("Black")
        self.top_label.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        outer.addWidget(self.top_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Board + eval bar side-by-side
        board_row = QHBoxLayout()
        board_row.setContentsMargins(0, 0, 0, 0)
        board_row.setSpacing(8)
        board_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.eval_bar = EvalBar()
        self.board    = BoardView()
        board_row.addWidget(self.eval_bar, alignment=Qt.AlignmentFlag.AlignTop)
        board_row.addWidget(self.board)
        wrap = QWidget()
        wrap.setLayout(board_row)
        wrap.setMinimumHeight(BOARD_PX)
        outer.addWidget(wrap, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.bottom_label = QLabel("White")
        self.bottom_label.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        outer.addWidget(self.bottom_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Nav buttons — grouped in a pill container
        nav = QHBoxLayout()
        nav.setSpacing(8)
        nav.setAlignment(Qt.AlignmentFlag.AlignCenter)

        nav_group = QFrame()
        nav_group.setObjectName("NavGroup")
        nav_group.setStyleSheet(
            f"QFrame#NavGroup {{ background-color: {COLORS.bg_card}; border-radius: 8px;"
            f" border: 1px solid {COLORS.border}; }}"
            f"QFrame#NavGroup QPushButton {{ background: transparent; border: none;"
            f" border-radius: 6px; padding: 0; min-width: 36px; max-width: 36px;"
            f" min-height: 36px; max-height: 36px; }}"
            f"QFrame#NavGroup QPushButton:hover {{ background-color: {COLORS.bg_card_hi}; }}"
            f"QFrame#NavGroup QPushButton:pressed {{ background-color: {COLORS.bg_input}; }}"
        )
        nav_group.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        nav_gl = QHBoxLayout(nav_group)
        nav_gl.setContentsMargins(4, 4, 4, 4)
        nav_gl.setSpacing(0)

        self.btn_first = self._nav_btn(ICONS_DIR / "skip-back.svg")
        self.btn_prev  = self._nav_btn(ICONS_DIR / "chevron-left.svg")
        self.btn_next  = self._nav_btn(ICONS_DIR / "chevron-right.svg")
        self.btn_last  = self._nav_btn(ICONS_DIR / "skip-forward.svg")
        for b in (self.btn_first, self.btn_prev, self.btn_next, self.btn_last):
            nav_gl.addWidget(b)
        nav.addWidget(nav_group)

        self.move_indicator = QLabel("—")
        self.move_indicator.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.move_indicator.setStyleSheet(
            f"color: {COLORS.text_dim}; font-size: {FONTS.sm}pt;"
            f" background-color: {COLORS.bg_card}; border-radius: 10px;"
            f" border: 1px solid {COLORS.border}; padding: 4px 10px;"
        )
        nav.addWidget(self.move_indicator)

        # Customize board button — right-aligned next to nav
        nav.addStretch(1)
        self.btn_customize = QPushButton("🎨  Customize")
        self.btn_customize.setToolTip("Change board theme and piece set")
        self.btn_customize.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_customize.setStyleSheet(
            f"color: {COLORS.text_dim}; font-size: {FONTS.xs}pt;"
            f" background: transparent; border: 1px solid {COLORS.border};"
            f" border-radius: 4px; padding: 3px 10px;"
        )
        nav.addWidget(self.btn_customize)
        outer.addLayout(nav)

        # Eval graph — wrapped in a card for visual containment
        _eval_card = QFrame()
        _eval_card.setObjectName("EvalCard")
        _eval_card.setStyleSheet(
            f"QFrame#EvalCard {{ background-color: {COLORS.bg_panel};"
            f" border: 1px solid {COLORS.border_subtle}; border-radius: 8px; }}"
        )
        _eval_card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        _eval_card.setMinimumWidth(BOARD_PX + 20)
        _eval_card.setMaximumWidth(BOARD_PX + 20)
        _eval_card_layout = QVBoxLayout(_eval_card)
        _eval_card_layout.setContentsMargins(8, 2, 8, 2)
        _eval_card_layout.setSpacing(3)
        _eval_header = QLabel("Evaluation")
        _eval_header.setStyleSheet(
            f"color: {COLORS.text_dim}; font-size: {FONTS.xs}pt;"
            f" background: transparent; border: none;"
        )
        _eval_card_layout.addWidget(_eval_header)
        self.eval_graph = EvalGraph()
        self.eval_graph.setFixedHeight(30)
        _eval_card_layout.addWidget(self.eval_graph)
        outer.addWidget(_eval_card, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Subtitle box — shows what the AI voice is currently saying.
        # Constrained to match the board+eval-bar width so it sits visually
        # under the board, not stretched across the whole panel.
        self.subtitles = SubtitleBox()
        self.subtitles.setMinimumWidth(BOARD_PX + 20)
        self.subtitles.setMaximumWidth(BOARD_PX + 20)
        outer.addWidget(self.subtitles, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Flip-aware label state
        self._white_text = "White"
        self._black_text = "Black"
        self._flipped = False
        self.board.flipped_changed.connect(self._on_flipped)
        self._render_labels()

    def _nav_btn(self, icon_path) -> QPushButton:
        b = QPushButton()
        b.setIcon(svg_icon(icon_path, 16, COLORS.text_muted))
        b.setIconSize(QSize(16, 16))
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        return b

    def set_player_labels(self, white: str, w_acc: Optional[int],
                          black: str, b_acc: Optional[int],
                          w_elo: Optional[str] = None,
                          b_elo: Optional[str] = None,
                          you_color: Optional[str] = None) -> None:
        def _acc_color(acc: int) -> str:
            if acc > 85:  return "#81b64c"
            if acc >= 60: return "#e6c34a"
            return "#e65c4a"

        def fmt(name: str, elo: Optional[str], acc: Optional[int],
                is_you: bool) -> str:
            elo_part = f" ({elo})" if elo else ""
            you_part = "  • you" if is_you else ""
            if acc is not None:
                c = _acc_color(acc)
                acc_part = (f'   ·   Accuracy '
                            f'<span style="color:{c};font-weight:600">{acc}%</span>')
            else:
                acc_part = ""
            return f"{name}{elo_part}{you_part}{acc_part}"

        self._white_text = fmt(white, w_elo, w_acc, you_color == "white")
        self._black_text = fmt(black, b_elo, b_acc, you_color == "black")
        self._render_labels()

    def _on_flipped(self, flipped: bool) -> None:
        self._flipped = flipped
        self._render_labels()

    def _render_labels(self) -> None:
        if self._flipped:
            top, top_w = self._white_text, "600"; top_c = COLORS.text
            bot, bot_w = self._black_text, "400"; bot_c = COLORS.text_muted
        else:
            top, top_w = self._black_text, "400"; top_c = COLORS.text_muted
            bot, bot_w = self._white_text, "600"; bot_c = COLORS.text
        _pill = (f"background-color: {COLORS.bg_card}; border-radius: 999px;"
                 f"border: 1px solid {COLORS.border_subtle}; padding: 3px 12px;")
        self.top_label.setText(top)
        self.top_label.setStyleSheet(
            f"color: {top_c}; font-size: {FONTS.sm}pt; font-weight: {top_w}; {_pill}"
        )
        self.bottom_label.setText(bot)
        self.bottom_label.setStyleSheet(
            f"color: {bot_c}; font-size: {FONTS.sm}pt; font-weight: {bot_w}; {_pill}"
        )


# ═════════════════════════════════════════════════════════════════════════════
#  RIGHT
# ═════════════════════════════════════════════════════════════════════════════
class RightPanel(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("SidePanel")
        self.setFixedWidth(RIGHT_PANEL_W)
        self.setStyleSheet(panel_qss("right"))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE.lg, SPACE.lg, SPACE.lg, SPACE.lg)
        layout.setSpacing(SPACE.md)

        section = QLabel("ENGINE ANALYSIS")
        section.setProperty("role", "section")
        section.style().unpolish(section); section.style().polish(section)
        layout.addWidget(section)

        self.eval_num = QLabel("+0.0")
        self.eval_num.setStyleSheet(
            f"font-size: {FONTS.xxl}pt; font-weight: 700; color: {COLORS.text};"
        )
        layout.addWidget(self.eval_num)

        self.eval_sub = QLabel("Equal position")
        self.eval_sub.setStyleSheet(
            f"color: {COLORS.text_muted}; font-size: {FONTS.sm}pt;"
        )
        layout.addWidget(self.eval_sub)

        self.badge = QLabel("")
        self.badge.setStyleSheet(
            f"color: {COLORS.text_dim}; font-size: {FONTS.md}pt; font-weight: 600;"
            f"padding-top: 8px;"
        )
        layout.addWidget(self.badge)

        div = QFrame(); div.setProperty("role", "divider")
        div.style().unpolish(div); div.style().polish(div)
        layout.addWidget(div)

        coach_header = QLabel("COACH")
        coach_header.setProperty("role", "section")
        coach_header.style().unpolish(coach_header); coach_header.style().polish(coach_header)
        layout.addWidget(coach_header)

        # Engine attribution — builds trust by telling the user exactly what's
        # crunching their moves. Hover for more detail.
        engine_info = QLabel(f"Analysis: Stockfish · depth {ENGINE_DEPTH}")
        engine_info.setStyleSheet(
            f"color: {COLORS.text_dim}; font-size: {FONTS.xs}pt;"
            f"padding-bottom: 4px;"
        )
        engine_info.setToolTip(
            "All evaluations come from Stockfish — the world's strongest\n"
            "open-source chess engine, the same one chess.com uses for\n"
            f"its Game Review. ChessLens analyzes at depth {ENGINE_DEPTH},\n"
            "which gives reliable classifications for review purposes."
        )
        layout.addWidget(engine_info)

        # Quick-action bar — "Best | Explain | Next" (chess.com style)
        self.quick_actions = QuickActionBar()
        layout.addWidget(self.quick_actions)

        # Opening strip — book icon + name + ECO code
        self.opening_strip = OpeningStrip()
        layout.addWidget(self.opening_strip)

        self.coach_panel = CoachPanel()
        layout.addWidget(self.coach_panel, 1)


# ═════════════════════════════════════════════════════════════════════════════
#  MAIN WINDOW
# ═════════════════════════════════════════════════════════════════════════════
class MainWindow(QMainWindow):
    # Thread-safe status forwarding — emitted from any thread, handled on main
    voice_status_emitted = Signal(str, bool)
    # Subtitle line — emitted from any thread, displayed on main
    subtitle_emitted     = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(WINDOW_DEFAULT_W, WINDOW_DEFAULT_H)
        self.setMinimumSize(WINDOW_MIN_W, WINDOW_MIN_H)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.topbar = TopBar()
        root.addWidget(self.topbar)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        self.left   = LeftPanel()
        self.center = CenterArea()
        self.right  = RightPanel()
        body_layout.addWidget(self.left)
        body_layout.addWidget(self.center, 1)
        body_layout.addWidget(self.right)
        root.addWidget(body, 1)

        # State
        self._result: Optional[AnalysisResult] = None
        self._fens: list[tuple[str, Optional[chess.Move]]] = []
        self._cur_idx: int = 0
        self._thread: Optional[QThread] = None
        self._worker: Optional[AnalyzerWorker] = None
        self._nav_busy: bool = False

        # Voice service — starts disabled; user clicks 🔇 to enable
        # Status callback emits a Qt signal so it's marshalled to main thread
        self.voice_status_emitted.connect(self._on_voice_status_main)
        self.subtitle_emitted.connect(self.center.subtitles.set_text)
        self.voice = Voice(
            on_status=lambda msg, err=False: self.voice_status_emitted.emit(msg, err),
            on_speak=lambda text: self.subtitle_emitted.emit(text),
        )

        # User profile — "who am I" so we can auto-detect the color in each
        # game and offer the "only my moves" voice filter.
        self.user_profile = UserProfile.load()
        # When this game's PGN matches a saved username, we cache the
        # detected color here. None means "no match for this game" — the
        # auto filter then falls back to reading both sides.
        self._detected_color: Optional[str] = None

        # Sound effects — always on by default
        self.sounds = SoundService()

        # Wiring
        self.topbar.btn_flip.clicked.connect(self.center.board.flip)
        self.topbar.btn_voice.clicked.connect(self._toggle_voice)
        self.topbar.btn_pause.clicked.connect(self._toggle_pause)
        self.topbar.btn_profile.clicked.connect(self._open_profile)
        self.left.pgn.analyze_requested.connect(self._start_analysis)
        self.left.pgn.cancel_requested.connect(self._cancel_analysis)
        self.left.pgn.cleared.connect(self._reset)
        self.left.move_list.move_selected.connect(self._goto_move)
        self.center.eval_graph.move_clicked.connect(self._goto_position)
        # Explicit methods (NOT lambdas) — debuggable + reliable cur_idx refs
        self.center.btn_first.clicked.connect(self._nav_first)
        self.center.btn_prev.clicked.connect(self._nav_prev)
        self.center.btn_next.clicked.connect(self._nav_next)
        self.center.btn_last.clicked.connect(self._nav_last)
        self.center.board.prev_move_requested.connect(self._nav_prev)
        self.center.board.next_move_requested.connect(self._nav_next)
        self.center.board.first_move_requested.connect(self._nav_first)
        self.center.board.last_move_requested.connect(self._nav_last)

        # Quick-action bar wiring
        self.right.quick_actions.best_clicked.connect(self._on_best_clicked)
        self.right.quick_actions.explain_clicked.connect(self._on_explain_clicked)
        self.right.quick_actions.next_clicked.connect(self._nav_next)

        # Board customization dialog — lazy-created on first open
        self._customize_dlg: BoardCustomizeDialog | None = None
        self.center.btn_customize.clicked.connect(self._open_customize_dialog)

        # Restore saved board theme + piece set on startup
        _saved_theme = load_board_theme()
        _saved_piece_set = load_piece_set()
        self._apply_board_theme(_saved_theme, save=False)
        self._apply_piece_set(_saved_piece_set, save=False)

        # Reflect any voice settings restored from disk (enabled state, voice,
        # speed, etc.). Without this, the top-bar Voice button would always
        # show 🔇 on startup even though the user had voice on last session.
        self._refresh_voice_buttons()

        # F11 — toggle true fullscreen (chess.com / IDE convention).
        # Works regardless of which widget currently has focus.
        self._fullscreen_shortcut = QShortcut(QKeySequence("F11"), self)
        self._fullscreen_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self._fullscreen_shortcut.activated.connect(self._toggle_fullscreen)
        # Esc — exit fullscreen back to maximized
        self._exit_fs_shortcut = QShortcut(QKeySequence("Escape"), self)
        self._exit_fs_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self._exit_fs_shortcut.activated.connect(self._exit_fullscreen)

        QTimer.singleShot(50, self.center.board.setFocus)

    # ─────────────────────────────────────────────────────────────────────
    #  ANALYSIS LIFECYCLE
    # ─────────────────────────────────────────────────────────────────────
    def _start_analysis(self, pgn_text: str) -> None:
        if self._thread is not None:
            return

        try:
            parsed = parse_pgn(pgn_text)
        except Exception as e:
            QMessageBox.warning(self, "PGN error", str(e))
            return
        if not parsed.moves:
            QMessageBox.information(self, "Empty game",
                                    "This PGN has no moves to analyze.")
            return

        self.left.pgn.set_enabled_during_analysis(False)

        self._worker = AnalyzerWorker(parsed)
        self._thread = QThread(self)
        self._worker.moveToThread(self._thread)

        # CRITICAL: explicit QueuedConnection — PySide6's AutoConnection
        # doesn't reliably auto-route bound-method slots across threads,
        # which causes "Timers cannot be started from another thread" errors
        # when the slot then schedules QTimer.singleShot etc.
        self._worker.progress.connect(self.left.set_progress,
                                      Qt.ConnectionType.QueuedConnection)
        self._worker.finished.connect(self._on_analysis_finished,
                                      Qt.ConnectionType.QueuedConnection)
        self._worker.failed.connect(self._on_analysis_failed,
                                    Qt.ConnectionType.QueuedConnection)
        self._worker.cancelled.connect(self._on_analysis_cancelled,
                                       Qt.ConnectionType.QueuedConnection)

        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._thread.quit,
                                      Qt.ConnectionType.QueuedConnection)
        self._worker.failed.connect(self._thread.quit,
                                    Qt.ConnectionType.QueuedConnection)
        self._worker.cancelled.connect(self._thread.quit,
                                       Qt.ConnectionType.QueuedConnection)
        self._thread.finished.connect(self._cleanup_thread)

        self._thread.start()

    def _on_analysis_finished(self, result: AnalysisResult) -> None:
        self._result = result
        # Build FEN sequence
        starting_fen = result.parsed.starting_fen if result.parsed else chess.STARTING_FEN
        board = chess.Board(starting_fen)
        self._fens = [(board.fen(), None)]
        for am in result.moves:
            mv = chess.Move.from_uci(am.uci)
            board.push(mv)
            self._fens.append((board.fen(), mv))

        # ── Detect which color the user played ───────────────────────────────
        # Done BEFORE voice pre-computation so _detected_color is available
        # for user-perspective game-end messages (win vs loss).
        self._detected_color = self.user_profile.detect_color(result.parsed) \
            if result.parsed is not None else None

        # ── Pre-compute voice lines so navigation doesn't pay the cost ──────
        for am in result.moves:
            try:
                am.voice_line = self._build_voice_line(am)
            except Exception:
                am.voice_line = ""

        # ── Auto-flip the board to match the user's color ──────────────────
        # If we recognise sjefenfabian as Black, flip the board so Black sits
        # on the bottom — same behaviour as chess.com Game Review. Done
        # idempotently against the current flipped state so it never
        # double-flips on re-analyze.
        if self._detected_color is not None:
            want_flipped = (self._detected_color == "black")
            try:
                current = self.center.board.scene_.is_flipped()
            except Exception:
                current = False
            if current != want_flipped:
                self.center.board.flip()

        # Populate UI
        self.left.move_list.set_moves(result.moves)
        _cls_keys = ["brilliant", "best", "good", "inaccuracy", "mistake", "blunder"]
        self.left.set_stats(
            {c: sum(1 for m in result.moves if m.is_white     and m.classification == c) for c in _cls_keys},
            {c: sum(1 for m in result.moves if not m.is_white and m.classification == c) for c in _cls_keys},
        )
        if result.parsed is not None:
            self.center.set_player_labels(
                result.parsed.white, result.white_accuracy,
                result.parsed.black, result.black_accuracy,
                w_elo=result.parsed.white_elo,
                b_elo=result.parsed.black_elo,
                you_color=self._detected_color,
            )
        # Pass classifications so the graph draws chess.com-style colored dots
        classifications = [am.classification for am in result.moves]
        self.center.eval_graph.set_scores(
            result.ev_scores, cursor_idx=0, classifications=classifications)
        self._goto_position(0)
        self.left.pgn.set_enabled_during_analysis(True)
        # Friendly chime — analysis is ready
        self.sounds.play("ready")

    def _cancel_analysis(self) -> None:
        if self._worker is not None:
            self._worker.cancel()

    def _on_analysis_cancelled(self) -> None:
        self.left.set_progress(0, "")
        self.left.pgn.set_enabled_during_analysis(True)

    def _on_analysis_failed(self, message: str) -> None:
        self.left.set_progress(0, f"Error: {message}")
        QMessageBox.warning(self, "Analysis failed", message)
        self.left.pgn.set_enabled_during_analysis(True)

    def _cleanup_thread(self) -> None:
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None
        if self._thread is not None:
            self._thread.deleteLater()
            self._thread = None

    # ─────────────────────────────────────────────────────────────────────
    #  NAVIGATION
    # ─────────────────────────────────────────────────────────────────────
    def _goto_position(self, idx: int) -> None:
        if not self._fens:
            return
        idx = max(0, min(len(self._fens) - 1, idx))
        if idx == self._cur_idx and self._cur_idx != 0:
            return

        # Decide if a sound should play. Only play when stepping forward by
        # one move (idx == prev+1) — bulk jumps and rewinds stay silent so
        # the user isn't bombarded with sounds when scrubbing.
        play_sound = (idx == self._cur_idx + 1 and idx > 0)
        prev_idx = self._cur_idx

        fen, move = self._fens[idx]
        from_sq = move.from_square if move else None
        to_sq   = move.to_square   if move else None

        # ── Green "better" arrow + classification tint ───────────────────
        # CRITICAL: show the alternative to the move JUST PLAYED, not the
        # engine's recommendation for the NEXT move. This makes the arrow
        # visually match the coach's "Better: X" text. Without this fix
        # the arrow and the coach text point to different moves.
        # Also pass the classification so the destination square is tinted
        # red for blunders, orange for mistakes, green for best, etc.
        best = None
        cls  = None
        if (self._result is not None and idx > 0
                and idx <= len(self._result.moves)):
            am_just_played = self._result.moves[idx - 1]
            best = getattr(am_just_played, "alternative_move", None)
            # Fallback for backward-compat: if alternative_move isn't set
            # (older analysis result loaded somehow), fall back to best_move.
            if best is None:
                best = am_just_played.best_move
            cls = am_just_played.classification

        self.center.board.set_position(fen, from_sq, to_sq, best, cls=cls)

        # Eval display
        if self._result is not None:
            ev = self._result.ev_scores[idx] if idx < len(self._result.ev_scores) else 0.0
            self.center.eval_bar.set_eval(ev)
            self._update_eval_card(ev, idx)
        self.center.eval_graph.set_cursor(idx)
        self._cur_idx = idx

        if idx > 0:
            self.left.move_list.set_active_move(idx - 1)
        self._update_move_indicator()
        self._show_coach_for_index(idx)
        self._update_quick_actions(idx)
        self._update_opening_strip(idx)

        # Sound effect — after everything else so audio aligns with visual
        if play_sound and move is not None and 0 <= prev_idx < len(self._fens):
            prev_fen, _ = self._fens[prev_idx]
            try:
                board_before = chess.Board(prev_fen)
                self.sounds.play_for_move(board_before, move)
            except Exception:
                pass

    def _goto_move(self, move_index: int) -> None:
        self._goto_position(move_index + 1)

    # ─── Explicit nav slots (avoid late-binding traps with lambdas) ───────
    def _nav_first(self) -> None:
        if self._nav_busy: return
        self._nav_busy = True
        QTimer.singleShot(80, lambda: setattr(self, '_nav_busy', False))
        self._goto_position(0)
        self.center.board.setFocus()

    def _nav_prev(self) -> None:
        if self._nav_busy: return
        self._nav_busy = True
        QTimer.singleShot(80, lambda: setattr(self, '_nav_busy', False))
        self._goto_position(self._cur_idx - 1)
        self.center.board.setFocus()

    def _nav_next(self) -> None:
        if self._nav_busy: return
        self._nav_busy = True
        QTimer.singleShot(80, lambda: setattr(self, '_nav_busy', False))
        self._goto_position(self._cur_idx + 1)
        self.center.board.setFocus()

    def _nav_last(self) -> None:
        if self._nav_busy: return
        self._nav_busy = True
        QTimer.singleShot(80, lambda: setattr(self, '_nav_busy', False))
        self._goto_position(len(self._fens) - 1)
        self.center.board.setFocus()

    def _update_eval_card(self, eval_cp: float, idx: int) -> None:
        if eval_cp >= 9000:
            mate_in = max(1, round(10000 - eval_cp))
            text = f"M{mate_in}"
            color = COLORS.text
            who = f"Checkmate in {mate_in}"
        elif eval_cp <= -9000:
            mate_in = max(1, round(10000 + eval_cp))
            text = f"M{mate_in}"
            color = COLORS.text_muted
            who = f"Checkmate in {mate_in}"
        else:
            text = f"{eval_cp:+.1f}"
            color = COLORS.text if eval_cp >= 0 else COLORS.text_muted
            thresholds = [(3, "White is winning"), (1, "White is better"),
                          (0.3, "Slight edge for White"), (-0.3, "Equal"),
                          (-1, "Slight edge for Black"), (-3, "Black is better")]
            who = "Black is winning"
            for thr, lbl in thresholds:
                if eval_cp >= thr:
                    who = lbl
                    break
        self.right.eval_num.setText(text)
        self.right.eval_num.setStyleSheet(
            f"font-size: {FONTS.xxl}pt; font-weight: 700; color: {color};"
        )
        self.right.eval_sub.setText(who)

        if self._result is not None and 0 < idx <= len(self._result.moves):
            am = self._result.moves[idx - 1]
            cls_color = CLS_COLOR.get(am.classification, COLORS.text_dim)
            cls_icon  = CLS_ICON.get(am.classification, "·")
            label_map = {
                "brilliant": "Brilliant!", "best": "Best Move", "good": "Good Move",
                "inaccuracy": "Inaccuracy", "mistake": "Mistake", "blunder": "Blunder",
            }
            label = label_map.get(am.classification, "")
            self.right.badge.setText(f"{cls_icon}  {label}")
            self.right.badge.setStyleSheet(
                f"color: {cls_color}; font-size: {FONTS.md}pt; font-weight: 600;"
                f"padding-top: 8px;"
            )
        else:
            self.right.badge.setText("")

    def _update_move_indicator(self) -> None:
        total = max(0, len(self._fens) - 1)
        if self._cur_idx == 0:
            self.center.move_indicator.setText(f"Start  ·  {total} moves")
        else:
            side = "w" if self._cur_idx % 2 == 1 else "b"
            mn = (self._cur_idx + 1) // 2
            self.center.move_indicator.setText(f"Move {mn}{side}  /  {total}")

    # ─────────────────────────────────────────────────────────────────────
    #  COACH + VOICE
    # ─────────────────────────────────────────────────────────────────────
    def _show_coach_for_index(self, idx: int) -> None:
        """Display coaching cards + speak (if enabled) for position `idx`."""
        if self._result is None or idx <= 0 or idx > len(self._result.moves):
            self.right.coach_panel._show_placeholder()
            # No move at this position → no subtitle. Also stop any in-flight
            # speech so we don't keep talking about the previous move.
            self.voice.stop()
            self.center.subtitles.set_text("")
            return
        am = self._result.moves[idx - 1]

        # ── Per-color filter (cheap check — must run before speaking) ───────
        # "auto" means "only my moves" — resolves to the color detected from
        # the PGN headers against the user's saved usernames. If no username
        # matched (someone else's game), auto falls back to reading both.
        rc = getattr(self.voice, "read_color", "both")
        if rc == "auto":
            rc = self._detected_color or "both"
        is_for_white = am.is_white
        skip = (rc == "white" and not is_for_white) or \
               (rc == "black" and is_for_white)
        if skip:
            self.voice.stop()
            self.center.subtitles.set_text("")
            # Still render the coach card so the user can SEE the analysis
            side = "w" if am.is_white else "b"
            header = f"Move {am.move_number}{side} — {am.san}"
            self.right.coach_panel.show_for_move(am, header)
            return

        # ── Speak FIRST so audio generation starts ASAP ─────────────────────
        # The TTS engine (especially Kokoro) needs ~0.2-1s to produce audio;
        # queuing it before we render the coach cards cuts the perceived
        # delay between move-change and voice-start significantly.
        vt = am.voice_line if getattr(am, "voice_line", None) else self._build_voice_line(am)
        self.voice.stop()
        self.center.subtitles.set_text("")
        if self.voice.enabled and vt and not self.voice.paused:
            self.voice.speak(vt)
        elif vt:
            self.center.subtitles.set_text(vt)
        else:
            self.center.subtitles.set_text("")

        # ── Now the heavier UI rendering ────────────────────────────────────
        side = "w" if am.is_white else "b"
        header = f"Move {am.move_number}{side} — {am.san}"
        self.right.coach_panel.show_for_move(am, header)

    def _game_end_voice_line(self, am, exp: dict) -> str:
        """User-perspective voice line for a game-ending move."""
        end_type   = exp.get("game_end_type", "")
        winner     = exp.get("winner", "")
        user_color = self._detected_color          # "white" / "black" / None
        user_won   = user_color is not None and winner == user_color
        user_lost  = (user_color is not None
                      and winner not in ("draw", user_color))
        side = "White" if am.is_white else "Black"
        n    = am.move_number

        if end_type == "checkmate":
            if user_won:
                return f"Move {n}. Checkmate — excellent finish!"
            if user_lost:
                return (f"Move {n}. You were checkmated. "
                        f"Let's review where things went wrong.")
            return f"Move {n}. Checkmate — {side} wins!"

        if end_type == "stalemate":
            return (f"Move {n}. Stalemate — the game ends in a draw. "
                    f"The opponent had no legal moves.")

        if "draw" in end_type:
            base = exp.get("voice", "The game is drawn.")
            return f"Move {n}. {base}"

        if end_type == "resignation":
            if user_won:
                return f"Move {n}. Your opponent resigned — well played!"
            if user_lost:
                return (f"Move {n}. You resigned. A tough result — "
                        f"let's find where things went wrong.")
            return f"Move {n}. {exp.get('voice', 'The game ends here.')}"

        return f"Move {n}. {exp.get('voice', 'The game ends here.')}"

    def _build_voice_line(self, am) -> str:
        """Construct the spoken sentence for an AnalyzedMove.
        No pawn-count numbers — conversational coach language only.
        For good/best/brilliant moves, append the WHY (capture, development,
        castling, etc.) so the voice tells you something useful, not just
        "the engine's top choice"."""
        cls = am.classification
        side = "White" if am.is_white else "Black"
        exp = am.explanation or {}

        # Game-end moves get dedicated user-perspective messages instead of
        # the generic move-quality framing below.
        if isinstance(exp, dict) and exp.get("game_end"):
            return self._game_end_voice_line(am, exp)

        exp_voice = exp.get("voice", "") if isinstance(exp, dict) else ""
        reasons = exp.get("reasons", []) if isinstance(exp, dict) else []
        is_forced = any("forced" in r for r in reasons)

        # Strip generic "engine completely agrees" placeholder — don't speak it
        if exp_voice == "The engine completely agrees with this move.":
            exp_voice = ""

        if cls == "brilliant":
            head = (f"Move {am.move_number}. {side} played {am.san} — "
                    f"a brilliant move, the engine's top choice")
            return f"{head}. {exp_voice}" if exp_voice else f"{head}!"

        if cls == "best":
            if is_forced:
                return (f"Move {am.move_number}. {side} played {am.san}. "
                        f"This was the only legal move.")
            head = (f"Move {am.move_number}. {side} played {am.san}. "
                    f"The engine's top choice")
            return f"{head} — {exp_voice}" if exp_voice else f"{head}."

        if cls == "good":
            if "stronger" in exp_voice:
                # Coach already wrote a full "X was stronger" sentence
                return f"Move {am.move_number}. {exp_voice}"
            head = f"Move {am.move_number}. {side} played {am.san}. A solid choice"
            return f"{head} — {exp_voice}" if exp_voice else f"{head}."

        # Inaccuracy / mistake / blunder — no pawn-counting
        qual = {"inaccuracy": "an inaccuracy",
                "mistake":    "a mistake",
                "blunder":    "a blunder"}.get(cls, "a misstep")
        if exp_voice:
            return f"Move {am.move_number}. {exp_voice} That was {qual}."
        return (f"Move {am.move_number}. {side} played {am.san} — {qual}.")

    def _toggle_voice(self) -> None:
        """Open the voice settings dialog. Dialog handles enable/disable."""
        from app.ui.widgets.voice_settings import VoiceSettingsDialog
        from app.services.voice import KOKORO_MODEL, KOKORO_VPACK

        dlg = VoiceSettingsDialog(self.voice, self)
        dlg.download_requested.connect(
            lambda: self.voice.download_kokoro(self._on_kokoro_progress)
        )
        dlg.exec()
        self._refresh_voice_buttons()

    def _toggle_pause(self) -> None:
        """Flip pause state. Visible only when voice is enabled."""
        self.voice.toggle_pause()
        self._refresh_voice_buttons()

    def _toggle_fullscreen(self) -> None:
        """F11 toggle: borderless fullscreen ↔ maximized.
        Pressed once: enters true fullscreen (hides title bar, taskbar).
        Pressed again (or Esc): returns to maximized state.
        """
        if self.isFullScreen():
            self.showMaximized()
        else:
            self.showFullScreen()

    def _exit_fullscreen(self) -> None:
        """Esc: only act if we're in fullscreen — otherwise let other
        widgets handle Escape (e.g. closing a focused dialog).
        """
        if self.isFullScreen():
            self.showMaximized()

    def _open_profile(self) -> None:
        """Top-bar 👤 button: open the username manager.
        After it closes we re-detect the color against the loaded PGN so
        any newly-added handles take effect on the current game without
        re-running analysis.
        """
        dlg = UserProfileDialog(self.user_profile, self)
        dlg.exec()
        if self._result is not None and self._result.parsed is not None:
            self._detected_color = self.user_profile.detect_color(self._result.parsed)
            # Refresh • you tag on player labels
            self.center.set_player_labels(
                self._result.parsed.white, self._result.white_accuracy,
                self._result.parsed.black, self._result.black_accuracy,
                w_elo=self._result.parsed.white_elo,
                b_elo=self._result.parsed.black_elo,
                you_color=self._detected_color,
            )
            # If a coach line is on screen, re-evaluate the filter
            if self._cur_idx > 0:
                self._show_coach_for_index(self._cur_idx)

    # ── Quick-action handlers ──────────────────────────────────────────────────────
    def _current_analyzed_move(self):
        """Return the AnalyzedMove for the position we're currently on,
        or None if we're at the start or haven't analyzed yet."""
        if (self._result is None or self._cur_idx <= 0
                or self._cur_idx > len(self._result.moves)):
            return None
        return self._result.moves[self._cur_idx - 1]

    def _on_best_clicked(self) -> None:
        """"Best" button: emphasize the engine's alternative on the board
        and speak it out loud. If the user already played the best move,
        affirm that instead."""
        am = self._current_analyzed_move()
        if am is None:
            return
        alt = getattr(am, "alternative_move", None) or am.best_move
        played_was_best = (am.classification in ("best", "brilliant")
                           or (alt is not None and alt.uci() == am.uci))
        # Brief pulse of the destination square so the user looks at the board
        self._pulse_best_arrow()
        if played_was_best:
            line = (f"You played the best move, {am.san}. "
                    f"The engine completely agrees.")
        elif alt is not None:
            # Format like "e2 to e4"
            u = alt.uci()
            line = (f"Better was {u[:2]} to {u[2:4]} — the engine's top choice.")
        else:
            line = "No alternative move available for this position."
        # Speak even if voice is disabled — user explicitly asked for it.
        # If voice is paused, un-pause for this request? No — respect the
        # paused state. Just show the subtitle as a fallback.
        if self.voice.enabled and not self.voice.paused:
            self.voice.speak(line)
        else:
            self.center.subtitles.set_text(line)

    def _on_explain_clicked(self) -> None:
        """"Explain" button: read the full "Why" coach text aloud."""
        am = self._current_analyzed_move()
        if am is None:
            return
        exp = am.explanation or {}
        # Prefer the voice version (concise) but fall back to the card text
        text = exp.get("voice", "") if isinstance(exp, dict) else ""
        if not text:
            text = exp.get("card", "") if isinstance(exp, dict) else ""
        # Strip any newlines so the speech flows
        text = (text or "").replace("\n", ". ").strip()
        if not text:
            text = f"No additional explanation for {am.san}."
        # Prepend move context so the user knows what's being explained
        line = f"Move {am.move_number}. {text}"
        if self.voice.enabled and not self.voice.paused:
            self.voice.speak(line)
        else:
            self.center.subtitles.set_text(line)

    def _pulse_best_arrow(self) -> None:
        """Briefly emphasize the green "better move" arrow so the user
        notices it when they click Best. Implemented as a transient
        opacity dip-and-return via QPropertyAnimation on the arrow item."""
        scene = self.center.board.scene_
        arrow = getattr(scene, "_best_arrow", None)
        if arrow is None:
            return
        # Two-step pulse: dim to 0.25 then back to 0.78 (its normal opacity)
        from PySide6.QtCore import QPropertyAnimation, QEasingCurve
        anim = QPropertyAnimation(arrow, b"opacity", arrow)
        anim.setDuration(450)
        anim.setKeyValueAt(0.0, 0.78)
        anim.setKeyValueAt(0.5, 0.20)
        anim.setKeyValueAt(1.0, 0.78)
        anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def _update_quick_actions(self, idx: int) -> None:
        """Sync quick-action button enable states to the current position."""
        if self._result is None or idx <= 0 or idx > len(self._result.moves):
            self.right.quick_actions.set_enabled_for(False, False,
                                                     has_next=idx < len(self._fens) - 1)
            return
        am = self._result.moves[idx - 1]
        exp = am.explanation or {}
        has_explanation = bool(
            (isinstance(exp, dict)
             and (exp.get("voice") or exp.get("card")))
        )
        # "Best" is meaningful as long as there's an alternative move on file
        # (even if it matches what was played — then it just affirms)
        has_alternative = (getattr(am, "alternative_move", None) is not None
                           or am.best_move is not None)
        has_next = idx < len(self._fens) - 1
        self.right.quick_actions.set_enabled_for(
            has_alternative, has_explanation, has_next)

    def _update_opening_strip(self, idx: int) -> None:
        if self._result is None or idx == 0:
            self.right.opening_strip.clear()
            return
        sans = [am.san for am in self._result.moves[:idx]]
        match = detect_opening(sans)
        if match:
            eco, name = match
            self.right.opening_strip.set_opening(eco, name)
        else:
            self.right.opening_strip.set_out_of_book()

    def _apply_board_theme(self, name: str, save: bool = True) -> None:
        colors = BOARD_THEMES.get(name)
        if colors is None:
            return
        self.center.board.set_square_colors(colors["dark"], colors["light"])
        if save:
            save_board_theme(name)

    def _apply_piece_set(self, name: str, save: bool = True) -> None:
        self.center.board.set_piece_set(name)
        if save:
            save_piece_set(name)

    def _open_customize_dialog(self) -> None:
        if self._customize_dlg is None:
            self._customize_dlg = BoardCustomizeDialog(self)
            self._customize_dlg.theme_selected.connect(self._apply_board_theme)
            self._customize_dlg.piece_set_selected.connect(self._apply_piece_set)
        # Sync current selections into dialog before showing
        self._customize_dlg.set_active_theme(load_board_theme())
        self._customize_dlg.set_active_piece_set(load_piece_set())
        self._customize_dlg.exec()

    def _refresh_voice_buttons(self) -> None:
        """Sync top-bar voice + pause button icons to current Voice state."""
        _sz = QSize(14, 14)
        if self.voice.enabled:
            self.topbar.btn_voice.setIcon(
                svg_icon(ICONS_DIR / "volume.svg", 14, COLORS.accent))
            self.topbar.btn_pause.setVisible(True)
            _pause_ico = "play.svg" if self.voice.paused else "pause.svg"
            self.topbar.btn_pause.setIcon(
                svg_icon(ICONS_DIR / _pause_ico, 14, COLORS.text_muted))
        else:
            self.topbar.btn_voice.setIcon(
                svg_icon(ICONS_DIR / "volume-off.svg", 14, COLORS.text_muted))
            self.topbar.btn_pause.setVisible(False)
        self.topbar.btn_voice.setIconSize(_sz)
        self.topbar.btn_pause.setIconSize(_sz)

    def _on_voice_status_main(self, msg: str, err: bool) -> None:
        # Always runs on main thread (via Qt::AutoConnection on Signal)
        self.left.status_label.setText(f"Voice: {msg}")

    def _on_kokoro_progress(self, msg: str, done: bool) -> None:
        # Re-route via the same signal so we're thread-safe
        self.voice_status_emitted.emit(msg, False)

    def _reset(self) -> None:
        self._result = None
        self._fens = []
        self._cur_idx = 0
        self.left.move_list.set_moves([])
        self.left.set_stats({}, {})
        self.center.eval_bar.set_eval(0.0, animate=False)
        self.center.eval_graph.set_scores([])
        self.center.board.reset()
        self.right.eval_num.setText("+0.0")
        self.right.eval_sub.setText("Equal position")
        self.right.badge.setText("")
        self.right.coach_panel._show_placeholder()
        self.center.move_indicator.setText("—")
        self.right.opening_strip.clear()
        self.center.set_player_labels("White", None, "Black", None)
