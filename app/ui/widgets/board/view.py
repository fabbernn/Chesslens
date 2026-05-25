"""
BoardView — the QGraphicsView that hosts a BoardScene.

Responsibilities:
  * own the BoardScene
  * route mouse events into chess-square coordinates
  * implement chess.com-style right-click drawing:
      - press-and-drag → live arrow preview
      - release on different square → commit arrow (toggle)
      - release on same square (no drag) → commit circle, OR erase
        anything that already touches that square
  * left-click anywhere clears all user drawings
  * forwards keyboard arrows to the parent for move navigation
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent, QPainter, QResizeEvent
from PySide6.QtWidgets import QGraphicsView, QSizePolicy

from app.config import BOARD_PX
from app.ui.widgets.board.scene import BoardScene


class BoardView(QGraphicsView):
    """The widget that's actually placed in the main window."""

    # Forwarded keyboard signals (let the main window decide what to do)
    prev_move_requested = Signal()
    next_move_requested = Signal()
    first_move_requested = Signal()
    last_move_requested  = Signal()
    # Re-emitted from the scene so the parent doesn't need to know about it
    flipped_changed = Signal(bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._board_scene = BoardScene(self)
        self.setScene(self._board_scene)
        # Forward flip changes upward
        self._board_scene.flipped_changed.connect(self.flipped_changed.emit)

        # Rendering quality
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
            | QPainter.RenderHint.TextAntialiasing
        )
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.setFixedSize(BOARD_PX, BOARD_PX)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)
        # Crisp piece rendering — no fractional anchor
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        # Accept keyboard focus so arrow keys work
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Drag state for right-click drawing
        self._rclick_start_sq: int | None = None
        self._drag_active: bool = False

    # ─────────────────────────────────────────────────────────────────────
    @property
    def scene_(self) -> BoardScene:
        """Typed accessor for the BoardScene (avoids QGraphicsView.scene name clash)."""
        return self._board_scene

    # ═════════════════════════════════════════════════════════════════════
    #  MOUSE — drawing system
    # ═════════════════════════════════════════════════════════════════════
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            sp = self.mapToScene(event.position().toPoint())
            sq = self._board_scene.square_at_scene_pos(sp)
            self._rclick_start_sq = sq
            self._drag_active = False
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            # Left-click anywhere clears user drawings (chess.com behavior)
            self._board_scene.clear_user_drawings()
            super().mousePressEvent(event)
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        sp = self.mapToScene(event.position().toPoint())
        if (self._rclick_start_sq is not None
                and event.buttons() & Qt.MouseButton.RightButton):
            cur_sq = self._board_scene.square_at_scene_pos(sp)
            if cur_sq is not None and cur_sq != self._rclick_start_sq:
                self._drag_active = True
            event.accept()
            return
        self._board_scene.set_hover_square(self._board_scene.square_at_scene_pos(sp))
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:
        self._board_scene.set_hover_square(None)
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            start = self._rclick_start_sq
            self._rclick_start_sq = None
            self._board_scene.clear_drag_preview()
            if start is None:
                event.accept()
                return

            sp = self.mapToScene(event.position().toPoint())
            end = self._board_scene.square_at_scene_pos(sp)
            if end is None:
                self._drag_active = False
                event.accept()
                return

            if end == start:
                # Single right-click — erase any drawing on the square,
                # OR add a circle if nothing was there
                if not self._board_scene.erase_at_square(end):
                    self._board_scene.toggle_user_circle(end)
            else:
                # Drag — commit arrow (toggle)
                self._board_scene.toggle_user_arrow(start, end)

            self._drag_active = False
            event.accept()
            return

        super().mouseReleaseEvent(event)

    # ═════════════════════════════════════════════════════════════════════
    #  KEYBOARD — move navigation
    # ═════════════════════════════════════════════════════════════════════
    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key == Qt.Key.Key_Left:
            self.prev_move_requested.emit()
        elif key == Qt.Key.Key_Right:
            self.next_move_requested.emit()
        elif key == Qt.Key.Key_Home:
            self.first_move_requested.emit()
        elif key == Qt.Key.Key_End:
            self.last_move_requested.emit()
        elif key == Qt.Key.Key_Escape:
            self._board_scene.clear_user_drawings()
        else:
            super().keyPressEvent(event)
            return
        event.accept()

    # ═════════════════════════════════════════════════════════════════════
    #  PASSTHROUGH API
    # ═════════════════════════════════════════════════════════════════════
    def set_position(self, *args, **kwargs):
        self._board_scene.set_position(*args, **kwargs)

    def flip(self) -> None:
        self._board_scene.flip()

    def reset(self) -> None:
        self._board_scene.reset()

    def set_best_arrow(self, move) -> None:
        self._board_scene.set_best_arrow(move)

    def set_square_colors(self, dark_hex: str, light_hex: str) -> None:
        self._board_scene.set_square_colors(dark_hex, light_hex)

    def set_piece_set(self, name: str) -> None:
        self._board_scene.set_piece_set(name)
