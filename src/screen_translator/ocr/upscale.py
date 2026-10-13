"""Helper functions for adaptive OCR image scaling and coordinate remapping."""

from __future__ import annotations

from collections.abc import Sequence
import cv2
import numpy as np

from screen_translator.models import TextBlock


def calculate_median_line_height(blocks: Sequence[TextBlock]) -> float:
    """Calculate median line height in pixels from a list of TextBlock items.

    Args:
        blocks: List or sequence of detected TextBlock instances.

    Returns:
        float: Median bounding box height (0.0 if empty).
    """
    if not blocks:
        return 0.0
    heights = [max(1, b.bbox[3] - b.bbox[1]) for b in blocks]
    return float(np.median(heights))


def calculate_mean_confidence(blocks: Sequence[TextBlock]) -> float:
    """Calculate mean confidence score of a list of TextBlock items.

    Args:
        blocks: Sequence of TextBlock instances.

    Returns:
        float: Average confidence score (0.0 if empty).
    """
    if not blocks:
        return 0.0
    return float(np.mean([b.confidence for b in blocks]))


def scale_image(image: np.ndarray, factor: float) -> np.ndarray:
    """Resize image array using bicubic interpolation.

    Args:
        image: Original BGR or grayscale numpy image.
        factor: Scaling multiplier (e.g. 1.0, 1.5, 2.0).

    Returns:
        np.ndarray: Rescaled image, or original image if factor is 1.0.
    """
    if factor == 1.0 or image is None or image.size == 0:
        return image

    h, w = image.shape[:2]
    new_w = max(1, int(round(w * factor)))
    new_h = max(1, int(round(h * factor)))
    return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_CUBIC)


def remap_blocks_to_screen(
    blocks: Sequence[TextBlock],
    factor: float,
    offset: tuple[int, int] = (0, 0),
) -> list[TextBlock]:
    """Map upscaled block coordinates back to original unscaled screen coordinates.

    Args:
        blocks: Blocks detected on (possibly upscaled) image.
        factor: Scale factor used when running OCR (>= 1.0).
        offset: (left, top) screen offset to add after un-scaling.

    Returns:
        list[TextBlock]: Blocks with bounding boxes mapped to original screen pixels.
    """
    remapped: list[TextBlock] = []
    scale = max(0.01, float(factor))
    off_x, off_y = offset

    for b in blocks:
        l, t, r, b_bottom = b.bbox
        orig_l = int(round(l / scale)) + off_x
        orig_t = int(round(t / scale)) + off_y
        orig_r = int(round(r / scale)) + off_x
        orig_b = int(round(b_bottom / scale)) + off_y

        if orig_r <= orig_l:
            orig_r = orig_l + 1
        if orig_b <= orig_t:
            orig_b = orig_t + 1

        remapped.append(
            TextBlock(
                text=b.text,
                bbox=(orig_l, orig_t, orig_r, orig_b),
                confidence=b.confidence,
            )
        )

    return remapped
