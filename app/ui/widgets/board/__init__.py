"""Board widget package — public exports."""

from app.ui.widgets.board.view import BoardView
from app.ui.widgets.board.scene import BoardScene
from app.ui.widgets.board.renderer import PieceRenderer

__all__ = ["BoardView", "BoardScene", "PieceRenderer"]
