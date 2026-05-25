"""
ChessLens — entry point.

Usage:
    python main.py
"""

from __future__ import annotations
import sys

from app.application import create_application
from app.ui.main_window import MainWindow


def main() -> int:
    app = create_application(sys.argv)
    window = MainWindow()
    # Open maximized so you get the whole screen without window chrome
    # taking up review space. F11 inside the app toggles true fullscreen.
    window.showMaximized()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
