"""RapidOCR engine implementation using ONNX Runtime."""

from __future__ import annotations

import numpy as np

from screen_translator.models import TextBlock
from screen_translator.ocr.base import OcrEngine


class RapidOcrEngine(OcrEngine):
    """Concrete OCR engine backed by rapidocr-onnxruntime."""

    def __init__(self, min_confidence: float = 0.6) -> None:
        """Initialize RapidOCR engine instance.

        Args:
            min_confidence: Threshold confidence (0.0 to 1.0) below which OCR detections are discarded.
        """
        raise NotImplementedError("RapidOcrEngine is scheduled for Stage 1")

    def recognize(
        self,
        image: np.ndarray,
        offset: tuple[int, int] = (0, 0),
    ) -> list[TextBlock]:
        """Perform text recognition on image array.

        Args:
            image: Image array to recognize text from.
            offset: (left, top) screen offset added to local coordinates.

        Returns:
            list[TextBlock]: Recognized text blocks in screen coordinates.
        """
        raise NotImplementedError("RapidOcrEngine is scheduled for Stage 1")
