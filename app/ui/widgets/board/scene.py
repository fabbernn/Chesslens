"""
BoardScene — the QGraphicsScene that holds the chess board.

Owns:
  * 64 square rectangles (created once, recolored on demand)
  * 8 file labels + 8 rank labels (coord text)
  * piece items keyed by square
  * engine best-move arrow (singleton)
  * user-drawn arrows + circles (dicts)
  * live drag-preview arrow during right-click drag

Public API:
  set_position(fen, from_sq=None, to_sq=None, best=None)
      → animates moved piece, recolors highlights, redraws best arrow
  flip()
  reset()
  set_best_arrow(move | None)
  clear_user_drawings()
"""

from __future__ import annotations
from typing import Optional

import chess

from PySide6.QtCore import (
    QObject, QPointF, QPropertyAnimation, QRectF, Qt, Signal,
)
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPen
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect,
    QGraphicsItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
)

from app.config import SQUARE_PX, BOARD_PX, ANIM_MOVE_MS
from app.ui.animations import Curves
from app.ui.theme import COLORS
from app.ui.widgets.board.items import ArrowItem, CircleItem, PieceItem
from app.ui.widgets.board.renderer import PieceRenderer


class BoardScene(QGraphicsScene):
    """Pure presentation — accepts FEN strings, renders the position."""

    # Z layers
    Z_SQUARE     = 0
    Z_HIGHLIGHT  = 1
    Z_COORD      = 5
    Z_BEST_ARROW = 20
    Z_PIECE      = 30
    Z_USER_DRAW  = 40
    Z_DRAG       = 50

    # Signals the view will translate from mouse events
    request_clear_drawings = Signal()       # left-click anywhere
    flipped_changed = Signal(bool)          # board orientation changed

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.setSceneRect(0, 0, BOARD_PX, BOARD_PX)
        self.setBackgroundBrush(QColor(COLORS.bg_app))

        self._board     = chess.Board()
        self._flipped   = False
        self._sq_px     = SQUARE_PX
        self._renderer  = PieceRenderer(SQUARE_PX)
        self._renderer.warmup()

        # Active square colors — may be changed at runtime via set_square_colors
        self._sq_dark  = COLORS.board_dark
        self._sq_light = COLORS.board_light

        # Pre-computed gradient brushes — 3% lighter at top breaks the
        # flat-plastic look without any per-frame cost.
        self._brush_light = self._make_square_brush(True,  self._sq_light, self._sq_dark)
        self._brush_dark  = self._make_square_brush(False, self._sq_light, self._sq_dark)

        # Item registries
        self._sq_items:    dict[int, QGraphicsRectItem]      = {}
        self._coord_items: list[QGraphicsSimpleTextItem]     = []
        self._piece_items: dict[int, PieceItem]              = {}
        self._user_arrows: dict[tuple[int, int], ArrowItem]  = {}
        self._user_circles:dict[int, CircleItem]             = {}
        self._best_arrow:  Optional[ArrowItem] = None
        self._best_move:   Optional[chess.Move] = None
        self._drag_arrow:  Optional[ArrowItem] = None
        self._anim:        Optional[QPropertyAnimation] = None
        self._anim_gen:    int = 0   # incremented each time a new animation starts

        # Last-move highlight squares (for square recoloring)
        self._hl_from: Optional[int] = None
        self._hl_to:   Optional[int] = None
        # Classification of the last move — drives the destination tint.
        # None or "good" → standard yellow. Other values use the per-class
        # palette entries (see _brush_for_square).
        self._hl_cls:  Optional[str] = None

        # Hover square — very subtle highlight while the mouse is over the board
        self._hover_sq: Optional[int] = None

        # Build static geometry
        self._build_squares()
        self._build_coords()
        self._sync_pieces(animate=False)

    # ═════════════════════════════════════════════════════════════════════
    #  GEOMETRY HELPERS
    # ═════════════════════════════════════════════════════════════════════
    def square_top_left(self, sq: int) -> QPointF:
        """Top-left corner of a square in scene coords."""
        if self._flipped:
            file = 7 - chess.square_file(sq)
            rank = chess.square_rank(sq)
        else:
            file = chess.square_file(sq)
            rank = 7 - chess.square_rank(sq)
        return QPointF(file * self._sq_px, rank * self._sq_px)

    def square_center(self, sq: int) -> QPointF:
        tl = self.square_top_left(sq)
        return QPointF(tl.x() + self._sq_px / 2, tl.y() + self._sq_px / 2)

    def square_at_scene_pos(self, scene_pos: QPointF) -> Optional[int]:
        """Convert scene pixel coordinates → chess square, or None if outside."""
        x, y = scene_pos.x(), scene_pos.y()
        if x < 0 or y < 0 or x >= BOARD_PX or y >= BOARD_PX:
            return None
        file = int(x // self._sq_px)
        rank = int(y // self._sq_px)
        if self._flipped:
            return chess.square(7 - file, rank)
        return chess.square(file, 7 - rank)

    # ═════════════════════════════════════════════════════════════════════
    #  STATIC GEOMETRY — build once, recolor on demand
    # ═════════════════════════════════════════════════════════════════════
    def _build_squares(self) -> None:
        pen = QPen(Qt.PenStyle.NoPen)
        for sq in chess.SQUARES:
            tl = self.square_top_left(sq)
            rect = QGraphicsRectItem(tl.x(), tl.y(), self._sq_px, self._sq_px)
            rect.setPen(pen)
            rect.setBrush(self._brush_for_square(sq))
            rect.setZValue(self.Z_SQUARE)
            self.addItem(rect)
            self._sq_items[sq] = rect

    def _build_coords(self) -> None:
        files_str = "abcdefgh" if not self._flipped else "hgfedcba"
        ranks_str = "87654321" if not self._flipped else "12345678"
        # Smaller, not bold — labels should read as ambient, not compete with pieces
        font = QFont()
        font.setPointSize(6)

        for i, ch in enumerate(files_str):
            is_light_sq = (i + 7) % 2 == 0
            color = COLORS.board_dark if is_light_sq else COLORS.board_light
            t = QGraphicsSimpleTextItem(ch)
            t.setFont(font)
            t.setBrush(QBrush(QColor(color)))
            t.setOpacity(0.75)   # soft — blends into the square
            br = t.boundingRect()
            # Bottom-right corner of the bottom-row square (chess.com positioning)
            t.setPos(i * self._sq_px + self._sq_px - br.width() - 2,
                     BOARD_PX - br.height() - 1)
            t.setZValue(self.Z_COORD)
            self.addItem(t)
            self._coord_items.append(t)

        for i, ch in enumerate(ranks_str):
            is_light_sq = (i % 2 == 0)
            color = COLORS.board_dark if is_light_sq else COLORS.board_light
            t = QGraphicsSimpleTextItem(ch)
            t.setFont(font)
            t.setBrush(QBrush(QColor(color)))
            t.setOpacity(0.75)
            # Top-left corner of the left-column square
            t.setPos(2, i * self._sq_px + 2)
            t.setZValue(self.Z_COORD)
            self.addItem(t)
            self._coord_items.append(t)

    def _rebuild_coords(self) -> None:
        for t in self._coord_items:
            self.removeItem(t)
        self._coord_items.clear()
        self._build_coords()

    @staticmethod
    def _make_square_brush(light: bool, light_color: str, dark_color: str) -> QBrush:
        base = QColor(light_color if light else dark_color)
        top  = base.lighter(103)
        grad = QLinearGradient(0.0, 0.0, 0.0, 1.0)
        grad.setCoordinateMode(QLinearGradient.CoordinateMode.ObjectBoundingMode)
        grad.setColorAt(0.0, top)
        grad.setColorAt(1.0, base)
        return QBrush(grad)

    @staticmethod
    def _make_highlight_brush(color_hex: str, darker: int = 100) -> QBrush:
        """Gradient brush for last-move highlight squares — slightly lighter at top."""
        base = QColor(color_hex)
        if darker != 100:
            base = base.darker(darker)
        top = base.lighter(108)
        grad = QLinearGradient(0.0, 0.0, 0.0, 1.0)
        grad.setCoordinateMode(QLinearGradient.CoordinateMode.ObjectBoundingMode)
        grad.setColorAt(0.0, top)
        grad.setColorAt(1.0, base)
        return QBrush(grad)

    def _brush_for_square(self, sq: int) -> QBrush:
        if sq == self._hl_from:
            return self._make_highlight_brush(COLORS.board_from, darker=118)
        if sq == self._hl_to:
            color = self._dest_color_for_class(self._hl_cls)
            return self._make_highlight_brush(color)
        file = chess.square_file(sq)
        rank = chess.square_rank(sq)
        light = (file + rank) % 2 == 1
        if sq == self._hover_sq:
            base = QColor(self._sq_light if light else self._sq_dark)
            return QBrush(base.lighter(106))
        return self._brush_light if light else self._brush_dark

    @staticmethod
    def _dest_color_for_class(cls: Optional[str]) -> str:
        """Map move classification → destination-square tint (chess.com style)."""
        if cls == "brilliant":  return COLORS.board_brilliant_to
        if cls == "best":       return COLORS.board_best_to
        if cls == "good":       return COLORS.board_good_to
        if cls == "inaccuracy": return COLORS.board_inaccuracy_to
        if cls == "mistake":    return COLORS.board_mistake_to
        if cls == "blunder":    return COLORS.board_blunder_to
        return COLORS.board_to

    def _recolor_squares(self) -> None:
        for sq, rect in self._sq_items.items():
            rect.setBrush(self._brush_for_square(sq))

    def set_square_colors(self, dark_hex: str, light_hex: str) -> None:
        """Switch board square colors instantly — no repaint lag."""
        self._sq_dark  = dark_hex
        self._sq_light = light_hex
        self._brush_light = self._make_square_brush(True,  light_hex, dark_hex)
        self._brush_dark  = self._make_square_brush(False, light_hex, dark_hex)
        self._recolor_squares()

    def set_piece_set(self, name: str) -> None:
        """Switch piece set by name — re-renders all pieces instantly."""
        self._renderer.set_piece_set(name)
        self._renderer.warmup()
        # Rebuild all on-screen piece items with the new pixmaps
        for sq, item in self._piece_items.items():
            piece = self._board.piece_at(sq)
            if piece is not None:
                item.set_pixmap(self._renderer.pixmap_for(piece))

    # ═════════════════════════════════════════════════════════════════════
    #  PIECE SYNC — reposition existing items, only create/destroy on need
    # ═════════════════════════════════════════════════════════════════════
    def _sync_pieces(self, animate: bool = True,
                     moved_from: Optional[int] = None,
                     moved_to: Optional[int] = None) -> None:
        """Sync graphics items to self._board state."""
        occupied: dict[int, chess.Piece] = {}
        for sq in chess.SQUARES:
            p = self._board.piece_at(sq)
            if p:
                occupied[sq] = p

        # Remove items whose square is empty or where the piece type changed
        to_remove = []
        for sq, item in self._piece_items.items():
            new_piece = occupied.get(sq)
            if new_piece is None or new_piece.symbol() != item.piece_symbol():
                to_remove.append(sq)
        for sq in to_remove:
            # If this piece is the one we're animating, don't destroy it yet
            if animate and sq == moved_from:
                continue
            item = self._piece_items.pop(sq)
            self.removeItem(item)

        # Create / reposition items
        for sq, piece in occupied.items():
            if animate and sq == moved_to and moved_from in self._piece_items:
                # The mover is currently sitting at moved_from — animate it
                continue
            existing = self._piece_items.get(sq)
            if existing is not None:
                # Reposition only — flip may have changed coords
                tl = self.square_top_left(sq)
                existing.setPos(tl)
                continue

            # Create new piece item
            pm = self._renderer.pixmap_for(piece)
            item = PieceItem(pm, self._sq_px, sq)
            item._piece_symbol = piece.symbol()
            item.setPos(self.square_top_left(sq))
            self.addItem(item)
            self._piece_items[sq] = item

        # Trigger the animation for the moving piece
        if animate and moved_from is not None and moved_to is not None:
            mover = self._piece_items.pop(moved_from, None)
            if mover is not None:
                target_tl = self.square_top_left(moved_to)
                self._piece_items[moved_to] = mover
                mover.square = moved_to
                self._animate_piece(mover, target_tl)
                # Also update sprite if pawn promoted
                expected = occupied.get(moved_to)
                if expected and getattr(mover, "_piece_symbol",
                                          "") != expected.symbol():
                    mover.set_pixmap(self._renderer.pixmap_for(expected))
                    mover._piece_symbol = expected.symbol()
            else:
                # Animation impossible (e.g. piece wasn't where we expected) —
                # fall back to a static refresh
                self._sync_pieces(animate=False)

    def _animate_piece(self, item: PieceItem, end_top_left: QPointF) -> None:
        """Slide a piece smoothly to its destination using QPropertyAnimation."""
        # Previous animation may have been auto-deleted (DeleteWhenStopped).
        # Defensively check then clear the dead reference.
        if self._anim is not None:
            try:
                if self._anim.state() != QPropertyAnimation.State.Stopped:
                    self._anim.stop()
            except RuntimeError:
                pass
            self._anim = None

        self._anim_gen += 1
        my_gen = self._anim_gen

        anim = QPropertyAnimation(item, b"pos", item)
        anim.setDuration(ANIM_MOVE_MS)
        anim.setStartValue(item.pos())
        anim.setEndValue(end_top_left)
        anim.setEasingCurve(Curves.PIECE)
        item.setZValue(self.Z_DRAG)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(10)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(0, 0, 0, 150))
        item.setGraphicsEffect(shadow)

        def on_finished():
            try:
                item.setZValue(self.Z_PIECE)
                item.setGraphicsEffect(None)
            except RuntimeError:
                pass
            if self._anim_gen == my_gen:
                self._anim = None

        anim.finished.connect(on_finished)
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
        self._anim = anim

    # ═════════════════════════════════════════════════════════════════════
    #  PUBLIC API
    # ═════════════════════════════════════════════════════════════════════
    def set_position(self, fen: str,
                     from_sq: Optional[int] = None,
                     to_sq:   Optional[int] = None,
                     best:    Optional[chess.Move] = None,
                     cls:     Optional[str] = None) -> None:
        """Display a position. Animates the moved piece if from/to given.

        `cls` is the move's classification ("brilliant", "best", "good",
        "inaccuracy", "mistake", "blunder") which drives the destination
        square tint — chess.com style.
        """
        # Stop any in-flight piece animation and snap the piece to its
        # destination before starting a new one. Without this, rapid
        # navigation leaves animations referencing stale piece state → crash.
        if self._anim is not None:
            try:
                end_pos = self._anim.endValue()
                animated_item = self._anim.parent()
                self._anim.stop()
                if end_pos is not None and animated_item is not None:
                    try:
                        animated_item.setPos(end_pos)
                        animated_item.setZValue(self.Z_PIECE)
                        animated_item.setGraphicsEffect(None)
                    except RuntimeError:
                        pass
            except RuntimeError:
                pass
            self._anim = None

        # Clear user drawings — chess.com behavior: moving clears them
        self.clear_user_drawings()

        prev_board = self._board.copy()
        self._board.set_fen(fen)
        self._hl_from = from_sq
        self._hl_to   = to_sq
        self._hl_cls  = cls
        self._recolor_squares()

        # Animation: detect if moved_from has the same color piece as moved_to
        # in the prev_board (i.e. a real move happened from from_sq to to_sq).
        can_animate = (
            from_sq is not None and to_sq is not None
            and prev_board.piece_at(from_sq) is not None
            and self._board.piece_at(to_sq) is not None
        )

        if can_animate:
            self._sync_pieces(animate=True, moved_from=from_sq, moved_to=to_sq)
        else:
            self._sync_pieces(animate=False)

        # Engine best-move arrow
        self.set_best_arrow(best)

    # ═════════════════════════════════════════════════════════════════════
    #  KNIGHT-MOVE DETECTION FOR L-SHAPED ARROWS
    # ═════════════════════════════════════════════════════════════════════
    @staticmethod
    def _is_knight_move(from_sq: int, to_sq: int) -> bool:
        df = abs(chess.square_file(from_sq) - chess.square_file(to_sq))
        dr = abs(chess.square_rank(from_sq) - chess.square_rank(to_sq))
        return {df, dr} == {1, 2}

    def _knight_corner(self, from_sq: int, to_sq: int) -> QPointF:
        """Return the scene-coordinate corner for an L-shaped knight arrow.
        Goes along the LONGER axis first (the '2' in the 1-2 split)."""
        f1, r1 = chess.square_file(from_sq), chess.square_rank(from_sq)
        f2, r2 = chess.square_file(to_sq),   chess.square_rank(to_sq)
        df, dr = abs(f1 - f2), abs(r1 - r2)
        if dr > df:
            # Rank is the long axis → travel vertical first, then horizontal
            corner_sq = chess.square(f1, r2)
        else:
            # File is the long axis → travel horizontal first, then vertical
            corner_sq = chess.square(f2, r1)
        return self.square_center(corner_sq)

    def set_best_arrow(self, move: Optional[chess.Move]) -> None:
        if self._best_arrow is not None:
            self.removeItem(self._best_arrow)
            self._best_arrow = None
        self._best_move = move
        if move is None:
            return
        corner = None
        if self._is_knight_move(move.from_square, move.to_square):
            corner = self._knight_corner(move.from_square, move.to_square)
        a = ArrowItem(self.square_center(move.from_square),
                      self.square_center(move.to_square),
                      self._sq_px, color=COLORS.arrow_best,
                      opacity=0.78, above_pieces=False,
                      corner=corner)
        # Soft green outer glow — offset (0,0) creates a symmetric halo
        glow = QGraphicsDropShadowEffect()
        glow.setBlurRadius(14)
        glow.setOffset(0, 0)
        glow_color = QColor(COLORS.arrow_best)
        glow_color.setAlpha(110)
        glow.setColor(glow_color)
        a.setGraphicsEffect(glow)
        a.setZValue(self.Z_BEST_ARROW)
        self.addItem(a)
        self._best_arrow = a

    def set_hover_square(self, sq: Optional[int]) -> None:
        """Update the hovered square (for subtle hover highlight). Called by the view."""
        if sq == self._hover_sq:
            return
        old = self._hover_sq
        self._hover_sq = sq
        for changed in (old, sq):
            if changed is not None and changed in self._sq_items:
                self._sq_items[changed].setBrush(self._brush_for_square(changed))

    def flip(self) -> None:
        self._flipped = not self._flipped
        # CRITICAL: reposition each square rectangle to its new pixel
        # location. Without this, highlights (the yellow "from" and the
        # classification-tinted "to" squares) appear at the un-flipped
        # positions — a mirror-image of where the actual move happened.
        # The pieces themselves DO get repositioned below, so without this
        # fix the highlight and the piece end up on opposite sides of the
        # board.
        for sq, rect in self._sq_items.items():
            tl = self.square_top_left(sq)
            rect.setRect(tl.x(), tl.y(), self._sq_px, self._sq_px)
        self._recolor_squares()
        self._rebuild_coords()
        # Reposition every piece
        for sq, item in self._piece_items.items():
            item.setPos(self.square_top_left(sq))
        # Rebuild best-move arrow if we have one
        saved_best = self._best_move
        if self._best_arrow is not None:
            self.removeItem(self._best_arrow)
            self._best_arrow = None
        if saved_best is not None:
            self.set_best_arrow(saved_best)
        # User drawings cleared on flip (chess.com behavior)
        self.clear_user_drawings()
        # Emit so the host can swap player labels
        self.flipped_changed.emit(self._flipped)

    @property
    def is_flipped(self) -> bool:
        return self._flipped

    def reset(self) -> None:
        self._board = chess.Board()
        self._hl_from = self._hl_to = None
        self._recolor_squares()
        self.clear_user_drawings()
        self.set_best_arrow(None)
        self._sync_pieces(animate=False)

    # ═════════════════════════════════════════════════════════════════════
    #  USER DRAWING
    # ═════════════════════════════════════════════════════════════════════
    def toggle_user_arrow(self, from_sq: int, to_sq: int) -> None:
        key = (from_sq, to_sq)
        if key in self._user_arrows:
            self.removeItem(self._user_arrows.pop(key))
            return
        corner = None
        if self._is_knight_move(from_sq, to_sq):
            corner = self._knight_corner(from_sq, to_sq)
        a = ArrowItem(self.square_center(from_sq),
                      self.square_center(to_sq),
                      self._sq_px, color=COLORS.arrow_user, opacity=0.88,
                      above_pieces=True,
                      corner=corner)
        self.addItem(a)
        self._user_arrows[key] = a

    def toggle_user_circle(self, sq: int) -> None:
        if sq in self._user_circles:
            self.removeItem(self._user_circles.pop(sq))
            return
        c = CircleItem(self.square_center(sq), self._sq_px,
                       color=COLORS.arrow_user, opacity=0.88)
        self.addItem(c)
        self._user_circles[sq] = c

    def erase_at_square(self, sq: int) -> bool:
        """Remove any user drawing touching this square. Returns True if anything was removed."""
        removed = False
        if sq in self._user_circles:
            self.removeItem(self._user_circles.pop(sq))
            removed = True
        keys_to_remove = [k for k in self._user_arrows if sq in k]
        for key in keys_to_remove:
            self.removeItem(self._user_arrows.pop(key))
            removed = True
        return removed

    def clear_user_drawings(self) -> None:
        for a in self._user_arrows.values():
            self.removeItem(a)
        self._user_arrows.clear()
        for c in self._user_circles.values():
            self.removeItem(c)
        self._user_circles.clear()
        self.clear_drag_preview()

    # ── Live arrow preview during right-click drag ─────────────────────────
    def show_drag_preview(self, from_sq: int, scene_point: QPointF) -> None:
        center = self.square_center(from_sq)
        if self._drag_arrow is None:
            self._drag_arrow = ArrowItem(center, scene_point,
                                         self._sq_px, color=COLORS.arrow_user,
                                         opacity=0.55, above_pieces=True)
            self._drag_arrow.setZValue(self.Z_DRAG)
            self.addItem(self._drag_arrow)
        else:
            self._drag_arrow.update_endpoints(center, scene_point)

    def clear_drag_preview(self) -> None:
        if self._drag_arrow is not None:
            self.removeItem(self._drag_arrow)
            self._drag_arrow = None


# Monkey-patch convenience for piece-symbol tracking
def _piece_symbol(self) -> str:
    return getattr(self, "_piece_symbol", "")
PieceItem.piece_symbol = _piece_symbol  # type: ignore[attr-defined]
