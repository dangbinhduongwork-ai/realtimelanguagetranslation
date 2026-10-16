"""Result stabilization utilities to prevent visual jitter and redundant repaints."""

from __future__ import annotations

from collections.abc import Sequence
from screen_translator.models import TextBlock, TranslatedBlock


def _extract_bbox(b: TextBlock | TranslatedBlock) -> tuple[int, int, int, int]:
    """Extract (left, top, right, bottom) bounding box from TextBlock or TranslatedBlock."""
    return b.source.bbox if isinstance(b, TranslatedBlock) else b.bbox


def _extract_text(b: TextBlock | TranslatedBlock) -> str:
    """Extract text content from TextBlock or TranslatedBlock."""
    return b.translated_text if isinstance(b, TranslatedBlock) else b.text


def blocks_equivalent(
    prev: Sequence[TextBlock | TranslatedBlock] | None,
    new: Sequence[TextBlock | TranslatedBlock] | None,
    tol_px: int = 4,
) -> bool:
    """Check whether two block sequences are equivalent within coordinate jitter tolerance.

    Returns True if:
    - Both sequences are None or both are empty.
    - Both sequences have identical item count.
    - Each block pair sorted by (top, left) has identical text.
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

    # Sort both sequences by canonical coordinate order (top, left) before comparing
    sorted_prev = sorted(prev, key=lambda b: (_extract_bbox(b)[1], _extract_bbox(b)[0]))
    sorted_new = sorted(new, key=lambda b: (_extract_bbox(b)[1], _extract_bbox(b)[0]))

    for b_prev, b_new in zip(sorted_prev, sorted_new):
        if _extract_text(b_prev) != _extract_text(b_new):
            return False

        bbox_p = _extract_bbox(b_prev)
        bbox_n = _extract_bbox(b_new)

        for cp, cn in zip(bbox_p, bbox_n):
            if abs(cp - cn) > tol_px:
                return False

    return True
