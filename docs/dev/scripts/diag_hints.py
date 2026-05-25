"""Check sizeHint, minimumSizeHint, and minimumSize for board-area widgets."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QTimer
from app.application import create_application
from app.ui.main_window import MainWindow

app = create_application(sys.argv)
window = MainWindow()
window.showMaximized()

def _report():
    c = window.center
    b = c.board
    ev = c.eval_bar
    wrap = b.parent()
    outer = c.layout()

    def hint_info(name, w):
        sh = w.sizeHint()
        msh = w.minimumSizeHint()
        ms = w.minimumSize()
        xs = w.maximumSize()
        print(f"{name}: actual={w.width()}x{w.height()}  hint={sh.width()}x{sh.height()}  "
              f"minHint={msh.width()}x{msh.height()}  minSize={ms.width()}x{ms.height()}")

    hint_info("CenterArea ", c)
    hint_info("WrapWidget ", wrap)
    hint_info("EvalBar    ", ev)
    hint_info("BoardView  ", b)

    # Also check the board_row layout
    board_row = wrap.layout()
    if board_row:
        bsh = board_row.sizeHint()
        bmsh = board_row.minimumSize()
        print(f"board_row layout: hint={bsh.width()}x{bsh.height()}  minSize={bmsh.width()}x{bmsh.height()}")

    print(f"\nOuter VBox item count: {outer.count()}")
    for i in range(outer.count()):
        item = outer.itemAt(i)
        w = item.widget()
        if w:
            sh = item.sizeHint()
            ms = item.minimumSize()
            print(f"  item[{i}] {w.__class__.__name__}: cell sizeHint={sh.width()}x{sh.height()}  "
                  f"minSize={ms.width()}x{ms.height()}  alignment={int(item.alignment())}")

    app.quit()

QTimer.singleShot(2500, _report)
sys.exit(app.exec())
