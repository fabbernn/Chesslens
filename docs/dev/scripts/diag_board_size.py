"""Diagnostic: board widget dimensions, viewport, transform, scroll at startup."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QTimer
from app.application import create_application
from app.ui.main_window import MainWindow

app = create_application(sys.argv)
window = MainWindow()
window.showMaximized()

def _report():
    center = window.center
    board  = center.board
    vp     = board.viewport()
    scene  = board.scene_

    print(f"BoardView.size()          = {board.width()} x {board.height()}")
    print(f"BoardView.viewport.size() = {vp.width()} x {vp.height()}")
    print(f"BoardScene.sceneRect()    = {scene.sceneRect()}")
    print(f"BoardView.devicePixelRatio = {board.devicePixelRatio()}")
    print(f"CenterArea.size()         = {center.width()} x {center.height()}")

    tr = board.transform()
    print(f"BoardView.transform()     = [{tr.m11():.4f}, {tr.m12():.4f}; {tr.m21():.4f}, {tr.m22():.4f}]")

    vsb = board.verticalScrollBar()
    hsb = board.horizontalScrollBar()
    print(f"VScrollBar: value={vsb.value()} min={vsb.minimum()} max={vsb.maximum()}")
    print(f"HScrollBar: value={hsb.value()} min={hsb.minimum()} max={hsb.maximum()}")

    # Map top-left and bottom-right of scene to viewport coords
    tl = board.mapFromScene(0, 0)
    br = board.mapFromScene(512, 512)
    print(f"Scene (0,0) -> viewport  = ({tl.x()}, {tl.y()})")
    print(f"Scene (512,512) -> vport = ({br.x()}, {br.y()})")

    # Check visible scene rect
    vr = board.mapToScene(board.viewport().rect()).boundingRect()
    print(f"Visible scene rect       = {vr}")

    app.quit()

QTimer.singleShot(2000, _report)
sys.exit(app.exec())
