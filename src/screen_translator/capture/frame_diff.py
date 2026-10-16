"""Frame change detection to skip redundant OCR processing."""

from __future__ import annotations

import logging
import cv2
import numpy as np

logger = logging.getLogger(__name__)


class ChangeDetector:
    """Detects visual changes between video frames using downscaled OpenCV absdiff."""

    def __init__(self, threshold: float = 0.02, rolling: bool = False) -> None:
        """Initialize ChangeDetector with sensitivity threshold and mode.

        Args:
            threshold: Fraction of changed pixels (0.0 to 1.0) needed to trigger has_changed() = True.
            rolling: If True, compares with the immediately previous tick and updates reference
                     every frame to detect active motion (e.g. scrolling/animations).
                     If False (default), updates reference only when returning True.
        """
        self.threshold = float(threshold)
        self.rolling = bool(rolling)
        self._reference: np.ndarray | None = None

    @classmethod
    def preprocess(cls, image: np.ndarray) -> np.ndarray:
        """Convert image to grayscale first, then downscale to width 320 using INTER_LINEAR."""
        if image is None or image.size == 0:
            return image

        if image.ndim == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        h, w = gray.shape[:2]
        target_w = 320
        if w != target_w:
            target_h = max(1, int(round(h * (target_w / w))))
            return cv2.resize(gray, (target_w, target_h), interpolation=cv2.INTER_LINEAR)
        return gray

    def _preprocess(self, image: np.ndarray) -> np.ndarray:
        """Downscale frame to fixed width 320 and convert to grayscale."""
        return self.preprocess(image)

    def has_changed(self, image: np.ndarray, preprocessed: np.ndarray | None = None) -> bool:
        """Determine whether current image has changed meaningfully compared to reference frame.

        Args:
            image: Current frame numpy array (BGR or grayscale).
            preprocessed: Optional pre-computed downscaled grayscale thumbnail.

        Returns:
            bool: True if visual change exceeds threshold, False otherwise.
        """
        if (image is None or image.size == 0) and preprocessed is None:
            return False

        gray = preprocessed if preprocessed is not None else self._preprocess(image)

        if self._reference is None or self._reference.shape != gray.shape:
            logger.debug("ChangeDetector: New baseline frame initialized (shape=%s)", gray.shape)
            self._reference = gray
            return True

        diff = cv2.absdiff(gray, self._reference)
        changed_pixels = int(np.count_nonzero(diff > 25))
        total_pixels = diff.size
        ratio = changed_pixels / total_pixels
        is_diff = ratio > self.threshold

        if self.rolling:
            # Rolling mode: reference is always updated every frame to detect continuous motion
            self._reference = gray
            return is_diff

        # Baseline mode: reference is updated only when meaningful change occurs
        if is_diff:
            logger.debug("ChangeDetector: Change detected (ratio=%.4f > threshold=%.4f)", ratio, self.threshold)
            self._reference = gray
            return True

        return False

    def commit(self, image: np.ndarray, preprocessed: np.ndarray | None = None) -> None:
        """Set reference to the frame about to be processed, preventing extra OCR after motion."""
        if (image is None or image.size == 0) and preprocessed is None:
            return
        self._reference = preprocessed if preprocessed is not None else self._preprocess(image)
        logger.debug("ChangeDetector: Frame committed as new reference baseline")

    def reset(self) -> None:
        """Clear previous frame baseline so next frame is forced to register as changed."""
        logger.debug("ChangeDetector: Baseline reset")
        self._reference = None
