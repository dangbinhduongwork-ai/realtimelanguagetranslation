"""Unit tests for line grouping into paragraphs."""

from __future__ import annotations

from pathlib import Path
import sys

# Ensure src/ is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from screen_translator.models import TextBlock  # noqa: E402
from screen_translator.ocr.grouping import group_lines  # noqa: E402


def test_stacked_lines_merge() -> None:
    """Test that 3 vertically stacked lines merge into a single paragraph."""
    line1 = TextBlock(text="First line of paragraph", bbox=(10, 10, 200, 30), confidence=0.95)
    line2 = TextBlock(text="second line follows here", bbox=(10, 35, 200, 55), confidence=0.90)
    line3 = TextBlock(text="third line finishes thought", bbox=(10, 60, 200, 80), confidence=0.85)

    result = group_lines([line1, line2, line3], max_gap_ratio=0.8)

    assert len(result) == 1
    merged = result[0]
    assert merged.text == "First line of paragraph second line follows here third line finishes thought"
    assert merged.bbox == (10, 10, 200, 80)
    assert round(merged.confidence, 2) == 0.90


def test_two_columns_do_not_merge() -> None:
    """Test that lines belonging to different side-by-side columns do not merge."""
    # Column 1
    col1_l1 = TextBlock(text="Col 1 Top", bbox=(20, 50, 150, 70), confidence=0.9)
    col1_l2 = TextBlock(text="Col 1 Bottom", bbox=(20, 75, 150, 95), confidence=0.9)
    # Column 2
    col2_l1 = TextBlock(text="Col 2 Top", bbox=(250, 50, 380, 70), confidence=0.9)
    col2_l2 = TextBlock(text="Col 2 Bottom", bbox=(250, 75, 380, 95), confidence=0.9)

    result = group_lines([col1_l1, col2_l1, col1_l2, col2_l2], max_gap_ratio=0.8)

    assert len(result) == 2
    # Verify column 1 merged with column 1 and column 2 merged with column 2
    col1_text = next((r.text for r in result if "Col 1" in r.text), "")
    col2_text = next((r.text for r in result if "Col 2" in r.text), "")
    assert col1_text == "Col 1 Top Col 1 Bottom"
    assert col2_text == "Col 2 Top Col 2 Bottom"


def test_far_gap_does_not_merge() -> None:
    """Test that two lines separated by a vertical gap exceeding max_gap_ratio do not merge."""
    line1 = TextBlock(text="Heading title", bbox=(50, 20, 250, 40), confidence=0.95)
    # Height = 20. Vertical gap = 90 - 40 = 50. Ratio = 50/20 = 2.5 > 0.8
    line2 = TextBlock(text="Body paragraph after large gap", bbox=(50, 90, 250, 110), confidence=0.95)

    result = group_lines([line1, line2], max_gap_ratio=0.8)
    assert len(result) == 2
    assert result[0].text == "Heading title"
    assert result[1].text == "Body paragraph after large gap"


def test_font_size_mismatch_does_not_merge() -> None:
    """Test that lines with significantly different heights (font sizes) do not merge."""
    # Large headline: height = 60 (20 to 80)
    headline = TextBlock(text="HUGE HEADLINE", bbox=(30, 20, 300, 80), confidence=0.98)
    # Small body text directly below: height = 18 (85 to 103). Ratio = 60 / 18 = 3.33 > 1.4
    body = TextBlock(text="Small subtitle underneath", bbox=(30, 85, 300, 103), confidence=0.92)

    result = group_lines([headline, body], max_gap_ratio=0.8)
    assert len(result) == 2
    assert result[0].text == "HUGE HEADLINE"
    assert result[1].text == "Small subtitle underneath"


def test_reading_order_is_correct() -> None:
    """Test that input lines given out of order are sorted properly in reading order."""
    para_bottom = TextBlock(text="Paragraph 2 Line 2", bbox=(10, 140, 200, 160), confidence=0.9)
    para_top = TextBlock(text="Paragraph 1 Line 1", bbox=(10, 20, 200, 40), confidence=0.9)
    para_mid = TextBlock(text="Paragraph 1 Line 2", bbox=(10, 45, 200, 65), confidence=0.9)

    result = group_lines([para_bottom, para_top, para_mid], max_gap_ratio=0.8)
    assert len(result) == 2
    assert result[0].text == "Paragraph 1 Line 1 Paragraph 1 Line 2"
    assert result[1].text == "Paragraph 2 Line 2"
