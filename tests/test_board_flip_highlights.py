"""
Regression tests for the BoardScene flip behavior.

Pins the bug where flipping the board left highlight-square rectangles
at their original (un-flipped) pixel positions while the pieces moved
correctly. The result was last-move highlights appearing on the mirror-
image squares — extremely confusing for anyone playing black.

If this test fails, the fix in BoardScene.flip() that re-sets each
rect's geometry has regressed. Don't paper over it — re-do the rect
repositioning.
"""

import pytest
import chess

# Skip the whole file if PySide6 isn't available (e.g. CI without Qt)
pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.ui.widgets.board.scene import BoardScene  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    """Single QApplication for the whole test module."""
    app = QApplication.instance() or QApplication([])
    yield app


def _rect_pos(scene: BoardScene, sq: int) -> tuple[float, float]:
    """Pixel top-left of the QGraphicsRectItem currently representing `sq`."""
    rect_item = scene._sq_items[sq]
    r = rect_item.rect()
    return (r.x(), r.y())


def test_flip_repositions_rects_to_match_pieces(qapp):
    """After flip(), the rect for square G7 must sit at the same pixel
    coordinates as the G7 piece — otherwise highlights paint at the
    mirror position relative to the moved piece.
    """
    scene = BoardScene()
    # G7 piece exists in the starting position
    expected_pos_unflipped = scene.square_top_left(chess.G7)
    actual_rect_pos = _rect_pos(scene, chess.G7)
    assert actual_rect_pos == (expected_pos_unflipped.x(),
                               expected_pos_unflipped.y()), \
        "Sanity: rect for G7 must match square_top_left in unflipped state"

    scene.flip()

    # After flip, square_top_left returns the new (mirrored) coords
    expected_pos_flipped = scene.square_top_left(chess.G7)
    actual_rect_pos = _rect_pos(scene, chess.G7)
    assert actual_rect_pos == (expected_pos_flipped.x(),
                               expected_pos_flipped.y()), (
        f"flip() did NOT reposition the G7 rect. "
        f"Expected {(expected_pos_flipped.x(), expected_pos_flipped.y())}, "
        f"got {actual_rect_pos}. This causes highlights to appear at "
        f"mirror-image squares on flipped boards."
    )


def test_flip_is_idempotent_in_pairs(qapp):
    """Flipping twice should restore the original geometry exactly."""
    scene = BoardScene()
    original = {sq: _rect_pos(scene, sq) for sq in chess.SQUARES}
    scene.flip()
    scene.flip()
    after_two = {sq: _rect_pos(scene, sq) for sq in chess.SQUARES}
    assert original == after_two, \
        "Two consecutive flips should leave the board geometry unchanged"


def test_highlights_track_pieces_after_flip(qapp):
    """The square a piece is rendered ON must also be the square whose
    rect gets highlighted. After flip, both must use the same pixel
    coordinates. Tests the actual user-visible bug.
    """
    scene = BoardScene()
    scene.flip()

    # G7 has a piece in the start position. Its rect AND piece must
    # share the same top-left after flip.
    if chess.G7 not in scene._piece_items:
        pytest.skip("G7 has no piece item in this scene state")

    piece_pos = scene._piece_items[chess.G7].pos()
    rect_pos  = _rect_pos(scene, chess.G7)
    assert (piece_pos.x(), piece_pos.y()) == rect_pos, (
        f"Piece on G7 is rendered at {piece_pos.x(), piece_pos.y()} but "
        f"its highlight rect is at {rect_pos}. A 'from' highlight on G7 "
        f"would appear at the wrong visual location."
    )
