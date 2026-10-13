"""Pipeline worker executing the capture-diff-OCR-translate pipeline in a QThread."""

from __future__ import annotations

import logging
from PySide6.QtCore import QObject, Signal, Slot

from screen_translator.capture.base import ScreenCapturer
from screen_translator.capture.frame_diff import ChangeDetector
from screen_translator.models import Region
from screen_translator.ocr.base import OcrEngine
from screen_translator.translate.base import Translator

logger = logging.getLogger(__name__)


class PipelineWorker(QObject):
    """Worker QObject responsible for executing the screen processing loop."""

    # Qt Signals: communication with the UI thread occurs strictly via signals/slots
    blocks_ready = Signal(list)  # Emits list[TranslatedBlock]
    status = Signal(str)         # Emits pipeline status messages
    error = Signal(str)          # Emits error descriptions

    def __init__(
        self,
        capturer: ScreenCapturer,
        change_detector: ChangeDetector,
        ocr_engine: OcrEngine,
        translator: Translator,
        fps: int = 2,
        merge_lines: bool = True,
        parent: QObject | None = None,
    ) -> None:
        """Initialize PipelineWorker with injected components.

        Args:
            capturer: Concrete ScreenCapturer instance.
            change_detector: Concrete ChangeDetector instance.
            ocr_engine: Concrete OcrEngine instance.
            translator: Concrete Translator instance.
            fps: Target capture loop frequency in frames per second.
            merge_lines: Whether to group adjacent lines into paragraphs.
            parent: Optional parent QObject.
        """
        super().__init__(parent)
        raise NotImplementedError("PipelineWorker is scheduled for Stage 1")

    @Slot()
    def start(self) -> None:
        """Start the continuous pipeline capture loop."""
        raise NotImplementedError("PipelineWorker is scheduled for Stage 1")

    @Slot()
    def stop(self) -> None:
        """Stop the continuous pipeline capture loop gracefully."""
        raise NotImplementedError("PipelineWorker is scheduled for Stage 1")

    @Slot(object)
    def set_region(self, region: Region | None) -> None:
        """Dynamically update the screen region to capture and translate.

        Args:
            region: Region coordinates or None for full screen/monitor capture.
        """
        raise NotImplementedError("PipelineWorker is scheduled for Stage 1")
