"""Unit tests for verifying module imports and data models."""

from __future__ import annotations

import importlib
from pathlib import Path
import sys

import numpy as np
import pytest

# Ensure src/ is on sys.path for direct pytest execution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from screen_translator.models import (  # noqa: E402
    Frame,
    Region,
    TextBlock,
    TranslatedBlock,
)
from screen_translator.utils import win_utils  # noqa: E402

MODULES_TO_TEST = [
    "screen_translator",
    "screen_translator.config",
    "screen_translator.logging_setup",
    "screen_translator.models",
    "screen_translator.pipeline",
    "screen_translator.app",
    "screen_translator.capture",
    "screen_translator.capture.base",
    "screen_translator.capture.mss_capturer",
    "screen_translator.capture.frame_diff",
    "screen_translator.ocr",
    "screen_translator.ocr.base",
    "screen_translator.ocr.rapidocr_engine",
    "screen_translator.ocr.grouping",
    "screen_translator.translate",
    "screen_translator.translate.base",
    "screen_translator.translate.google_translator",
    "screen_translator.translate.cache",
    "screen_translator.ui",
    "screen_translator.ui.overlay_window",
    "screen_translator.ui.region_selector",
    "screen_translator.ui.tray",
    "screen_translator.ui.hotkeys",
    "screen_translator.utils",
    "screen_translator.utils.win_utils",
]


@pytest.mark.parametrize("module_name", MODULES_TO_TEST)
def test_module_import(module_name: str) -> None:
    """Ensure every module in the project imports without syntax or import errors."""
    mod = importlib.import_module(module_name)
    assert mod is not None


def test_region_model() -> None:
    """Test Region dataclass creation, properties, and validation."""
    region = Region(left=10, top=20, width=300, height=400)
    assert region.left == 10
    assert region.top == 20
    assert region.width == 300
    assert region.height == 400
    assert region.right == 310
    assert region.bottom == 420
    assert region.as_tuple == (10, 20, 300, 400)

    # Validation: non-positive dimensions must raise ValueError
    with pytest.raises(ValueError, match="width"):
        Region(left=0, top=0, width=0, height=100)
    with pytest.raises(ValueError, match="height"):
        Region(left=0, top=0, width=100, height=-5)


def test_text_block_model() -> None:
    """Test TextBlock dataclass creation, bounding box, and confidence validation."""
    block = TextBlock(text="Hello World", bbox=(10, 20, 110, 60), confidence=0.98)
    assert block.text == "Hello World"
    assert block.bbox == (10, 20, 110, 60)
    assert block.confidence == 0.98

    # Validation: inverted bbox coordinates must raise ValueError
    with pytest.raises(ValueError, match="Invalid bbox: right"):
        TextBlock(text="Bad", bbox=(100, 20, 50, 60), confidence=0.9)
    with pytest.raises(ValueError, match="Invalid bbox: bottom"):
        TextBlock(text="Bad", bbox=(10, 80, 100, 40), confidence=0.9)

    # Validation: confidence out of range
    with pytest.raises(ValueError, match="confidence"):
        TextBlock(text="Bad", bbox=(10, 20, 100, 40), confidence=1.5)


def test_translated_block_model() -> None:
    """Test TranslatedBlock pairing."""
    src = TextBlock(text="Hello", bbox=(10, 20, 50, 40), confidence=0.95)
    translated = TranslatedBlock(source=src, translated_text="Xin chào")
    assert translated.source == src
    assert translated.translated_text == "Xin chào"


def test_frame_model() -> None:
    """Test Frame dataclass with numpy array image and region."""
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    reg = Region(left=0, top=0, width=100, height=100)
    frame = Frame(image=img, region=reg, timestamp=1700000000.0)
    assert frame.image.shape == (100, 100, 3)
    assert frame.region == reg
    assert frame.timestamp == 1700000000.0


def test_win_utils_callables() -> None:
    """Verify that win_utils public API functions exist and are callable."""
    assert callable(win_utils.enable_dpi_awareness)
    assert callable(win_utils.exclude_window_from_capture)
    assert callable(win_utils.make_click_through)


def test_app_factories() -> None:
    """Verify that component factories instantiate pipeline components."""
    from screen_translator.app import (
        create_capturer,
        create_detector,
        create_ocr_engine,
        create_pipeline,
    )
    from screen_translator.config import load_config

    config = load_config()
    capturer = create_capturer(config)
    detector = create_detector(config)
    ocr_engine = create_ocr_engine(config)
    pipeline = create_pipeline(config)

    assert capturer is not None
    assert detector is not None
    assert ocr_engine is not None
    assert pipeline is not None
