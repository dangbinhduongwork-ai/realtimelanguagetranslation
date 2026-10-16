"""Transparent, click-through, always-on-top overlay window."""

from __future__ import annotations

from collections.abc import Callable
import logging

from PySide6.QtCore import QEvent, QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetrics, QPaintEvent, QPainter, QPen, QScreen, QShowEvent
from PySide6.QtWidgets import QWidget

from screen_translator.models import Region, TranslatedBlock
from screen_translator.ui.layout import bucket_line_heights, find_cached_layout, font_px_for
from screen_translator.utils.coords import native_to_local
from screen_translator.utils.win_utils import (
    exclude_window_from_capture,
    get_window_display_affinity,
    get_windows_build_number,
    make_click_through,
)

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
        tray_notifier: Callable[[str, str], None] | None = None,
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
        self.tray_notifier = tray_notifier

        self._blocks: list[TranslatedBlock] = []
        self._active_region: Region | None = None
        self._target_screen: QScreen | None = None
        self._screen_origin: tuple[int, int] = (0, 0)
        self._dpr: float = 1.0

        self._affinity_failed_warned: bool = False
        self._layout_cache: list[tuple[tuple[int, int, int, int], str, int, int]] = []
        self._computed_layouts: list[tuple[QRect, str, int]] = []

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
        if self.isVisible():
            self._apply_window_affinity()
        if self._blocks:
            self._computed_layouts = self._compute_layout(self._blocks)

    def set_active_region(self, region: Region | None) -> None:
        """Update active translation region to draw optional bounding border."""
        self._active_region = region
        self.update()

    def _apply_window_affinity(self) -> None:
        """Apply capture exclusion before click-through, and verify affinity value."""
        hwnd = int(self.winId())
        if hwnd <= 0:
            return

        # 1. Exclude from capture BEFORE setting WS_EX_TRANSPARENT
        res_excl = exclude_window_from_capture(hwnd)
        res_click = make_click_through(hwnd)

        # 2. Verify affinity
        aff = get_window_display_affinity(hwnd)
        build = get_windows_build_number()
        expected = 0x11 if build >= 19041 else 0x01

        logger.debug(
            "OverlayWindow affinity applied (HWND=%s): click_through=%s, exclude=%s, affinity=%s",
            hwnd,
            res_click,
            res_excl,
            f"{aff:#x}" if aff is not None else "None",
        )

        if aff != expected and aff != 0x11 and aff != 0x01:
            if not self._affinity_failed_warned:
                self._affinity_failed_warned = True
                logger.error(
                    "Window display affinity verification failed (expected 0x%x, got 0x%s)",
                    expected,
                    f"{aff:#x}" if aff is not None else "None",
                )
                if self.tray_notifier:
                    self.tray_notifier(
                        "Screen Translator",
                        "Overlay is visible to screen capture; translation may loop",
                    )

    def event(self, event: QEvent) -> bool:
        """Re-apply window capture exclusion when native window handle changes."""
        if event.type() == QEvent.Type.WinIdChange:
            self._apply_window_affinity()
        return super().event(event)

    def showEvent(self, event: QShowEvent) -> None:
        """Apply Windows click-through and capture exclusion attributes once window is shown."""
        super().showEvent(event)
        self._apply_window_affinity()
        # Re-attempt once window is mapped and composited by Desktop Window Manager (DWM)
        QTimer.singleShot(150, self._apply_window_affinity)

    def update_blocks(self, blocks: list[TranslatedBlock]) -> None:
        """Atomically replace active blocks, precompute typography layout, and schedule repaint."""
        self._blocks = list(blocks)
        self._computed_layouts = self._compute_layout(self._blocks)
        self.update()

    def clear(self) -> None:
        """Clear all active translation blocks and computed layouts from view."""
        self._blocks = []
        self._layout_cache = []
        self._computed_layouts = []
        self.update()

    def toggle_visible(self) -> None:
        """Toggle visibility between shown and hidden."""
        if self.isVisible():
            self.hide()
        else:
            self.show()

    def _compute_layout(
        self,
        blocks: list[TranslatedBlock],
    ) -> list[tuple[QRect, str, int]]:
        """Precompute layout geometry, clustered font sizes, and box heights outside paintEvent."""
        if not blocks:
            self._layout_cache = []
            return []

        # 1. Compute local single-line heights across all blocks for cluster bucketing
        local_heights: list[float] = []
        for block in blocks:
            src = block.source if isinstance(block, TranslatedBlock) else block
            raw_lh = getattr(src, "line_height", 0.0)
            if raw_lh <= 0:
                raw_bbox = getattr(src, "bbox", (0, 0, 0, 0))
                raw_lh = (raw_bbox[3] - raw_bbox[1]) / max(1, getattr(src, "line_count", 1))
            local_lh = max(10.0, float(raw_lh) / max(0.1, self._dpr))
            local_heights.append(local_lh)

        bucket_map = bucket_line_heights(local_heights)
        new_layout_cache: list[tuple[tuple[int, int, int, int], str, int, int]] = []
        computed: list[tuple[QRect, str, int]] = []
        avail_h = self.height()

        for idx, block in enumerate(blocks):
            text = block.translated_text if isinstance(block, TranslatedBlock) else getattr(block, "text", "")
            text = text.strip()
            if not text:
                continue

            native_bbox = block.source.bbox if isinstance(block, TranslatedBlock) else getattr(block, "bbox", (0, 0, 0, 0))
            l, t, r, b = native_to_local(native_bbox, self._screen_origin, self._dpr)
            local_box = (l, t, r, b)

            box_w = max(10, r - l)
            box_h = max(10, b - t)

            # 2. Check temporal stability cache
            cached = find_cached_layout(local_box, text, self._layout_cache, tol_px=4, min_iou=0.6)
            if cached is not None:
                chosen_px, draw_h = cached
            else:
                lh = local_heights[idx] if idx < len(local_heights) else float(box_h)
                bucketed_lh = bucket_map.get(lh, lh)
                target_px = font_px_for(bucketed_lh)

                # Shrink by at most 15% (min 80% of target_px, min 10px)
                min_px = max(10, int(round(target_px * 0.85)))
                cur_px = target_px

                while cur_px > min_px:
                    font_test = QFont(self.font_family)
                    font_test.setPixelSize(cur_px)
                    metrics = QFontMetrics(font_test)
                    needed = metrics.boundingRect(QRect(l, t, box_w, 10000), Qt.TextWordWrap, text)
                    if needed.width() <= box_w and needed.height() <= box_h:
                        break
                    if needed.width() > box_w:
                        cur_px -= 1
                    else:
                        # Width fits, but height exceeds: extend box downward rather than shrinking further
                        break

                chosen_px = cur_px
                font_final = QFont(self.font_family)
                font_final.setPixelSize(chosen_px)
                metrics = QFontMetrics(font_final)
                needed = metrics.boundingRect(QRect(l, t, box_w, 10000), Qt.TextWordWrap, text)
                draw_h = max(box_h, needed.height() + 4)
                if avail_h > t:
                    draw_h = min(avail_h - t, draw_h)

            new_layout_cache.append((local_box, text, chosen_px, draw_h))
            draw_rect = QRect(l, t, box_w, draw_h)
            computed.append((draw_rect, text, chosen_px))

        self._layout_cache = new_layout_cache
        return computed

    def paintEvent(self, event: QPaintEvent) -> None:
        """Render active region dashed border and pre-computed translated blocks with zero paint-time measurement."""
        has_region_border = self.show_region_border and self._active_region is not None
        if not self._computed_layouts and not has_region_border:
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
        bg_brush = QBrush(bg_color)
        fg_pen = QPen(fg_color)

        font_draw = QFont(self.font_family)

        for draw_rect, text, chosen_px in self._computed_layouts:
            # Fill rounded background rectangle hiding original English text
            painter.setPen(Qt.NoPen)
            painter.setBrush(bg_brush)
            painter.drawRoundedRect(draw_rect, 4.0, 4.0)

            # Draw translated text
            font_draw.setPixelSize(chosen_px)
            painter.setFont(font_draw)
            painter.setPen(fg_pen)
            painter.drawText(draw_rect, Qt.TextWordWrap | Qt.AlignLeft | Qt.AlignVCenter, text)

        painter.end()
