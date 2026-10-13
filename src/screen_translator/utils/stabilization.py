"""Result stabilization utilities to prevent visual jitter and redundant repaints."""

from __future__ import annotations

from collections.abc import Sequence
from screen_translator.models import TextBlock, TranslatedBlock


def blocks_equivalent(
    prev: Sequence[TextBlock | TranslatedBlock] | None,
    new: Sequence[TextBlock | TranslatedBlock] | None,
    tol_px: int = 4,
) -> bool:
    """Check whether two block sequences are equivalent within coordinate jitter tolerance.

    Returns True if:
    - Both sequences are None or both are empty.
    - Both sequences have identical item count.
    - Each block pair has identical text (translated_text or text).
    - Each block pair's bounding box coordinates differ by at most `tol_px`.

    Args:
        prev: Previous sequence of blocks (or None).
        new: New sequence of blocks (or None).
        tol_px: Maximum allowed pixel jitter for left, top, right, bottom coordinates.

    Returns:
        bool: True if results are equivalent; False if visual update is needed.
    """
    if prev is None and new is None:
        return True
    if prev is None or new is None:
        return False
    if len(prev) != len(new):
        return False

    for b_prev, b_new in zip(prev, new):
        # 1. Compare text content
        text_p = b_prev.translated_text if isinstance(b_prev, TranslatedBlock) else b_prev.text
        text_n = b_new.translated_text if isinstance(b_new, TranslatedBlock) else b_new.text
        if text_p != text_n:
            return False

        # 2. Compare bounding box coordinates within tolerance
        bbox_p = b_prev.source.bbox if isinstance(b_prev, TranslatedBlock) else b_prev.bbox
        bbox_n = b_new.source.bbox if isinstance(b_new, TranslatedBlock) else b_new.bbox

        for cp, cn in zip(bbox_p, bbox_n):
            if abs(cp - cn) > tol_px:
                return False

    return True
