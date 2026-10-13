"""Abstract base class for OCR engines."""

from __future__ import annotations

from abc import ABC, abstractmethod
import numpy as np

from screen_translator.models import TextBlock


class OcrEngine(ABC):
    """Abstract interface for optical character recognition engines."""

    @abstractmethod
    def recognize(
        self,
        image: np.ndarray,
        offset: tuple[int, int] = (0, 0),
    ) -> list[TextBlock]:
        """Detect and recognize text regions from an image array.

        Args:
            image: Image array to process (numpy BGR / RGB array).
            offset: (left, top) screen coordinate offset to convert local box coordinates to screen coordinates.

        Returns:
            list[TextBlock]: List of recognized text blocks with bounding boxes in SCREEN coordinates.
        """
