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

logger = logging.getLogger(__name__)


def create_capturer(config: AppConfig, monitor: int | None = None) -> ScreenCapturer:
    """Create configured ScreenCapturer engine instance.

    Args:
        config: Application configuration.
        monitor: Optional monitor index override.

    Returns:
        ScreenCapturer: Configured capturer.
    """
    mon_idx = monitor if monitor is not None else config.capture.monitor
    logger.debug("Creating MssCapturer for monitor %d", mon_idx)
    return MssCapturer(monitor_index=mon_idx)


def create_detector(config: AppConfig) -> ChangeDetector:
    """Create configured ChangeDetector engine instance.

    Args:
        config: Application configuration.

    Returns:
        ChangeDetector: Configured frame difference detector.
    """
    logger.debug("Creating ChangeDetector with threshold %.4f", config.change_detection.threshold)
    return ChangeDetector(threshold=config.change_detection.threshold)


def create_ocr_engine(config: AppConfig) -> OcrEngine:
    """Create configured OcrEngine instance.

    Args:
        config: Application configuration.

    Returns:
        OcrEngine: Configured OCR engine.
    """
    if config.ocr.engine == "rapidocr":
        logger.debug("Creating RapidOcrEngine (min_confidence=%.2f)", config.ocr.min_confidence)
        return RapidOcrEngine(min_confidence=config.ocr.min_confidence)
    raise ValueError(f"Unknown OCR engine: {config.ocr.engine}")


def create_pipeline(config: AppConfig, monitor: int | None = None) -> Pipeline:
    """Create complete Stage 1 Pipeline instance from application configuration.

    Args:
        config: Application configuration.
        monitor: Optional monitor index override.

    Returns:
        Pipeline: Assembled pipeline instance.
    """
    capturer = create_capturer(config, monitor=monitor)
    detector = create_detector(config)
    ocr_engine = create_ocr_engine(config)
    return Pipeline(
        capturer=capturer,
        detector=detector,
        ocr_engine=ocr_engine,
        merge_lines=config.ocr.merge_lines,
        max_gap_ratio=config.ocr.max_gap_ratio,
    )


class ScreenTranslatorApp:
    """Coordinates lifecycle, worker threads, UI widgets, and dependency injection."""

    def __init__(self, config: AppConfig) -> None:
        """Construct application and wire all dependencies via constructor injection.

        Args:
            config: Validated application configuration dataclass.
        """
        raise NotImplementedError("Application wiring is scheduled for Stage 4")

    def run(self) -> int:
        """Execute the Qt application event loop.

        Returns:
            int: Exit status code.
        """
        raise NotImplementedError("Application execution is scheduled for Stage 4")
