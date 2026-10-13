"""Transparent, click-through, always-on-top overlay window."""

from __future__ import annotations

import logging

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetrics, QPaintEvent, QPainter, QPen, QScreen, QShowEvent
from PySide6.QtWidgets import QWidget

from screen_translator.models import Region, TranslatedBlock
from screen_translator.utils.coords import native_to_local
from screen_translator.utils.win_utils import exclude_window_from_capture, make_click_through

logger = logging.getLogger(__name__)


class OverlayWindow(QWidget):
    """Transparent overlay rendering translated text blocks directly above source text."""

    def __init__(
        self,
        font_family: str = "Segoe UI",
        font_size: int = 14,
        opacity: float = 0.9,
        background_color: str = "#000000",
        text_color: str = "#FFFFFF",
        show_region_border: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize overlay window visual styling and window flags."""
        super().__init__(parent)
        self.font_family = font_family
        self.default_font_size = font_size
        self.opacity = float(opacity)
        self.background_color = background_color
        self.text_color = text_color
        self.show_region_border = show_region_border

        self._blocks: list[TranslatedBlock] = []
        self._active_region: Region | None = None
        self._target_screen: QScreen | None = None
        self._screen_origin: tuple[int, int] = (0, 0)
        self._dpr: float = 1.0

        # Window flags: Frameless, Always On Top, Tool window, Transparent for input
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowTransparentForInput
        )

        # Qt widget attributes for transparency and click-through
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    def set_target_screen(
        self,
        screen: QScreen,
        native_origin: tuple[int, int] | None = None,
    ) -> None:
        """Configure overlay geometry and DPI scaling to cover target screen."""
        self._target_screen = screen
        self.setScreen(screen)
        geom = screen.geometry()
        self.setGeometry(geom)

        self._dpr = max(0.1, screen.devicePixelRatio())
        if native_origin is not None:
            self._screen_origin = native_origin
        else:
            self._screen_origin = (int(round(geom.x() * self._dpr)), int(round(geom.y() * self._dpr)))

        logger.debug(
            "OverlayWindow target screen set: geom=%s, origin=%s, DPR=%.2f",
            geom,
            self._screen_origin,
            self._dpr,
        )

    def set_active_region(self, region: Region | None) -> None:
        """Update active translation region to draw optional bounding border."""
        self._active_region = region
        self.update()

    def showEvent(self, event: QShowEvent) -> None:
        """Apply Windows click-through and capture exclusion attributes once window is shown."""
        super().showEvent(event)
        hwnd = int(self.winId())
        res_click = make_click_through(hwnd)
        res_excl = exclude_window_from_capture(hwnd)
        logger.info(
            "OverlayWindow active (HWND=%s): click_through=%s, exclude_capture=%s",
            hwnd,
            res_click,
            res_excl,
        )

    def update_blocks(self, blocks: list[TranslatedBlock]) -> None:
        """Atomically replace active blocks and schedule repaint."""
        self._blocks = list(blocks)
        self.update()

    def clear(self) -> None:
        """Clear all active translation blocks from view."""
        self._blocks = []
        self.update()

    def toggle_visible(self) -> None:
        """Toggle visibility between shown and hidden."""
        if self.isVisible():
            self.hide()
        else:
            self.show()

    def paintEvent(self, event: QPaintEvent) -> None:
        """Render active region dashed border and word-wrapped translated blocks."""
        has_region_border = self.show_region_border and self._active_region is not None
        if not self._blocks and not has_region_border:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        # Draw active region border if enabled
        if has_region_border and self._active_region is not None:
            reg = self._active_region
            l, t, r, b = native_to_local((reg.left, reg.top, reg.right, reg.bottom), self._screen_origin, self._dpr)
            border_rect = QRect(l, t, max(1, r - l), max(1, b - t))
            dashed_pen = QPen(QColor(0, 255, 128, 160), 1, Qt.DashLine)
            painter.setPen(dashed_pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(border_rect)

        bg_color = QColor(self.background_color)
        bg_color.setAlpha(int(self.opacity * 255))
        fg_color = QColor(self.text_color)

        for block in self._blocks:
            text = block.translated_text if isinstance(block, TranslatedBlock) else getattr(block, "text", "")
            text = text.strip()
            if not text:
                continue

            native_bbox = block.source.bbox if isinstance(block, TranslatedBlock) else getattr(block, "bbox", (0, 0, 0, 0))
            l, t, r, b = native_to_local(native_bbox, self._screen_origin, self._dpr)

            box_w = max(10, r - l)
            box_h = max(10, b - t)
            target_rect = QRect(l, t, box_w, box_h)

            current_px = max(9, int(round(box_h * 0.9)))
            font = QFont(self.font_family)

            while current_px > 9:
                font.setPixelSize(current_px)
                metrics = QFontMetrics(font)
                needed = metrics.boundingRect(target_rect, Qt.TextWordWrap, text)
                if needed.height() <= target_rect.height() and needed.width() <= target_rect.width():
                    break
                current_px -= 1

            font.setPixelSize(current_px)
            metrics = QFontMetrics(font)
            needed = metrics.boundingRect(target_rect, Qt.TextWordWrap, text)

            draw_rect = QRect(target_rect)
            if needed.height() > draw_rect.height():
                padding = 4
                max_avail_h = self.height() - draw_rect.top()
                new_h = min(max_avail_h, needed.height() + padding)
                draw_rect.setHeight(max(draw_rect.height(), new_h))

            # Fill rounded background rectangle hiding original English text
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(bg_color))
            painter.drawRoundedRect(draw_rect, 4.0, 4.0)

            # Draw translated text
            painter.setFont(font)
            painter.setPen(QPen(fg_color))
            painter.drawText(draw_rect, Qt.TextWordWrap | Qt.AlignLeft | Qt.AlignVCenter, text)

        painter.end()
