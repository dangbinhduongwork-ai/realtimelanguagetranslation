"""Screen capture implementation using mss."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

import cv2
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
        lazily on the first grab() call inside each executing thread.

        Args:
            monitor_index: Monitor index (1-based; 1 is typically the primary monitor).
        """
        self.monitor_index = monitor_index
        self._local = threading.local()

    def _get_sct(self) -> Any:
        """Get or lazily initialize thread-local MSS instance."""
        if not hasattr(self._local, "sct") or self._local.sct is None:
            logger.debug("Initializing MSS instance in thread %s", threading.get_ident())
            self._local.sct = mss.mss()
        return self._local.sct

    def grab(self, region: Region | None = None) -> Frame:
        """Capture screen frame from the requested region or active monitor.

        Args:
            region: Optional screen region in absolute pixel coordinates.
                    If None, captures the entire monitor specified by monitor_index.

        Returns:
            Frame: Captured BGR frame with actual screen region and monotonic timestamp.
        """
        sct = self._get_sct()

        if region is None:
            monitors = sct.monitors
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

        sct_img = sct.grab(capture_bbox)

        # Convert raw BGRA pixels to 3-channel BGR using OpenCV SIMD
        raw_bgra = np.asarray(sct_img, dtype=np.uint8)
        bgr_image = cv2.cvtColor(raw_bgra, cv2.COLOR_BGRA2BGR)

        return Frame(
            image=bgr_image,
            region=actual_region,
            timestamp=time.monotonic(),
        )

    def close(self) -> None:
        """Release underlying MSS context for the current thread."""
        if hasattr(self._local, "sct") and self._local.sct is not None:
            try:
                self._local.sct.close()
            except Exception as exc:
                logger.debug("Error closing MSS instance: %s", exc)
            finally:
                self._local.sct = None
