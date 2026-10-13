"""Interactive screen region selection overlay across all monitors."""

from __future__ import annotations

import logging
from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QKeyEvent, QMouseEvent, QPaintEvent, QPainter, QPen, QScreen
from PySide6.QtWidgets import QApplication, QWidget

from screen_translator.models import Region
from screen_translator.utils.coords import local_to_native

logger = logging.getLogger(__name__)


class _ScreenSelectorWindow(QWidget):
    """Full-screen translucent canvas for drag-selecting a rectangular region on one QScreen."""

    def __init__(
        self,
        screen: QScreen,
        on_selected,
        on_cancelled,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.screen_ref = screen
        self.on_selected = on_selected
        self.on_cancelled = on_cancelled

        self._start_pos: QPoint | None = None
        self._curr_pos: QPoint | None = None
        self._is_dragging = False

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setCursor(Qt.CrossCursor)

        self.setScreen(screen)
        self.setGeometry(screen.geometry())

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self._start_pos = event.position().toPoint()
            self._curr_pos = self._start_pos
            self._is_dragging = True
            self.update()
        elif event.button() == Qt.RightButton:
            self.on_cancelled()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._is_dragging:
            self._curr_pos = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton and self._is_dragging:
            self._is_dragging = False
            if self._start_pos and self._curr_pos:
                l = min(self._start_pos.x(), self._curr_pos.x())
                t = min(self._start_pos.y(), self._curr_pos.y())
                r = max(self._start_pos.x(), self._curr_pos.x())
                b = max(self._start_pos.y(), self._curr_pos.y())
                w, h = r - l, b - t

                if w >= 50 and h >= 30:
                    dpr = self.screen_ref.devicePixelRatio()
                    geom = self.screen_ref.geometry()
                    origin = (int(round(geom.x() * dpr)), int(round(geom.y() * dpr)))

                    native_l, native_t, native_r, native_b = local_to_native((l, t, r, b), origin, dpr)
                    region = Region(native_l, native_t, native_r - native_l, native_b - native_t)
                    self.on_selected(region)
                    return

            self.on_cancelled()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key_Escape:
            self.on_cancelled()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 1. Dim the whole screen (alpha ~0.3)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 75))

        if self._is_dragging and self._start_pos and self._curr_pos:
            l = min(self._start_pos.x(), self._curr_pos.x())
            t = min(self._start_pos.y(), self._curr_pos.y())
            r = max(self._start_pos.x(), self._curr_pos.x())
            b = max(self._start_pos.y(), self._curr_pos.y())
            sel_rect = QRect(l, t, r - l, b - t)

            # 2. Punch clear hole in the dim layer for the selection
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            painter.fillRect(sel_rect, Qt.transparent)
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)

            # 3. Draw bright green border
            painter.setPen(QPen(QColor(0, 255, 0), 2))
            painter.drawRect(sel_rect)

            # 4. Draw live dimension badge (W x H)
            dim_text = f"{sel_rect.width()} × {sel_rect.height()}"
            badge_font = QFont("Segoe UI", 10, QFont.Bold)
            painter.setFont(badge_font)

            badge_w = 90
            badge_h = 24
            badge_x = sel_rect.right() - badge_w if sel_rect.right() + badge_w <= self.width() else sel_rect.left()
            badge_y = sel_rect.bottom() + 6 if sel_rect.bottom() + badge_h + 10 <= self.height() else sel_rect.top() - badge_h - 6
            badge_rect = QRect(badge_x, badge_y, badge_w, badge_h)

            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0, 0, 0, 180))
            painter.drawRoundedRect(badge_rect, 4, 4)

            painter.setPen(QColor(255, 255, 255))
            painter.drawText(badge_rect, Qt.AlignCenter, dim_text)

        painter.end()


class RegionSelector(QWidget):
    """Coordinates multi-monitor dimming overlays and emits region selection signals."""

    region_selected = Signal(object)  # Emits Region
    cancelled = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._windows: list[_ScreenSelectorWindow] = []

    def start_selection(self) -> None:
        """Dim all connected screens and prompt user for rectangular region drag."""
        self._close_all()
        app = QApplication.instance()
        screens = app.screens() if app else []

        if not screens:
            self.cancelled.emit()
            return

        def handle_selected(region: Region) -> None:
            self._close_all()
            logger.info("Region selected: %s", region)
            self.region_selected.emit(region)

        def handle_cancelled() -> None:
            self._close_all()
            logger.info("Region selection cancelled")
            self.cancelled.emit()

        for screen in screens:
            win = _ScreenSelectorWindow(screen, on_selected=handle_selected, on_cancelled=handle_cancelled)
            self._windows.append(win)
            win.show()

        # Give focus to active screen selector window
        if self._windows:
            self._windows[0].activateWindow()

    def _close_all(self) -> None:
        for win in self._windows:
            win.close()
        self._windows.clear()
