"""Render application icons (assets/app.ico and assets/app.png) using PySide6."""

from __future__ import annotations

from pathlib import Path
import sys

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QGuiApplication, QImage, QPainter, QPen


def generate_icon(output_dir: Path | None = None) -> Path:
    """Generate 256x256 app.ico icon using QPainter without Pillow.

    Args:
        output_dir: Directory where app.ico will be saved (defaults to assets/).

    Returns:
        Path: Path to the generated app.ico file.
    """
    app = QGuiApplication.instance()
    if app is None:
        app = QGuiApplication(sys.argv)

    target_dir = output_dir or (Path(__file__).resolve().parent.parent / "assets")
    target_dir.mkdir(parents=True, exist_ok=True)
    ico_path = target_dir / "app.ico"
    png_path = target_dir / "app.png"

    size = 256
    image = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.TextAntialiasing)

    # 1. Vibrant rounded square container
    bg_color = QColor(46, 204, 113)  # Emerald Green
    painter.setBrush(QBrush(bg_color))
    painter.setPen(Qt.NoPen)
    margin = 16
    rect_size = size - (margin * 2)
    radius = 48
    painter.drawRoundedRect(margin, margin, rect_size, rect_size, radius, radius)

    # 2. Centered bold white "T" glyph
    font = QFont("Segoe UI", 128, QFont.Bold)
    painter.setFont(font)
    painter.setPen(QPen(QColor(255, 255, 255)))

    # Slight vertical adjustment for visual balance
    text_rect = QRect(0, -6, size, size)
    painter.drawText(text_rect, Qt.AlignCenter, "T")
    painter.end()

    # Save both ICO and PNG formats
    image.save(str(ico_path), "ICO")
    image.save(str(png_path), "PNG")
    print(f"Generated application icon at {ico_path} (and {png_path})")
    return ico_path


if __name__ == "__main__":
    generate_icon()
