"""
Utility: launch ChessLens, wait for it to render, screenshot it, then quit.
Usage:
    python docs/screenshots/take_screenshot.py <output_path>
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from app.application import create_application
from app.ui.main_window import MainWindow

from PySide6.QtCore import QTimer
from PySide6.QtGui import QScreen
from PySide6.QtWidgets import QApplication


def main():
    output = sys.argv[1] if len(sys.argv) > 1 else "screenshot.png"
    os.makedirs(os.path.dirname(output) or ".", exist_ok=True)

    app = create_application(sys.argv[:1])
    window = MainWindow()
    window.showMaximized()

    def capture():
        screen = QApplication.primaryScreen()
        pixmap = screen.grabWindow(int(window.winId()))
        pixmap.save(output, "PNG")
        print(f"Saved: {output}")
        app.quit()

    # Give the window time to fully render before capturing
    QTimer.singleShot(2500, capture)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
