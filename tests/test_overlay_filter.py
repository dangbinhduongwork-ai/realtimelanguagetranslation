"""Unit tests for overlay self-capture prevention and block reconciliation."""

from __future__ import annotations

from screen_translator.models import TextBlock, TranslatedBlock
from screen_translator.utils.overlay_filter import bbox_overlaps, strip_accents


def test_strip_accents() -> None:
    """Verifies that Vietnamese diacritics are removed correctly."""
    assert strip_accents("Chào mừng bạn đến với Wikipedia") == "chao mung ban den voi wikipedia"
    assert strip_accents("Đại học Quốc gia") == "dai hoc quoc gia"
    assert strip_accents("Hello World") == "hello world"


def test_bbox_overlaps() -> None:
    """Verifies bounding box overlap calculation."""
    box1 = (100, 100, 300, 200)
    box2 = (105, 102, 295, 198)  # almost identical
    assert bbox_overlaps(box1, box2, threshold=0.4) is True

    box3 = (400, 400, 500, 500)  # separate
    assert bbox_overlaps(box1, box3, threshold=0.4) is False
