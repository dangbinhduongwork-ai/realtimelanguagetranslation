"""Screen capture implementation using mss."""

from __future__ import annotations

import logging
import time
from typing import Any

import mss
import numpy as np

from screen_translator.capture.base import ScreenCapturer
from screen_translator.models import Frame, Region

logger = logging.getLogger(__name__)


class MssCapturer(ScreenCapturer):
    """Captures screen frames using the mss library with lazy thread-local initialization."""

    def __init__(self, monitor_index: int = 1) -> None:
        """Initialize MSS capturer configuration.

        IMPORTANT: mss instances are NOT thread-safe. The mss instance is created
        lazily on the first grab() call inside the executing thread.

        Args:
            monitor_index: Monitor index (1-based; 1 is typically the primary monitor).
        """
        self.monitor_index = monitor_index
        self._sct: Any | None = None

    def grab(self, region: Region | None = None) -> Frame:
        """Capture screen frame from the requested region or active monitor.

        Args:
            region: Optional screen region in absolute pixel coordinates.
                    If None, captures the entire monitor specified by monitor_index.

        Returns:
            Frame: Captured BGR frame with actual screen region and monotonic timestamp.
        """
        if self._sct is None:
            logger.debug("Lazily initializing MSS instance in current thread")
            self._sct = mss.mss()

        if region is None:
            monitors = self._sct.monitors
            if 1 <= self.monitor_index < len(monitors):
                mon = monitors[self.monitor_index]
            else:
                logger.warning(
                    "Monitor index %d out of bounds (available: 1..%d). Falling back to primary monitor 1.",
                    self.monitor_index,
                    len(monitors) - 1,
                )
                mon = monitors[1] if len(monitors) > 1 else monitors[0]

            capture_bbox = {
                "left": mon["left"],
                "top": mon["top"],
                "width": mon["width"],
                "height": mon["height"],
            }
            actual_region = Region(
                left=mon["left"],
                top=mon["top"],
                width=mon["width"],
                height=mon["height"],
            )
        else:
            capture_bbox = {
                "left": region.left,
                "top": region.top,
                "width": region.width,
                "height": region.height,
            }
            actual_region = region

        sct_img = self._sct.grab(capture_bbox)

        # Convert raw BGRA pixels to contiguous 3-channel BGR numpy array
        raw_bgra = np.asarray(sct_img, dtype=np.uint8)
        bgr_image = np.ascontiguousarray(raw_bgra[:, :, :3])

        return Frame(
            image=bgr_image,
            region=actual_region,
            timestamp=time.monotonic(),
        )

    def close(self) -> None:
        """Release underlying MSS context."""
        if self._sct is not None:
            try:
                self._sct.close()
            except Exception as exc:
                logger.debug("Error closing MSS instance: %s", exc)
            finally:
                self._sct = None
