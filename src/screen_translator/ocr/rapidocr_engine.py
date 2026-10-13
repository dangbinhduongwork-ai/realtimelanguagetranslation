"""RapidOCR engine implementation using ONNX Runtime."""

from __future__ import annotations

import logging
from typing import Any
import numpy as np

from screen_translator.models import TextBlock
from screen_translator.ocr.base import OcrEngine

logger = logging.getLogger(__name__)


class RapidOcrEngine(OcrEngine):
    """Concrete OCR engine backed by rapidocr-onnxruntime with lazy loading and screen coordinate mapping."""

    def __init__(self, min_confidence: float = 0.6) -> None:
        """Initialize RapidOCR engine configuration.

        Args:
            min_confidence: Confidence threshold (0.0 to 1.0) below which OCR results are dropped.
        """
        self.min_confidence = float(min_confidence)
        self._engine: Any | None = None

    def warmup(self) -> None:
        """Pre-load RapidOCR neural network models and execute a dummy inference pass."""
        if self._engine is None:
            logger.info("Loading RapidOCR ONNX models into memory...")
            from rapidocr_onnxruntime import RapidOCR

            self._engine = RapidOCR()
            # Run dummy frame for onnxruntime JIT / graph initialization
            dummy_frame = np.zeros((48, 128, 3), dtype=np.uint8)
            try:
                self._engine(dummy_frame)
            except Exception as exc:
                logger.debug("Warmup dummy inference encountered: %s", exc)
            logger.info("RapidOCR engine ready.")

    def recognize(
        self,
        image: np.ndarray,
        offset: tuple[int, int] = (0, 0),
    ) -> list[TextBlock]:
        """Extract text blocks using RapidOCR and convert bounding boxes to screen coordinates.

        Args:
            image: Image array (BGR) to run OCR on.
            offset: (left, top) screen coordinate offset added to local box coordinates.

        Returns:
            list[TextBlock]: List of detected text blocks in SCREEN coordinates.
        """
        if image is None or image.size == 0:
            return []

        if self._engine is None:
            self.warmup()

        try:
            result, _ = self._engine(image)
        except Exception as exc:
            logger.error("RapidOCR inference failed: %s", exc)
            return []

        if not result:
            return []

        blocks: list[TextBlock] = []
        offset_x, offset_y = offset

        for item in result:
            if not item or len(item) < 3:
                continue

            box, raw_text, raw_score = item[0], item[1], item[2]

            try:
                confidence = float(raw_score)
            except (ValueError, TypeError):
                confidence = 0.0

            if confidence < self.min_confidence:
                continue

            text = str(raw_text).strip()
            if not text:
                continue

            try:
                xs = [float(pt[0]) for pt in box]
                ys = [float(pt[1]) for pt in box]
                min_x = int(min(xs)) + offset_x
                max_x = int(max(xs)) + offset_x
                min_y = int(min(ys)) + offset_y
                max_y = int(max(ys)) + offset_y

                left, right = min(min_x, max_x), max(min_x, max_x)
                top, bottom = min(min_y, max_y), max(min_y, max_y)

                # Ensure non-zero width and height
                if right == left:
                    right += 1
                if bottom == top:
                    bottom += 1

                blocks.append(
                    TextBlock(
                        text=text,
                        bbox=(left, top, right, bottom),
                        confidence=round(confidence, 4),
                    )
                )
            except Exception as exc:
                logger.debug("Skipping malformed OCR detection item %s: %s", item, exc)

        return blocks
