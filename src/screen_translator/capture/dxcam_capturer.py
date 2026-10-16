"""Screen capture implementation using the dxcam library (DXGI Desktop Duplication)."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

import numpy as np

from screen_translator.capture.base import ScreenCapturer
from screen_translator.models import Frame, Region

logger = logging.getLogger(__name__)


class DxcamCapturer(ScreenCapturer):
    """Captures screen frames using DXGI Desktop Duplication via dxcam."""

    def __init__(self, monitor_index: int = 1) -> None:
        """Initialize DXCam capturer configuration.

        Args:
            monitor_index: 1-based monitor index (1 is typically the primary display).
        """
        self.monitor_index = monitor_index
        self._local = threading.local()
        self._last_frame: Frame | None = None
        self._monitor_bounds: tuple[int, int, int, int] | None = None

    def _get_camera(self) -> Any:
        """Lazily initialize dxcam camera for the current calling thread."""
        if not hasattr(self._local, "camera") or self._local.camera is None:
            try:
                import dxcam  # type: ignore[import-untyped]
            except ImportError as exc:
                raise ImportError(
                    "dxcam is required for capture.backend: 'dxcam'. "
                    "Install it via: pip install dxcam (see requirements-optional.txt)"
                ) from exc

            output_idx = max(0, self.monitor_index - 1)
            logger.info("Initializing DXCam camera on device 0, output %d in thread %s", output_idx, threading.get_ident())
            try:
                cam = dxcam.create(device_idx=0, output_idx=output_idx, output_color="BGR")
            except Exception as exc:
                logger.warning("Failed to initialize DXCam on output %d: %s. Falling back to default output 0.", output_idx, exc)
                cam = dxcam.create(device_idx=0, output_idx=0, output_color="BGR")

            self._local.camera = cam
        return self._local.camera

    def _get_monitor_bounds(self) -> tuple[int, int, int, int]:
        """Obtain native absolute bounds (left, top, width, height) of the active monitor (cached)."""
        if self._monitor_bounds is None:
            # Query mss monitors dictionary once as the canonical coordinate reference across monitors
            import mss

            with mss.mss() as sct:
                monitors = sct.monitors
                if 1 <= self.monitor_index < len(monitors):
                    m = monitors[self.monitor_index]
                else:
                    m = monitors[1] if len(monitors) > 1 else monitors[0]
                self._monitor_bounds = (m["left"], m["top"], m["width"], m["height"])
        return self._monitor_bounds

    def grab(self, region: Region | None = None) -> Frame:
        """Capture screen frame using DXCam.

        Args:
            region: Optional screen region in absolute pixel coordinates.

        Returns:
            Frame: Captured BGR frame with actual screen region and timestamp.
        """
        camera = self._get_camera()
        mon_left, mon_top, mon_width, mon_height = self._get_monitor_bounds()

        if region is None:
            actual_region = Region(left=mon_left, top=mon_top, width=mon_width, height=mon_height)
            dxcam_region = None
        else:
            actual_region = region
            # Convert absolute screen coordinates to monitor-relative (left, top, right, bottom)
            rel_left = max(0, region.left - mon_left)
            rel_top = max(0, region.top - mon_top)
            rel_right = min(mon_width, rel_left + region.width)
            rel_bottom = min(mon_height, rel_top + region.height)
            dxcam_region = (rel_left, rel_top, rel_right, rel_bottom)

        raw_bgr = camera.grab(region=dxcam_region)

        # DXCam returns None when Desktop Duplication reports no screen update
        if raw_bgr is None:
            if self._last_frame is not None:
                return Frame(
                    image=self._last_frame.image,
                    region=actual_region,
                    timestamp=time.monotonic(),
                )
            # First frame fallback: take a full screen capture or wait briefly
            time.sleep(0.01)
            raw_bgr = camera.grab(region=dxcam_region)
            if raw_bgr is None:
                # Fallback blank frame if still unavailable
                w = actual_region.width
                h = actual_region.height
                raw_bgr = np.zeros((h, w, 3), dtype=np.uint8)

        # Ensure contiguous uint8 BGR array
        bgr_contiguous = np.ascontiguousarray(raw_bgr[:, :, :3], dtype=np.uint8)

        frame = Frame(
            image=bgr_contiguous,
            region=actual_region,
            timestamp=time.monotonic(),
        )
        self._last_frame = frame
        return frame

    def close(self) -> None:
        """Release underlying DXCam camera resources."""
        if hasattr(self._local, "camera") and self._local.camera is not None:
            try:
                self._local.camera.release()
            except Exception as exc:
                logger.debug("Error releasing DXCam camera: %s", exc)
            self._local.camera = None
        self._last_frame = None
        self._monitor_bounds = None
