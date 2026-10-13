"""Unit tests for text translation filter logic."""

from __future__ import annotations

from pathlib import Path
import sys

# Ensure src/ is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from screen_translator.translate.filters import needs_translation  # noqa: E402


def test_needs_translation_valid_english() -> None:
    """Test valid English words and phrases return True."""
    assert needs_translation("Hello world") is True
    assert needs_translation("OK") is True
    assert needs_translation("Status: Active") is True
    assert needs_translation("Click here to proceed.") is True


def test_needs_translation_short_or_symbols() -> None:
    """Test strings with fewer than 2 letters return False."""
    assert needs_translation("") is False
    assert needs_translation("   ") is False
    assert needs_translation("A") is False
    assert needs_translation("12345") is False
    assert needs_translation("---") is False
    assert needs_translation("!@#$%^&*()") is False
    assert needs_translation("12.34%") is False
    assert needs_translation("A 123") is False  # only 1 letter


def test_needs_translation_vietnamese_text() -> None:
    """Test strings containing Vietnamese diacritics return False."""
    assert needs_translation("Xin chào") is False
    assert needs_translation("Cộng hòa xã hội chủ nghĩa Việt Nam") is False
    assert needs_translation("Đang xử lý dữ liệu") is False
    assert needs_translation("Slide thuyết trình") is False
