"""
Application bootstrap — QApplication setup, theming, fonts, metadata.

The main.py entry point calls create_application() and gets a fully-themed
QApplication ready to show a main window.
"""

from __future__ import annotations
import sys
import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase, QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication

from app.config import APP_NAME, APP_VERSION, APP_VENDOR, APP_ID, FONTS_DIR, RESOURCE_DIR
from app.ui.theme import build_global_qss, FONTS


def _load_bundled_fonts() -> None:
    """Load any TTF/OTF files in app/resources/fonts/ into Qt's font db."""
    if not FONTS_DIR.exists():
        return
    for path in FONTS_DIR.glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(path))
    for path in FONTS_DIR.glob("*.otf"):
        QFontDatabase.addApplicationFont(str(path))


def _pick_default_font() -> QFont:
    """Pick the best available UI font for this OS."""
    candidates = ["Segoe UI Variable", "Segoe UI", "Inter", "SF Pro Text", "Helvetica"]
    available = set(QFontDatabase.families())
    for name in candidates:
        if name in available:
            font = QFont(name)
            font.setPointSize(FONTS.md)
            # Subpixel rendering — important for small UI text
            font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
            return font
    return QFont()


def create_application(argv: list[str] | None = None) -> QApplication:
    if argv is None:
        argv = sys.argv

    # ── High-DPI ───────────────────────────────────────────────────────────
    # PySide6 6+ enables high-DPI by default but the scale factor policy
    # matters for fractional scales (125%, 150%).
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    # On Windows, set the AppUserModelID so taskbar grouping / icon works
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        except Exception:
            pass

    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(APP_VENDOR)
    app.setOrganizationDomain("chesslens.app")

    # ── App icon (window + taskbar) ────────────────────────────────────────
    icon_ico = RESOURCE_DIR / "icon" / "chesslens.ico"
    icon_png = RESOURCE_DIR / "icon" / "chesslens.png"
    if icon_ico.exists():
        app.setWindowIcon(QIcon(str(icon_ico)))
    elif icon_png.exists():
        app.setWindowIcon(QIcon(str(icon_png)))

    # ── Fonts ──────────────────────────────────────────────────────────────
    _load_bundled_fonts()
    app.setFont(_pick_default_font())

    # ── Theme ──────────────────────────────────────────────────────────────
    # Use Fusion style as the base — it's the most stylesheet-friendly Qt
    # style and looks consistent cross-platform.
    app.setStyle("Fusion")
    app.setStyleSheet(build_global_qss())

    return app
