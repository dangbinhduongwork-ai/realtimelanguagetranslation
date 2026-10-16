"""Unit tests for self-text filter preventing feedback loops."""

from __future__ import annotations

from screen_translator.utils.overlay_filter import is_similar_to_active_translation, strip_accents


def test_self_text_filter_exact_and_near_match() -> None:
    """Verifies that OCR text matching active translations (>= 0.75 ratio) is flagged."""
    active_translations = [
        "Chào mừng bạn đến với Wikipedia, bộ bách khoa toàn thư mở",
        "Trang chính hôm nay có gì mới",
    ]

    # Exact match (even with accents stripped)
    assert is_similar_to_active_translation(
        "Chào mừng bạn đến với Wikipedia, bộ bách khoa toàn thư mở",
        active_translations,
        ratio_threshold=0.75,
    ) is True

    # OCR missed diacritics
    assert is_similar_to_active_translation(
        "Chao mung ban den voi Wikipedia, bo bach khoa toan thu mo",
        active_translations,
        ratio_threshold=0.75,
    ) is True

    # Small OCR typo/noise (ratio still high >= 0.75)
    assert is_similar_to_active_translation(
        "Chao mung ban den voi Wikipedia, bo bach khoa toan thu",
        active_translations,
        ratio_threshold=0.75,
    ) is True

    # Completely different English text
    assert is_similar_to_active_translation(
        "Welcome to the free encyclopedia that anyone can edit.",
        active_translations,
        ratio_threshold=0.75,
    ) is False


def test_self_text_filter_empty_inputs() -> None:
    """Verifies that empty candidates or empty active lists return False."""
    assert is_similar_to_active_translation("", ["Chào mừng"]) is False
    assert is_similar_to_active_translation("Hello", []) is False
