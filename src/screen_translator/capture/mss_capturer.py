"""Screen capture implementation using mss."""

from __future__ import annotations

from screen_translator.capture.base import ScreenCapturer
from screen_translator.models import Frame, Region


class MssCapturer(ScreenCapturer):
    """MSS-based multi-monitor screen capture engine."""

    def __init__(self, monitor_index: int = 1) -> None:
        """Initialize MSS capturer for a specific monitor.

        Args:
            monitor_index: 1-based monitor index (1 is typically primary monitor).
        """
        raise NotImplementedError("MssCapturer is scheduled for Stage 1")

    def grab(self, region: Region | None = None) -> Frame:
        """Capture screen frame from the requested region or active monitor.

        Args:
            region: Optional bounding rectangle to capture.

        Returns:
            Frame: Captured frame containing image data, region, and timestamp.
        """
        raise NotImplementedError("MssCapturer is scheduled for Stage 1")

    def close(self) -> None:
        """Release the MSS capture context."""
        raise NotImplementedError("MssCapturer is scheduled for Stage 1")
