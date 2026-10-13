"""Data models for Screen Translator.

All models are defined as frozen dataclasses representing pure data in the pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class Region:
    """Represents a rectangular screen area in pixel coordinates.

    Attributes:
        left: Leftmost screen X coordinate.
        top: Topmost screen Y coordinate.
        width: Width of the region in pixels.
        height: Height of the region in pixels.
    """

    left: int
    top: int
    width: int
    height: int

    def __post_init__(self) -> None:
        """Validate region dimensions."""
        if self.width <= 0:
            raise ValueError(f"Region width must be positive, got {self.width}")
        if self.height <= 0:
            raise ValueError(f"Region height must be positive, got {self.height}")

    @property
    def right(self) -> int:
        """Return right coordinate (left + width)."""
        return self.left + self.width

    @property
    def bottom(self) -> int:
        """Return bottom coordinate (top + height)."""
        return self.top + self.height

    @property
    def as_tuple(self) -> tuple[int, int, int, int]:
        """Return region as a (left, top, width, height) tuple."""
        return (self.left, self.top, self.width, self.height)


@dataclass(frozen=True, eq=False)
class Frame:
    """Represents a captured screen frame.

    Attributes:
        image: Numpy ndarray holding the raw captured image (BGR / BGRA).
        region: Screen region where this frame was captured from.
        timestamp: Unix epoch timestamp in seconds when the frame was acquired.
    """

    image: np.ndarray
    region: Region
    timestamp: float


@dataclass(frozen=True)
class TextBlock:
    """Represents detected text with bounding box in SCREEN coordinates.

    Attributes:
        text: Recognized text string.
        bbox: (left, top, right, bottom) screen coordinates bounding the text.
        confidence: Recognition confidence score between 0.0 and 1.0.
    """

    text: str
    bbox: tuple[int, int, int, int]
    confidence: float

    def __post_init__(self) -> None:
        """Validate bounding box and confidence score."""
        if len(self.bbox) != 4:
            raise ValueError(f"bbox must contain 4 coordinates (left, top, right, bottom), got {self.bbox}")
        left, top, right, bottom = self.bbox
        if right < left:
            raise ValueError(f"Invalid bbox: right ({right}) < left ({left})")
        if bottom < top:
            raise ValueError(f"Invalid bbox: bottom ({bottom}) < top ({top})")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"confidence must be between 0.0 and 1.0, got {self.confidence}")


@dataclass(frozen=True)
class TranslatedBlock:
    """Represents a source text block paired with its translated text.

    Attributes:
        source: Original TextBlock detected by OCR.
        translated_text: Translated target language text.
    """

    source: TextBlock
    translated_text: str
