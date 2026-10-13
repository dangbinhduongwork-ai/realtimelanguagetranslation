"""Integration test for RapidOCR on a synthetic image."""

from __future__ import annotations

from pathlib import Path
import sys

import cv2
import numpy as np
import pytest

# Ensure src/ is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from screen_translator.ocr.rapidocr_engine import RapidOcrEngine  # noqa: E402


@pytest.mark.integration
def test_rapidocr_hello_world() -> None:
    """Draw 'Hello World' with cv2.putText and assert RapidOCR detects 'hello'."""
    # White background image
    img = np.full((160, 500, 3), 255, dtype=np.uint8)

    # Render high-contrast dark text
    cv2.putText(
        img,
        "Hello World",
        (40, 105),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.8,
        (0, 0, 0),
        3,
        cv2.LINE_AA,
    )

    engine = RapidOcrEngine(min_confidence=0.5)
    blocks = engine.recognize(img, offset=(100, 200))

    assert len(blocks) > 0, "RapidOCR should recognize at least one block from synthetic image"

    full_detected_text = " ".join(b.text for b in blocks).lower()
    assert "hello" in full_detected_text, f"Expected 'hello' in '{full_detected_text}'"

    # Verify that offset is reflected in the resulting screen bounding boxes
    for b in blocks:
        assert b.bbox[0] >= 100
        assert b.bbox[1] >= 200


@pytest.mark.integration
def test_rapidocr_small_text_auto_upscale() -> None:
    """Test that small text (fontScale ~0.45) is recognized in auto upscale mode."""
    img = np.full((120, 450, 3), 255, dtype=np.uint8)

    cv2.putText(
        img,
        "Quarterly financial report summary",
        (20, 60),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        (0, 0, 0),
        1,
        cv2.LINE_AA,
    )

    engine = RapidOcrEngine(min_confidence=0.4, upscale="auto", small_text_px=16)
    blocks = engine.recognize(img, offset=(50, 80))

    assert len(blocks) > 0, "RapidOCR should recognize small text using adaptive upscale"
    full_text = " ".join(b.text for b in blocks).lower()
    assert any(w in full_text for w in ["quarterly", "financial", "report", "summary"]), (
        f"Expected keywords in detected text: '{full_text}'"
    )

    for b in blocks:
        assert b.bbox[0] >= 50
        assert b.bbox[1] >= 80

