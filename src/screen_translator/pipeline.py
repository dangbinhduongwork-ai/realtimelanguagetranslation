"""Pipeline processing engine and worker coordination."""

from __future__ import annotations

from collections.abc import Callable
import logging
import threading
import time

from PySide6.QtCore import QObject, Signal, Slot

from screen_translator.capture.base import ScreenCapturer
from screen_translator.capture.frame_diff import ChangeDetector
from screen_translator.models import Frame, Region, TextBlock
from screen_translator.ocr.base import OcrEngine
from screen_translator.ocr.grouping import group_lines
from screen_translator.translate.base import Translator

logger = logging.getLogger(__name__)


class Pipeline:
    """Pure Python pipeline coordinating capture -> change detection -> OCR -> line grouping.

    Does NOT depend on Qt so it can run cleanly in CLI / console modes or in background threads.
    """

    def __init__(
        self,
        capturer: ScreenCapturer,
        detector: ChangeDetector,
        ocr_engine: OcrEngine,
        merge_lines: bool = True,
        max_gap_ratio: float = 0.8,
    ) -> None:
        """Initialize the pipeline with engine components.

        Args:
            capturer: ScreenCapturer implementation.
            detector: ChangeDetector implementation.
            ocr_engine: OcrEngine implementation.
            merge_lines: Whether to group vertically adjacent lines into paragraphs.
            max_gap_ratio: Maximum line spacing multiplier allowed between adjacent lines.
        """
        self.capturer = capturer
        self.detector = detector
        self.ocr_engine = ocr_engine
        self.merge_lines = merge_lines
        self.max_gap_ratio = max_gap_ratio
        self.last_frame: Frame | None = None

    def step(self, region: Region | None = None) -> list[TextBlock] | None:
        """Execute a single capture, change detection, OCR, and grouping pass.

        Args:
            region: Optional screen region. If None, captures default monitor.

        Returns:
            list[TextBlock] | None: None when frame did not change; otherwise list of TextBlocks.
        """
        t0 = time.monotonic()
        frame = self.capturer.grab(region)
        t_cap = time.monotonic() - t0
        self.last_frame = frame

        t1 = time.monotonic()
        changed = self.detector.has_changed(frame.image)
        t_diff = time.monotonic() - t1

        if not changed:
            logger.debug("no change (capture=%.3fs, diff=%.3fs)", t_cap, t_diff)
            return None

        t2 = time.monotonic()
        offset = (frame.region.left, frame.region.top)
        raw_blocks = self.ocr_engine.recognize(frame.image, offset=offset)
        t_ocr = time.monotonic() - t2

        if self.merge_lines and raw_blocks:
            blocks = group_lines(raw_blocks, max_gap_ratio=self.max_gap_ratio)
        else:
            blocks = raw_blocks

        total_time = time.monotonic() - t0
        logger.debug(
            "Pipeline timings: capture=%.3fs, diff=%.3fs, ocr=%.3fs (total=%.3fs, blocks=%d)",
            t_cap,
            t_diff,
            t_ocr,
            total_time,
            len(blocks),
        )
        return blocks

    def run(
        self,
        stop_event: threading.Event,
        fps: float = 2.0,
        on_result: Callable[[list[TextBlock]], None] | None = None,
        region: Region | None = None,
    ) -> None:
        """Run the pipeline continuously, pacing execution to the target frame rate.

        Args:
            stop_event: threading.Event checked on every iteration to exit cleanly.
            fps: Target iterations per second.
            on_result: Callback receiving detected text blocks when screen content changes.
            region: Optional screen region coordinates.
        """
        interval = 1.0 / max(0.1, fps)
        while not stop_event.is_set():
            t_start = time.monotonic()
            try:
                blocks = self.step(region)
                if blocks is not None and on_result is not None:
                    on_result(blocks)
            except Exception as exc:
                logger.error("Error during pipeline iteration: %s", exc, exc_info=True)

            elapsed = time.monotonic() - t_start
            sleep_time = interval - elapsed
            if sleep_time > 0:
                stop_event.wait(sleep_time)


class PipelineWorker(QObject):
    """Worker QObject responsible for executing the screen processing loop in a QThread.

    Stub maintained for Stage 3 Qt integration.
    """

    blocks_ready = Signal(list)
    status = Signal(str)
    error = Signal(str)

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
        super().__init__(parent)
        raise NotImplementedError("PipelineWorker is scheduled for Stage 3")

    @Slot()
    def start(self) -> None:
        raise NotImplementedError("PipelineWorker is scheduled for Stage 3")

    @Slot()
    def stop(self) -> None:
        raise NotImplementedError("PipelineWorker is scheduled for Stage 3")

    @Slot(object)
    def set_region(self, region: Region | None) -> None:
        raise NotImplementedError("PipelineWorker is scheduled for Stage 3")
