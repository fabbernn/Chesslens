"""Launch ChessLens, wait 4s, screenshot it, then quit."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QTimer
from PySide6.QtGui import QScreen
from PySide6.QtWidgets import QApplication
from app.application import create_application
from app.ui.main_window import MainWindow

app = create_application(sys.argv)
window = MainWindow()
window.showMaximized()

def _snap():
    screen = QApplication.primaryScreen()
    pixmap = screen.grabWindow(window.winId())
    out = os.path.join(os.environ.get("TEMP", "."), "chesslens_snap.png")
    pixmap.save(out, "PNG")
    print(f"Saved {pixmap.width()}x{pixmap.height()} to {out}")
    app.quit()

QTimer.singleShot(4000, _snap)
sys.exit(app.exec())
