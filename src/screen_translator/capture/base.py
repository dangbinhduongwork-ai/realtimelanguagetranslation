"""Abstract base class for screen capturers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from screen_translator.models import Frame, Region


class ScreenCapturer(ABC):
    """Abstract interface for screen capture implementations."""

    @abstractmethod
    def grab(self, region: Region | None = None) -> Frame:
        """Capture a frame from the specified screen region.

        Args:
            region: Screen coordinates to capture, or None for full monitor capture.

        Returns:
            Frame: Captured image with region metadata and timestamp.
        """

    @abstractmethod
    def close(self) -> None:
        """Release any underlying capture resources and handles."""
