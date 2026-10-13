"""Frame change detection to skip redundant OCR processing."""

from __future__ import annotations

import numpy as np


class ChangeDetector:
    """Detects visual differences between consecutive screen frames using OpenCV."""

    def __init__(self, threshold: float = 0.02) -> None:
        """Initialize ChangeDetector with sensitivity threshold.

        Args:
            threshold: Normalized pixel difference ratio (0.0 to 1.0) required to trigger OCR.
        """
        raise NotImplementedError("ChangeDetector is scheduled for Stage 1")

    def has_changed(self, image: np.ndarray) -> bool:
        """Determine whether current image has changed significantly compared to previous frame.

        Args:
            image: Current frame numpy array.

        Returns:
            bool: True if difference exceeds threshold or if baseline is empty, False otherwise.
        """
        raise NotImplementedError("ChangeDetector is scheduled for Stage 1")

    def reset(self) -> None:
        """Clear previous frame baseline so next frame is treated as changed."""
        raise NotImplementedError("ChangeDetector is scheduled for Stage 1")
