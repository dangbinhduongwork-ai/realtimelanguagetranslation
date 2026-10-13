"""Unit tests for adaptive upscale helpers."""

from __future__ import annotations

from pathlib import Path
import sys

import numpy as np

# Ensure src/ is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from screen_translator.models import TextBlock  # noqa: E402
from screen_translator.ocr.upscale import (  # noqa: E402
    calculate_mean_confidence,
    calculate_median_line_height,
    remap_blocks_to_screen,
    scale_image,
)


def test_calculate_median_line_height() -> None:
    """Test median line height computation."""
    assert calculate_median_line_height([]) == 0.0

    blocks = [
        TextBlock(text="a", bbox=(0, 0, 10, 12), confidence=0.8),  # h = 12
        TextBlock(text="b", bbox=(0, 0, 10, 20), confidence=0.8),  # h = 20
        TextBlock(text="c", bbox=(0, 0, 10, 16), confidence=0.8),  # h = 16
    ]
    # Median of [12, 16, 20] is 16.0
    assert calculate_median_line_height(blocks) == 16.0


def test_calculate_mean_confidence() -> None:
    """Test average confidence calculation."""
    assert calculate_mean_confidence([]) == 0.0

    blocks = [
        TextBlock(text="a", bbox=(0, 0, 10, 10), confidence=0.7),
        TextBlock(text="b", bbox=(0, 0, 10, 10), confidence=0.9),
    ]
    assert abs(calculate_mean_confidence(blocks) - 0.8) < 1e-4


def test_scale_image() -> None:
    """Test image upscaling dimensions."""
    img = np.zeros((100, 200, 3), dtype=np.uint8)

    # Factor 1.0 returns original object
    assert scale_image(img, 1.0) is img

    # Factor 2.0 scales to (200, 400)
    scaled = scale_image(img, 2.0)
    assert scaled.shape == (200, 400, 3)


def test_remap_blocks_to_screen() -> None:
    """Test mapping 2x upscaled blocks back to unscaled screen coordinates with offset."""
    blocks = [
        TextBlock(text="Title", bbox=(20, 40, 200, 80), confidence=0.95),
    ]

    # Factor = 2.0, Offset = (100, 200)
    # Expected: (20/2 + 100, 40/2 + 200, 200/2 + 100, 80/2 + 200) = (110, 220, 200, 240)
    remapped = remap_blocks_to_screen(blocks, factor=2.0, offset=(100, 200))

    assert len(remapped) == 1
    assert remapped[0].text == "Title"
    assert remapped[0].bbox == (110, 220, 200, 240)
    assert remapped[0].confidence == 0.95
