"""Application component factories, wiring, and GUI overlay execution."""

from __future__ import annotations

import argparse
import logging
import signal
import sys

from PySide6.QtCore import QThread, QTimer, Qt
from PySide6.QtWidgets import QApplication

from screen_translator.capture.base import ScreenCapturer
from screen_translator.capture.frame_diff import ChangeDetector
from screen_translator.capture.mss_capturer import MssCapturer
from screen_translator.config import AppConfig
from screen_translator.logging_setup import setup_logging
from screen_translator.models import Region
from screen_translator.ocr.base import OcrEngine
from screen_translator.ocr.rapidocr_engine import RapidOcrEngine
from screen_translator.pipeline import Pipeline, PipelineWorker
from screen_translator.translate import build_translator
from screen_translator.translate.base import Translator
from screen_translator.ui.overlay_window import OverlayWindow
from screen_translator.utils.win_utils import enable_dpi_awareness

logger = logging.getLogger(__name__)


def create_capturer(config: AppConfig, monitor: int | None = None) -> ScreenCapturer:
    """Create configured ScreenCapturer engine instance."""
    mon_idx = monitor if monitor is not None else config.capture.monitor
    logger.debug("Creating MssCapturer for monitor %d", mon_idx)
    return MssCapturer(monitor_index=mon_idx)


def create_detector(config: AppConfig) -> ChangeDetector:
    """Create configured ChangeDetector engine instance."""
    logger.debug("Creating ChangeDetector with threshold %.4f", config.change_detection.threshold)
    return ChangeDetector(threshold=config.change_detection.threshold)


def create_ocr_engine(config: AppConfig) -> OcrEngine:
    """Create configured OcrEngine instance."""
    if config.ocr.engine == "rapidocr":
        logger.debug("Creating RapidOcrEngine (min_confidence=%.2f)", config.ocr.min_confidence)
        return RapidOcrEngine(min_confidence=config.ocr.min_confidence)
    raise ValueError(f"Unknown OCR engine: {config.ocr.engine}")


def create_translator(config: AppConfig) -> Translator:
    """Create configured Translator instance with LRU cache."""
    logger.debug("Creating Translator for provider '%s'", config.translate.provider)
    return build_translator(config.translate)


def create_pipeline(
    config: AppConfig,
    monitor: int | None = None,
    translate: bool = True,
) -> Pipeline:
    """Create complete Pipeline instance from application configuration.

    Args:
        config: Application configuration.
        monitor: Optional monitor index override.
        translate: Whether to attach translation provider (default True).

    Returns:
        Pipeline: Assembled pipeline instance.
    """
    capturer = create_capturer(config, monitor=monitor)
    detector = create_detector(config)
    ocr_engine = create_ocr_engine(config)
    translator = create_translator(config) if translate else None

    return Pipeline(
        capturer=capturer,
        detector=detector,
        ocr_engine=ocr_engine,
        merge_lines=config.ocr.merge_lines,
        max_gap_ratio=config.ocr.max_gap_ratio,
        translator=translator,
    )


def run_overlay(config: AppConfig, args: argparse.Namespace) -> int:
    """Launch full Stage 3 transparent click-through overlay GUI application."""
    enable_dpi_awareness()

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    log_level = getattr(args, "log_level", None) or config.logging.level
    setup_logging(level=log_level)

    # 1. Target screen selection
    mon_idx = getattr(args, "monitor", None) if getattr(args, "monitor", None) is not None else config.capture.monitor
    screens = app.screens()
    target_screen = screens[mon_idx - 1] if (1 <= mon_idx <= len(screens)) else app.primaryScreen()

    # 2. Pipeline assembly
    use_translation = not getattr(args, "no_translate", False)
    pipeline = create_pipeline(config, monitor=args.monitor, translate=use_translation)

    # 3. Overlay Window setup
    overlay = OverlayWindow(
        font_family=config.overlay.font_family,
        font_size=config.overlay.font_size,
        opacity=config.overlay.opacity,
        background_color=config.overlay.background_color,
        text_color=config.overlay.text_color,
    )
    overlay.set_target_screen(target_screen)
    overlay.show()

    # 4. Region resolution
    target_region: Region | None = None
    if getattr(args, "region", None):
        parts = [int(p.strip()) for p in args.region.split(",")]
        target_region = Region(*parts)
    elif config.capture.region:
        target_region = Region(*config.capture.region)

    # 5. QThread + PipelineWorker
    thread = QThread()
    worker = PipelineWorker(
        pipeline=pipeline,
        fps=config.capture.fps,
        region=target_region,
    )
    worker.moveToThread(thread)

    thread.started.connect(worker.start)
    worker.blocks_ready.connect(overlay.update_blocks, Qt.QueuedConnection)

    # 6. Clean shutdown wiring
    def cleanup() -> None:
        logger.info("Shutting down overlay application...")
        worker.stop()
        thread.quit()
        thread.wait(2000)
        pipeline.capturer.close()

    app.aboutToQuit.connect(cleanup)

    # 7. Enable Ctrl+C termination in terminal
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    sig_timer = QTimer()
    sig_timer.timeout.connect(lambda: None)
    sig_timer.start(200)

    logger.info("Launching overlay window. Press Ctrl+C in terminal to exit.")
    thread.start()
    return app.exec()


class ScreenTranslatorApp:
    """Coordinates lifecycle, worker threads, UI widgets, and dependency injection."""

    def __init__(self, config: AppConfig, args: argparse.Namespace | None = None) -> None:
        self.config = config
        self.args = args or argparse.Namespace(monitor=None, region=None, log_level=None, no_translate=False)

    def run(self) -> int:
        return run_overlay(self.config, self.args)
