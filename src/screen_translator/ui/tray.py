"""System tray icon and context menu."""

from __future__ import annotations

import logging
import time

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QAction, QBrush, QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from screen_translator import __version__
from screen_translator.models import Region

logger = logging.getLogger(__name__)


def _create_tray_icon(is_running: bool) -> QIcon:
    """Generate dynamic rounded square tray icon with 'T' glyph using QPainter."""
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    bg_color = QColor(46, 204, 113) if is_running else QColor(127, 140, 141)
    painter.setBrush(QBrush(bg_color))
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(2, 2, 28, 28, 6, 6)

    font = QFont("Segoe UI", 16, QFont.Bold)
    painter.setFont(font)
    painter.setPen(QPen(QColor(255, 255, 255)))
    painter.drawText(pixmap.rect(), Qt.AlignCenter, "T")
    painter.end()

    return QIcon(pixmap)


class TrayIcon(QSystemTrayIcon):
    """System tray icon providing dynamic status, context menu, and throttled notifications."""

    toggle_requested = Signal()
    select_region_requested = Signal()
    full_screen_requested = Signal()
    quit_requested = Signal()

    def __init__(
        self,
        toggle_key_hint: str = "Ctrl+Alt+T",
        select_key_hint: str = "Ctrl+Alt+R",
        quit_key_hint: str = "Ctrl+Alt+Q",
        parent: QObject | None = None,
    ) -> None:
        """Initialize tray icon, context menu actions, and activation listener."""
        super().__init__(parent)
        self.toggle_key_hint = toggle_key_hint
        self.select_key_hint = select_key_hint
        self.quit_key_hint = quit_key_hint

        self._is_running = True
        self._current_region: Region | None = None
        self._last_notifications: dict[str, float] = {}

        self.setIcon(_create_tray_icon(self._is_running))
        self._init_menu()

        self.activated.connect(self._on_activated)

    def _init_menu(self) -> None:
        menu = QMenu()

        self._toggle_action = QAction(f"Pause ({self.toggle_key_hint})", self)
        self._toggle_action.triggered.connect(self.toggle_requested.emit)
        menu.addAction(self._toggle_action)

        self._select_action = QAction(f"Select region... ({self.select_key_hint})", self)
        self._select_action.triggered.connect(self.select_region_requested.emit)
        menu.addAction(self._select_action)

        self._fullscreen_action = QAction("Full screen", self)
        self._fullscreen_action.triggered.connect(self.full_screen_requested.emit)
        menu.addAction(self._fullscreen_action)

        menu.addSeparator()

        self._quit_action = QAction(f"Quit ({self.quit_key_hint})", self)
        self._quit_action.triggered.connect(self.quit_requested.emit)
        menu.addAction(self._quit_action)

        self.setContextMenu(menu)
        self.update_state(is_running=True, region=None)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """Handle tray click activations (left-click toggles Pause/Start)."""
        if reason == QSystemTrayIcon.Trigger:
            logger.debug("Tray icon left-clicked -> toggle requested")
            self.toggle_requested.emit()

    def update_state(self, is_running: bool, region: Region | None = None) -> None:
        """Update icon appearance, menu labels, and tooltip."""
        self._is_running = is_running
        self._current_region = region

        self.setIcon(_create_tray_icon(is_running))
        toggle_label = f"Pause ({self.toggle_key_hint})" if is_running else f"Start ({self.toggle_key_hint})"
        self._toggle_action.setText(toggle_label)

        status_text = "Running" if is_running else "Paused"
        if region is not None:
            region_text = f"Region: {region.width}×{region.height} @ ({region.left},{region.top})"
        else:
            region_text = "Full Screen"

        self.setToolTip(f"Screen Translator v{__version__} - {status_text}\n{region_text}")

    def notify(self, title: str, message: str) -> None:
        """Display system balloon notification throttled to 1 per 30 seconds per message."""
        now = time.monotonic()
        last_sent = self._last_notifications.get(message, 0.0)
        if now - last_sent < 30.0:
            logger.debug("Suppressing throttled tray notification: %s", message)
            return

        self._last_notifications[message] = now
        self.showMessage(title, message, QSystemTrayIcon.Warning, 5000)
