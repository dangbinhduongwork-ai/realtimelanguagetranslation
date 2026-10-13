"""System tray icon and context menu."""

from __future__ import annotations

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QSystemTrayIcon


class TrayIcon(QSystemTrayIcon):
    """System tray icon providing menu options: Start/Pause, Select region, Full screen, Quit."""

    def __init__(self, parent: QObject | None = None) -> None:
        """Initialize system tray icon and attach context menu actions.

        Args:
            parent: Optional parent QObject.
        """
        super().__init__(parent)
        raise NotImplementedError("TrayIcon is scheduled for Stage 4")
