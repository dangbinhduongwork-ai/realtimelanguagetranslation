"""Frame change detection to skip redundant OCR processing."""

from __future__ import annotations

import logging
import cv2
import numpy as np

logger = logging.getLogger(__name__)


class ChangeDetector:
    """Detects visual changes between consecutive video frames using downscaled OpenCV absdiff."""

    def __init__(self, threshold: float = 0.02) -> None:
        """Initialize ChangeDetector with sensitivity threshold.

        Args:
            threshold: Fraction of changed pixels (0.0 to 1.0) needed to trigger has_changed() = True.
        """
        self.threshold = float(threshold)
        self._reference: np.ndarray | None = None

    def has_changed(self, image: np.ndarray) -> bool:
        """Determine whether current image has changed meaningfully compared to reference frame.

        - Converts to grayscale and downscales to width 320 (keeping aspect ratio).
        - Compares with reference frame using cv2.absdiff (diff > 25 threshold).
        - Returns True on first frame, on resolution change, or when changed ratio > threshold.
        - Updates reference ONLY when returning True so slow gradual changes accumulate.

        Args:
            image: Current frame numpy array (BGR or grayscale).

        Returns:
            bool: True if visual change exceeds threshold, False otherwise.
        """
        if image is None or image.size == 0:
            return False

        h, w = image.shape[:2]
        target_w = 320
        if w != target_w:
            target_h = max(1, int(round(h * (target_w / w))))
            resized = cv2.resize(image, (target_w, target_h), interpolation=cv2.INTER_AREA)
        else:
            resized = image

        if resized.ndim == 3:
            gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        else:
            gray = resized

        if self._reference is None or self._reference.shape != gray.shape:
            logger.debug("ChangeDetector: New baseline frame initialized (shape=%s)", gray.shape)
            self._reference = gray
            return True

        diff = cv2.absdiff(gray, self._reference)
        changed_pixels = int(np.count_nonzero(diff > 25))
        total_pixels = diff.size
        ratio = changed_pixels / total_pixels

        if ratio > self.threshold:
            logger.debug("ChangeDetector: Change detected (ratio=%.4f > threshold=%.4f)", ratio, self.threshold)
            self._reference = gray
            return True

        return False

    def reset(self) -> None:
        """Clear previous frame baseline so next frame is forced to register as changed."""
        logger.debug("ChangeDetector: Baseline reset")
        self._reference = None
