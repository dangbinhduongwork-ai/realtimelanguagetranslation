"""Unit tests for blocks_equivalent stabilization."""

from __future__ import annotations

from pathlib import Path
import sys

# Ensure src/ is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from screen_translator.models import TextBlock, TranslatedBlock  # noqa: E402
from screen_translator.utils.stabilization import blocks_equivalent  # noqa: E402


def test_identical_blocks() -> None:
    """Test identical TextBlock and TranslatedBlock sequences."""
    b1 = [TextBlock(text="Hello", bbox=(10, 20, 100, 50), confidence=0.9)]
    b2 = [TextBlock(text="Hello", bbox=(10, 20, 100, 50), confidence=0.9)]
    assert blocks_equivalent(b1, b2, tol_px=4) is True

    tr1 = [TranslatedBlock(source=b1[0], translated_text="Xin chào")]
    tr2 = [TranslatedBlock(source=b2[0], translated_text="Xin chào")]
    assert blocks_equivalent(tr1, tr2, tol_px=4) is True


def test_jitter_within_tolerance() -> None:
    """Test slight bounding box coordinate jitter within tol_px."""
    b1 = [TextBlock(text="Hello", bbox=(10, 20, 100, 50), confidence=0.9)]
    # Coordinates shifted by 2, -1, 3, 4 px (all <= 4)
    b2 = [TextBlock(text="Hello", bbox=(12, 19, 103, 54), confidence=0.9)]
    assert blocks_equivalent(b1, b2, tol_px=4) is True


def test_bbox_moved_beyond_tolerance() -> None:
    """Test coordinate shift exceeding tol_px returns False."""
    b1 = [TextBlock(text="Hello", bbox=(10, 20, 100, 50), confidence=0.9)]
    # X coordinate shifted by 5 px (> 4)
    b2 = [TextBlock(text="Hello", bbox=(15, 20, 100, 50), confidence=0.9)]
    assert blocks_equivalent(b1, b2, tol_px=4) is False


def test_text_change() -> None:
    """Test text change returns False."""
    b1 = [TextBlock(text="Hello", bbox=(10, 20, 100, 50), confidence=0.9)]
    b2 = [TextBlock(text="World", bbox=(10, 20, 100, 50), confidence=0.9)]
    assert blocks_equivalent(b1, b2, tol_px=4) is False

    tr1 = [TranslatedBlock(source=b1[0], translated_text="Xin chào")]
    tr2 = [TranslatedBlock(source=b1[0], translated_text="Thế giới")]
    assert blocks_equivalent(tr1, tr2, tol_px=4) is False


def test_count_change() -> None:
    """Test difference in block count returns False."""
    b1 = [TextBlock(text="Hello", bbox=(10, 20, 100, 50), confidence=0.9)]
    b2 = [
        TextBlock(text="Hello", bbox=(10, 20, 100, 50), confidence=0.9),
        TextBlock(text="World", bbox=(10, 60, 100, 90), confidence=0.9),
    ]
    assert blocks_equivalent(b1, b2, tol_px=4) is False
    assert blocks_equivalent([], b1, tol_px=4) is False


def test_none_and_empty_sequences() -> None:
    """Test handling of None and empty sequences."""
    assert blocks_equivalent(None, None, tol_px=4) is True
    assert blocks_equivalent([], [], tol_px=4) is True
    b1 = [TextBlock(text="Hello", bbox=(10, 20, 100, 50), confidence=0.9)]
    assert blocks_equivalent(b1, None, tol_px=4) is False
    assert blocks_equivalent(None, b1, tol_px=4) is False
