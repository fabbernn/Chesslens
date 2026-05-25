"""Print actual positions and sizes of board and surrounding widgets."""
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

    def win_pos(name, w):
        p = w.mapTo(window, w.rect().topLeft())
        br = w.mapTo(window, w.rect().bottomRight())
        print(f"{name}: window_y={p.y()} to {br.y()}  size={w.width()}x{w.height()}")

    win_pos("top_label   ", c.top_label)
    win_pos("WrapWidget  ", wrap)
    win_pos("BoardView   ", b)
    win_pos("bottom_label", c.bottom_label)
    print(f"Window height: {window.height()}")
    print(f"CenterArea height: {c.height()}")

    app.quit()

QTimer.singleShot(2500, _report)
sys.exit(app.exec())
