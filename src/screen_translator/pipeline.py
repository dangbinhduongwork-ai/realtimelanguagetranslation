"""Pipeline processing engine coordinating capture, OCR, and translation."""

from __future__ import annotations

from collections.abc import Callable
import difflib
import logging
import threading
import time

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from screen_translator.capture.base import ScreenCapturer
from screen_translator.capture.frame_diff import ChangeDetector
from screen_translator.capture.settle import SettleGate
from screen_translator.models import Frame, Region, TextBlock, TranslatedBlock
from screen_translator.ocr.base import OcrEngine
from screen_translator.ocr.grouping import group_lines
from screen_translator.translate.base import TranslationError, Translator
from screen_translator.translate.filters import VIETNAMESE_DIACRITICS, needs_translation
from screen_translator.utils.loop_watchdog import LoopWatchdog
from screen_translator.utils.overlay_filter import (
    bbox_overlaps,
    is_similar_to_active_translation,
    strip_accents,
)
from screen_translator.utils.stabilization import blocks_equivalent

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
        settle_ms: int = 300,
        max_wait_ms: int = 1500,
        motion_detector: ChangeDetector | None = None,
        settle_gate: SettleGate | None = None,
        watchdog: LoopWatchdog | None = None,
        self_filter_ratio: float = 0.75,
    ) -> None:
        """Initialize pipeline with engine components.

        Args:
            capturer: ScreenCapturer implementation.
            detector: ChangeDetector implementation (baseline frame diff).
            ocr_engine: OcrEngine implementation.
            merge_lines: Whether to group vertically adjacent lines into paragraphs.
            max_gap_ratio: Maximum line spacing multiplier allowed between adjacent lines.
            translator: Optional Translator implementation (Stage 2).
            settle_ms: Stillness duration (ms) before running OCR on changed screen.
            max_wait_ms: Maximum duration (ms) to debounce continuous screen motion.
            motion_detector: Optional ChangeDetector in rolling mode.
            settle_gate: Optional SettleGate instance.
            watchdog: Optional LoopWatchdog instance to detect/throttle feedback loops.
            self_filter_ratio: Similarity ratio threshold to drop/preserve active overlay text.
        """
        self.capturer = capturer
        self.detector = detector
        self.ocr_engine = ocr_engine
        self.merge_lines = merge_lines
        self.max_gap_ratio = max_gap_ratio
        self.translator = translator
        self.self_filter_ratio = float(self_filter_ratio)
        self.watchdog = watchdog or LoopWatchdog()

        self.motion_detector = motion_detector or ChangeDetector(
            threshold=detector.threshold, rolling=True
        )
        self.settle_gate = settle_gate or SettleGate(
            settle_ms=settle_ms, max_wait_ms=max_wait_ms
        )

        self.last_frame: Frame | None = None
        self.last_ocr_time: float = 0.0
        self.last_group_time: float = 0.0
        self.last_translate_time: float = 0.0
        self._last_emitted_blocks: list[TranslatedBlock] | list[TextBlock] | None = None

    def reset(self) -> None:
        """Reset change detector baseline, motion history, settle gate, and stabilization cache."""
        self.detector.reset()
        self.motion_detector.reset()
        self.settle_gate.reset()
        self.watchdog.reset()
        self._last_emitted_blocks = None
        logger.debug("Pipeline state completely reset")

    def step(
        self,
        region: Region | None = None,
    ) -> list[TranslatedBlock] | list[TextBlock] | None:
        """Execute a single capture, change detection, OCR, grouping, and translation pass.

        Returns:
            list[TranslatedBlock] | None when translator is configured.
            list[TextBlock] | None when running without translator (Stage 1 mode).
            None if frame has not changed, screen has not settled, or error occurred.
        """
        t0 = time.monotonic()
        frame = self.capturer.grab(region)
        t_cap = time.monotonic() - t0
        self.last_frame = frame

        t1 = time.monotonic()
        thumb = self.detector.preprocess(frame.image)
        changed = self.detector.has_changed(frame.image, preprocessed=thumb)
        moving = self.motion_detector.has_changed(frame.image, preprocessed=thumb)
        t_diff = time.monotonic() - t1

        ready = self.settle_gate.observe(changed=changed, moving=moving)
        if not ready:
            logger.debug("Settle gate waiting (changed=%s, moving=%s)", changed, moving)
            return None

        # Check loop watchdog before OCR
        cooldown = self.watchdog.record_run()
        if cooldown > 0:
            logger.debug("Loop watchdog active: cooling down for %.2fs", cooldown)
            time.sleep(cooldown)

        # Screen settled: commit baseline reference to current frame
        self.detector.commit(frame.image, preprocessed=thumb)

        t2 = time.monotonic()
        offset = (frame.region.left, frame.region.top)
        raw_blocks = self.ocr_engine.recognize(frame.image, offset=offset)
        self.last_ocr_time = time.monotonic() - t2

        t_grp_start = time.monotonic()
        if self.merge_lines and raw_blocks:
            blocks = group_lines(raw_blocks, max_gap_ratio=self.max_gap_ratio)
        else:
            blocks = raw_blocks
        self.last_group_time = time.monotonic() - t_grp_start

        # Stage 1 mode: No translator configured
        if self.translator is None:
            t_ocr_ms = int(round(self.last_ocr_time * 1000.0))
            t_group_ms = int(round(self.last_group_time * 1000.0))
            logger.info(
                "frame: ocr=%dms group=%dms translate=0ms api_calls=0 cache_hits=0 blocks=%d",
                t_ocr_ms,
                t_group_ms,
                len(blocks),
            )
            if self._last_emitted_blocks is not None and blocks_equivalent(
                self._last_emitted_blocks, blocks, tol_px=4
            ):
                logger.debug("Result stabilized (equivalent to last emitted blocks, skipping emission)")
                return None

            self._last_emitted_blocks = blocks
            return blocks

        # Stage 2 mode: Translate detected text blocks
        if not blocks:
            self.last_translate_time = 0.0
            if self._last_emitted_blocks == []:
                return None
            self._last_emitted_blocks = []
            return []

        t3 = time.monotonic()
        try:
            prev_emitted = (
                self._last_emitted_blocks
                if isinstance(self._last_emitted_blocks, list)
                else None
            )

            active_trans = [
                p.translated_text
                for p in (prev_emitted or [])
                if isinstance(p, TranslatedBlock)
            ]

            preserved_blocks: list[TranslatedBlock] = []
            blocks_to_translate: list[TextBlock] = []

            for b in blocks:
                # 1. Skip if text already contains Vietnamese diacritics (overlay text or already Vietnamese)
                if any(char in VIETNAMESE_DIACRITICS for char in b.text):
                    if prev_emitted:
                        matched_p = next(
                            (p for p in prev_emitted if isinstance(p, TranslatedBlock) and bbox_overlaps(b.bbox, p.source.bbox)),
                            None,
                        )
                        if matched_p is not None and matched_p not in preserved_blocks:
                            preserved_blocks.append(matched_p)
                    continue

                # 2. Check if normalized text matches active translation closely (feedback loop prevention)
                if is_similar_to_active_translation(b.text, active_trans, ratio_threshold=self.self_filter_ratio):
                    if prev_emitted:
                        matched_p = next(
                            (p for p in prev_emitted if isinstance(p, TranslatedBlock) and bbox_overlaps(b.bbox, p.source.bbox)),
                            None,
                        )
                        if matched_p is not None and matched_p not in preserved_blocks:
                            preserved_blocks.append(matched_p)
                    continue

                # 3. Skip if text does not need translation (numbers, symbols, punctuation)
                if not needs_translation(b.text, source_lang="en"):
                    continue

                # 4. Check if this block corresponds to an already active overlay translation via fuzzy matching
                matched_prev: TranslatedBlock | None = None
                if prev_emitted:
                    norm_b = strip_accents(b.text)
                    for p in prev_emitted:
                        if isinstance(p, TranslatedBlock) and bbox_overlaps(b.bbox, p.source.bbox):
                            norm_src = strip_accents(p.source.text)
                            norm_tr = strip_accents(p.translated_text)
                            ratio_src = difflib.SequenceMatcher(None, norm_b, norm_src).ratio()
                            ratio_tr = difflib.SequenceMatcher(None, norm_b, norm_tr).ratio()
                            if ratio_src >= 0.80 or ratio_tr >= 0.80:
                                matched_prev = p
                                break

                if matched_prev is not None:
                    if matched_prev not in preserved_blocks:
                        preserved_blocks.append(matched_prev)
                else:
                    blocks_to_translate.append(b)

            # Lock state when no new blocks require translation: preserve existing overlay and avoid repainting
            if not blocks_to_translate and preserved_blocks:
                logger.debug(
                    "Static screen: %d preserved blocks remain stable; skipping re-emission",
                    len(preserved_blocks),
                )
                preserved_blocks.sort(key=lambda b: (b.source.bbox[1], b.source.bbox[0]))
                self._last_emitted_blocks = preserved_blocks
                self.detector.commit(frame.image, preprocessed=thumb)
                return None

            hits_before = 0
            if hasattr(self.translator, "cache") and hasattr(self.translator.cache, "hits"):
                hits_before = self.translator.cache.hits

            newly_translated: list[TranslatedBlock] = []
            if blocks_to_translate:
                texts = [b.text for b in blocks_to_translate]
                translated_texts = self.translator.translate(texts)
                newly_translated = [
                    TranslatedBlock(source=b, translated_text=tr)
                    for b, tr in zip(blocks_to_translate, translated_texts)
                ]

            self.last_translate_time = time.monotonic() - t3
            translated_blocks = preserved_blocks + newly_translated
            translated_blocks.sort(key=lambda b: (b.source.bbox[1], b.source.bbox[0]))

            # Commit baseline after translation to ensure next frames have diff = 0
            self.detector.commit(frame.image, preprocessed=thumb)

            hits_after = 0
            if hasattr(self.translator, "cache") and hasattr(self.translator.cache, "hits"):
                hits_after = self.translator.cache.hits
            cache_hits = max(0, hits_after - hits_before)

            api_calls = 0
            if hasattr(self.translator, "get_and_reset_api_calls"):
                api_calls = self.translator.get_and_reset_api_calls()

            t_ocr_ms = int(round(self.last_ocr_time * 1000.0))
            t_group_ms = int(round(self.last_group_time * 1000.0))
            t_trans_ms = int(round(self.last_translate_time * 1000.0))

            logger.info(
                "frame: ocr=%dms group=%dms translate=%dms api_calls=%d cache_hits=%d blocks=%d",
                t_ocr_ms,
                t_group_ms,
                t_trans_ms,
                api_calls,
                cache_hits,
                len(translated_blocks),
            )

            # Result stabilization to eliminate micro-jitter and flicker
            if self._last_emitted_blocks is not None and blocks_equivalent(
                self._last_emitted_blocks, translated_blocks, tol_px=4
            ):
                logger.debug("Result stabilized (equivalent to last emitted blocks, skipping emission)")
                return None

            self._last_emitted_blocks = translated_blocks
            return translated_blocks
        except TranslationError as exc:
            logger.warning(
                "Translation failed: %s. Resetting detector baseline and waiting 2s backoff.",
                exc,
            )
            self.reset()
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
        """Initialize PipelineWorker wrapping Pipeline."""
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
        res = None
        try:
            res = self.pipeline.step(region=self.region)
            if res is not None:
                self.blocks_ready.emit(res)
                # Translate Once & Hold:
                # When a region is selected, after getting the translated blocks,
                # hold the result on screen and stop the worker loop immediately!
                if self.region is not None:
                    logger.info(
                        "Translate Once & Hold: Completed translation for selected region (%d blocks), stopping worker loop.",
                        len(res),
                    )
                    self.stop()
                    return
        except Exception as exc:
            logger.error("Error in PipelineWorker step: %s", exc, exc_info=True)
            self.error.emit(str(exc))

        if not self._is_running:
            return

        # If region is set and waiting for screen to settle, check quickly (50ms) to deliver translation fast
        if self.region is not None and res is None:
            if self._timer is not None:
                self._timer.start(50)
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
        self.pipeline.reset()
