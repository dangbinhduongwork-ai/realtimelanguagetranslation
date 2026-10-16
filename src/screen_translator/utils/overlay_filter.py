"""Utilities to prevent self-capturing overlay recursion and duplicate translation blocks."""

from __future__ import annotations

import unicodedata
from collections.abc import Sequence

from screen_translator.models import TextBlock, TranslatedBlock
from screen_translator.translate.filters import VIETNAMESE_DIACRITICS, needs_translation


def strip_accents(text: str) -> str:
    """Remove diacritical marks and normalize text, e.g. 'Chào mừng' -> 'chao mung'."""
    nfkd = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in nfkd if not unicodedata.combining(c))
    return stripped.replace("đ", "d").replace("Đ", "D").lower().strip()


def bbox_overlaps(
    box1: tuple[int, int, int, int],
    box2: tuple[int, int, int, int],
    threshold: float = 0.35,
) -> bool:
    """Check if two bounding boxes have significant overlap (IoU or containment)."""
    l1, t1, r1, b1 = box1
    l2, t2, r2, b2 = box2

    inter_l = max(l1, l2)
    inter_t = max(t1, t2)
    inter_r = min(r1, r2)
    inter_b = min(b1, b2)

    if inter_r <= inter_l or inter_b <= inter_t:
        return False

    inter_area = (inter_r - inter_l) * (inter_b - inter_t)
    area1 = max(1, (r1 - l1) * (b1 - t1))
    area2 = max(1, (r2 - l2) * (b2 - t2))
    min_area = min(area1, area2)

    return (inter_area / min_area) >= threshold


def is_similar_to_active_translation(
    candidate_text: str,
    active_translations: Sequence[str],
    ratio_threshold: float = 0.75,
) -> bool:
    """Check if normalized candidate text matches any active translation with SequenceMatcher ratio >= ratio_threshold.

    Args:
        candidate_text: Text string detected by OCR.
        active_translations: List of currently rendered translation strings.
        ratio_threshold: Minimum similarity ratio to consider a match (default 0.75).

    Returns:
        bool: True if candidate matches an active translation closely, False otherwise.
    """
    import difflib

    if not candidate_text or not active_translations:
        return False

    norm_cand = strip_accents(candidate_text)
    if not norm_cand:
        return False

    for trans in active_translations:
        norm_tr = strip_accents(trans)
        if not norm_tr:
            continue
        if norm_cand == norm_tr:
            return True
        if difflib.SequenceMatcher(None, norm_cand, norm_tr).ratio() >= ratio_threshold:
            return True

    return False
