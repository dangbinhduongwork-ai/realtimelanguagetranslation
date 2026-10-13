"""Pipeline processing engine coordinating capture, OCR, and translation."""

from __future__ import annotations

from collections.abc import Callable
import logging
import threading
import time

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from screen_translator.capture.base import ScreenCapturer
from screen_translator.capture.frame_diff import ChangeDetector
from screen_translator.models import Frame, Region, TextBlock, TranslatedBlock
from screen_translator.ocr.base import OcrEngine
from screen_translator.ocr.grouping import group_lines
from screen_translator.translate.base import TranslationError, Translator

logger = logging.getLogger(__name__)


class Pipeline:
    """Pure Python pipeline coordinating capture -> change detection -> OCR -> grouping -> translation.

    Does NOT depend on Qt so it runs cleanly in CLI / console modes or in background threads.
    """

    def __init__(
        self,
        capturer: ScreenCapturer,
        detector: ChangeDetector,
        ocr_engine: OcrEngine,
        merge_lines: bool = True,
        max_gap_ratio: float = 0.8,
        translator: Translator | None = None,
    ) -> None:
        """Initialize pipeline with engine components.

        Args:
            capturer: ScreenCapturer implementation.
            detector: ChangeDetector implementation.
            ocr_engine: OcrEngine implementation.
            merge_lines: Whether to group vertically adjacent lines into paragraphs.
            max_gap_ratio: Maximum line spacing multiplier allowed between adjacent lines.
            translator: Optional Translator implementation (Stage 2).
        """
        self.capturer = capturer
        self.detector = detector
        self.ocr_engine = ocr_engine
        self.merge_lines = merge_lines
        self.max_gap_ratio = max_gap_ratio
        self.translator = translator
        self.last_frame: Frame | None = None
        self.last_ocr_time: float = 0.0
        self.last_translate_time: float = 0.0

    def step(
        self,
        region: Region | None = None,
    ) -> list[TranslatedBlock] | list[TextBlock] | None:
        """Execute a single capture, change detection, OCR, grouping, and translation pass.

        Returns:
            list[TranslatedBlock] | None when translator is configured.
            list[TextBlock] | None when running without translator (Stage 1 mode).
            None if frame has not changed or if translation encounters a retryable error.
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
        self.last_ocr_time = time.monotonic() - t2

        if self.merge_lines and raw_blocks:
            blocks = group_lines(raw_blocks, max_gap_ratio=self.max_gap_ratio)
        else:
            blocks = raw_blocks

        # Stage 1 mode: No translator configured
        if self.translator is None:
            logger.debug(
                "Pipeline timings (no-translate): capture=%.3fs diff=%.3fs ocr=%.3fs blocks=%d",
                t_cap,
                t_diff,
                self.last_ocr_time,
                len(blocks),
            )
            return blocks

        # Stage 2 mode: Translate detected text blocks
        if not blocks:
            self.last_translate_time = 0.0
            return []

        t3 = time.monotonic()
        try:
            texts = [b.text for b in blocks]
            translated_texts = self.translator.translate(texts)
            self.last_translate_time = time.monotonic() - t3

            translated_blocks = [
                TranslatedBlock(source=b, translated_text=tr)
                for b, tr in zip(blocks, translated_texts)
            ]

            logger.debug(
                "Pipeline timings: capture=%.3fs diff=%.3fs ocr=%.3fs translate=%.3fs blocks=%d",
                t_cap,
                t_diff,
                self.last_ocr_time,
                self.last_translate_time,
                len(translated_blocks),
            )
            return translated_blocks
        except TranslationError as exc:
            logger.warning(
                "Translation failed: %s. Resetting detector baseline and waiting 2s backoff.",
                exc,
            )
            self.detector.reset()
            time.sleep(2.0)
            return None

    def run(
        self,
        stop_event: threading.Event,
        fps: float = 2.0,
        on_result: Callable[[list[TranslatedBlock] | list[TextBlock]], None] | None = None,
        region: Region | None = None,
    ) -> None:
        """Run the pipeline loop continuously, pacing execution to the target frame rate."""
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
    """Worker QObject executing the pipeline loop inside a QThread using a single-shot QTimer."""

    blocks_ready = Signal(object)  # Emits list[TranslatedBlock] or list[TextBlock]
    status = Signal(str)           # Emits pipeline status messages
    error = Signal(str)            # Emits error descriptions

    def __init__(
        self,
        pipeline: Pipeline | None = None,
        capturer: ScreenCapturer | None = None,
        change_detector: ChangeDetector | None = None,
        ocr_engine: OcrEngine | None = None,
        translator: Translator | None = None,
        fps: float = 2.0,
        merge_lines: bool = True,
        region: Region | None = None,
        parent: QObject | None = None,
    ) -> None:
        """Initialize PipelineWorker wrapping Pipeline.

        Accepts either an assembled Pipeline instance or individual components.
        """
        super().__init__(parent)
        if pipeline is not None:
            self.pipeline = pipeline
        elif capturer is not None and change_detector is not None and ocr_engine is not None:
            self.pipeline = Pipeline(
                capturer=capturer,
                detector=change_detector,
                ocr_engine=ocr_engine,
                merge_lines=merge_lines,
                translator=translator,
            )
        else:
            raise ValueError("PipelineWorker requires either an assembled Pipeline or engine components")

        self.fps = max(0.1, float(fps))
        self.region = region
        self._timer: QTimer | None = None
        self._is_running = False

    @Slot()
    def start(self) -> None:
        """Start the continuous pipeline loop via single-shot QTimer inside the worker thread."""
        if self._is_running:
            return
        self._is_running = True
        self.status.emit("running")
        logger.info("PipelineWorker started at %.1f FPS", self.fps)

        if self._timer is None:
            self._timer = QTimer(self)
            self._timer.setSingleShot(True)
            self._timer.timeout.connect(self._step_and_schedule)

        self._step_and_schedule()

    def _step_and_schedule(self) -> None:
        """Execute one pipeline step and schedule the next iteration."""
        if not self._is_running:
            return

        t_start = time.monotonic()
        try:
            res = self.pipeline.step(region=self.region)
            if res is not None:
                self.blocks_ready.emit(res)
        except Exception as exc:
            logger.error("Error in PipelineWorker step: %s", exc, exc_info=True)
            self.error.emit(str(exc))

        if not self._is_running:
            return

        elapsed_ms = (time.monotonic() - t_start) * 1000.0
        target_interval_ms = 1000.0 / self.fps
        remaining_ms = max(0, int(round(target_interval_ms - elapsed_ms)))

        if self._timer is not None:
            self._timer.start(remaining_ms)

    @Slot()
    def stop(self) -> None:
        """Gracefully stop the timer and worker execution."""
        self._is_running = False
        if self._timer is not None:
            self._timer.stop()
        self.status.emit("stopped")
        logger.info("PipelineWorker stopped")

    @Slot(object)
    def set_region(self, region: Region | None) -> None:
        """Update capture region and reset detector baseline."""
        logger.debug("PipelineWorker region updated: %s", region)
        self.region = region
        self.pipeline.detector.reset()
