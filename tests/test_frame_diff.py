"""Unit tests for frame difference detection."""

from __future__ import annotations

from pathlib import Path
import sys

import numpy as np

# Ensure src/ is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from screen_translator.capture.frame_diff import ChangeDetector  # noqa: E402


def test_frame_diff_first_frame_and_identical() -> None:
    """Test that first frame returns True and identical subsequent frame returns False."""
    detector = ChangeDetector(threshold=0.02)
    img1 = np.zeros((200, 400, 3), dtype=np.uint8)

    # First frame must always return True to initialize baseline
    assert detector.has_changed(img1) is True

    # Identical frame must return False
    assert detector.has_changed(img1) is False

    img_copy = img1.copy()
    assert detector.has_changed(img_copy) is False


def test_frame_diff_small_vs_big_change() -> None:
    """Test small change under threshold vs big change above threshold."""
    detector = ChangeDetector(threshold=0.05)
    base = np.zeros((200, 400, 3), dtype=np.uint8)
    assert detector.has_changed(base) is True

    # Change only 10 pixels in a 200x400 image (well under 5%)
    small_change = base.copy()
    small_change[0:2, 0:5] = 255
    assert detector.has_changed(small_change) is False

    # Change 20% of image pixels
    big_change = base.copy()
    big_change[0:40, :] = 255
    assert detector.has_changed(big_change) is True


def test_frame_diff_gradual_accumulation_and_reset() -> None:
    """Test that reference frame is not updated on False, allowing gradual changes to accumulate."""
    detector = ChangeDetector(threshold=0.10)
    base = np.zeros((100, 320, 3), dtype=np.uint8)
    assert detector.has_changed(base) is True

    # 1. First small change: 4 rows out of 100 = 4% (< 10%)
    step1 = base.copy()
    step1[0:4, :] = 255
    assert detector.has_changed(step1) is False

    # 2. Second small change: cumulative 8 rows = 8% (< 10%)
    step2 = step1.copy()
    step2[4:8, :] = 255
    assert detector.has_changed(step2) is False

    # 3. Third small change: cumulative 12 rows = 12% (> 10%)
    # Should trigger True because reference was NOT updated during steps 1 and 2
    step3 = step2.copy()
    step3[8:12, :] = 255
    assert detector.has_changed(step3) is True

    # 4. Now reset() forces next frame to count as changed
    detector.reset()
    assert detector.has_changed(step3) is True


def test_frame_diff_resolution_change() -> None:
    """Test that changing frame resolution resets reference and triggers True."""
    detector = ChangeDetector(threshold=0.05)
    img_a = np.zeros((100, 200, 3), dtype=np.uint8)
    assert detector.has_changed(img_a) is True
    assert detector.has_changed(img_a) is False

    img_b = np.zeros((300, 200, 3), dtype=np.uint8)
    assert detector.has_changed(img_b) is True
