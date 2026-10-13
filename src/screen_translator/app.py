"""Application component factories and wiring."""

from __future__ import annotations

import logging

from screen_translator.capture.base import ScreenCapturer
from screen_translator.capture.frame_diff import ChangeDetector
from screen_translator.capture.mss_capturer import MssCapturer
from screen_translator.config import AppConfig
from screen_translator.ocr.base import OcrEngine
from screen_translator.ocr.rapidocr_engine import RapidOcrEngine
from screen_translator.pipeline import Pipeline
from screen_translator.translate import build_translator
from screen_translator.translate.base import Translator

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


class ScreenTranslatorApp:
    """Coordinates lifecycle, worker threads, UI widgets, and dependency injection."""

    def __init__(self, config: AppConfig) -> None:
        raise NotImplementedError("Application wiring is scheduled for Stage 4")

    def run(self) -> int:
        raise NotImplementedError("Application execution is scheduled for Stage 4")
