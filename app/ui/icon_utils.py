"""SVG icon rendering helpers — tint and size any Feather/custom SVG."""

from __future__ import annotations
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer


def svg_pixmap(path: str | Path, size: int, color_hex: str) -> QPixmap:
    """Render an SVG at `size`×`size` px, tinted uniformly to `color_hex`."""
    renderer = QSvgRenderer(str(path))
    img = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    renderer.render(p)
    p.end()

    tinted = QImage(img.size(), QImage.Format.Format_ARGB32_Premultiplied)
    tinted.fill(Qt.GlobalColor.transparent)
    p2 = QPainter(tinted)
    p2.fillRect(tinted.rect(), QColor(color_hex))
    p2.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
    p2.drawImage(0, 0, img)
    p2.end()

    return QPixmap.fromImage(tinted)


def svg_icon(path: str | Path, size: int, color_hex: str) -> QIcon:
    """Return a QIcon from an SVG file, tinted to `color_hex`."""
    return QIcon(svg_pixmap(path, size, color_hex))
