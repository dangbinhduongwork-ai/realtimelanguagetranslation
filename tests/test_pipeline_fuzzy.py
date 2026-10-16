"""Unit tests for pipeline fuzzy matching and static lock behavior."""

from __future__ import annotations

from unittest.mock import MagicMock
import numpy as np
import pytest

from screen_translator.capture.base import ScreenCapturer
from screen_translator.capture.frame_diff import ChangeDetector
from screen_translator.capture.settle import SettleGate
from screen_translator.models import Frame, Region, TextBlock, TranslatedBlock
from screen_translator.ocr.base import OcrEngine
from screen_translator.pipeline import Pipeline
from screen_translator.translate.base import Translator


class DummyCapturer(ScreenCapturer):
    def grab(self, region: Region | None = None) -> Frame:
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        reg = region or Region(0, 0, 100, 100)
        return Frame(image=img, region=reg, timestamp=1.0)

    def close(self) -> None:
        pass


class DummyDetector(ChangeDetector):
    def has_changed(self, current_frame, preprocessed=None) -> bool:
        return True

    def commit(self, current_frame, preprocessed=None) -> None:
        pass

    def reset(self) -> None:
        pass


class DummyOcr(OcrEngine):
    def __init__(self, blocks: list[TextBlock]) -> None:
        self.blocks = blocks

    def recognize(self, image, offset=(0, 0)) -> list[TextBlock]:
        return self.blocks


class DummyTranslator(Translator):
    def __init__(self) -> None:
        self.call_count = 0

    def translate(self, texts: list[str], source: str = "en", target: str = "vi") -> list[str]:
        self.call_count += len(texts)
        return [f"Dich: {t}" for t in texts]


def test_pipeline_fuzzy_matching_and_static_lock() -> None:
    """Verify that jittered OCR matches previous translation via fuzzy matching and locks state."""
    initial_ocr = [
        TextBlock(text="Welcome to the meeting", bbox=(10, 10, 200, 40), confidence=0.95),
    ]
    ocr_engine = DummyOcr(initial_ocr)
    translator = DummyTranslator()
    detector = DummyDetector()
    settle_gate = MagicMock(spec=SettleGate)
    settle_gate.observe.return_value = True

    pipeline = Pipeline(
        capturer=DummyCapturer(),
        detector=detector,
        ocr_engine=ocr_engine,
        translator=translator,
        settle_gate=settle_gate,
    )

    # 1. First step: text is translated
    res1 = pipeline.step()
    assert res1 is not None
    assert len(res1) == 1
    assert isinstance(res1[0], TranslatedBlock)
    assert res1[0].translated_text == "Dich: Welcome to the meeting"
    assert translator.call_count == 1

    # 2. Second step: OCR text has 1-character jitter ("Welcame to the meeting" vs "Welcome to the meeting")
    # difflib ratio is ~95% (>= 0.80) and bbox overlaps
    jitter_ocr = [
        TextBlock(text="Welcame to the meeting", bbox=(11, 10, 199, 41), confidence=0.93),
    ]
    ocr_engine.blocks = jitter_ocr

    res2 = pipeline.step()
    # Static screen: blocks_to_translate is empty, preserved_blocks has 1 item -> returns None!
    assert res2 is None
    # No additional translation API calls made!
    assert translator.call_count == 1
    # Preserved blocks remain intact in _last_emitted_blocks
    assert pipeline._last_emitted_blocks is not None
    assert len(pipeline._last_emitted_blocks) == 1
    assert pipeline._last_emitted_blocks[0].translated_text == "Dich: Welcome to the meeting"


def test_worker_translate_once_and_hold() -> None:
    """Verify that PipelineWorker stops automatically after translating a selected region."""
    from PySide6.QtWidgets import QApplication
    from screen_translator.pipeline import PipelineWorker

    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    initial_ocr = [
        TextBlock(text="Slide content to translate", bbox=(10, 10, 200, 40), confidence=0.95),
    ]
    ocr_engine = DummyOcr(initial_ocr)
    translator = DummyTranslator()
    detector = DummyDetector()
    settle_gate = MagicMock(spec=SettleGate)
    settle_gate.observe.return_value = True

    pipeline = Pipeline(
        capturer=DummyCapturer(),
        detector=detector,
        ocr_engine=ocr_engine,
        translator=translator,
        settle_gate=settle_gate,
    )

    region = Region(10, 10, 300, 200)
    worker = PipelineWorker(pipeline=pipeline, region=region)

    received_blocks = []
    worker.blocks_ready.connect(lambda b: received_blocks.append(b))

    # Trigger worker step
    worker._is_running = True
    worker._step_and_schedule()

    # Verify that translation was emitted
    assert len(received_blocks) == 1
    assert len(received_blocks[0]) == 1
    assert received_blocks[0][0].translated_text == "Dich: Slide content to translate"

    # Verify that worker loop stopped immediately (Translate Once & Hold)
    assert worker._is_running is False
