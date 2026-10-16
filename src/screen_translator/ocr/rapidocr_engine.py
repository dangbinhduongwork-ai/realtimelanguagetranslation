"""RapidOCR engine implementation with adaptive upscaling."""

from __future__ import annotations

import logging
from typing import Any
import numpy as np

from screen_translator.models import TextBlock
from screen_translator.ocr.base import OcrEngine
from screen_translator.ocr.upscale import (
    calculate_mean_confidence,
    calculate_median_line_height,
    remap_blocks_to_screen,
    scale_image,
)

logger = logging.getLogger(__name__)


class RapidOcrEngine(OcrEngine):
    """Concrete OCR engine backed by rapidocr-onnxruntime with adaptive scaling and screen mapping."""

    def __init__(
        self,
        min_confidence: float = 0.6,
        upscale: str | float = "auto",
        small_text_px: int = 14,
    ) -> None:
        """Initialize RapidOCR engine configuration.

        Args:
            min_confidence: Confidence threshold (0.0 to 1.0) below which OCR results are dropped.
            upscale: "auto" (default) or numeric upscale factor (e.g. 1.0, 1.5, 2.0).
            small_text_px: Median line height threshold in original pixels triggering 2x upscale in auto mode.
        """
        self.min_confidence = float(min_confidence)
        self.upscale = upscale
        self.small_text_px = int(small_text_px)
        self._engine: Any | None = None
        self._current_factor: float = 1.0
        self._frame_count: int = 0

    @property
    def current_upscale_factor(self) -> float:
        """Return the upscale multiplier currently in active use."""
        return self._current_factor

    def warmup(self) -> None:
        """Pre-load RapidOCR neural network models and execute a dummy inference pass."""
        if self._engine is None:
            logger.info("Loading RapidOCR ONNX models into memory...")
            from rapidocr_onnxruntime import RapidOCR

            kwargs: dict[str, Any] = {}
            try:
                import onnxruntime as ort

                providers = ort.get_available_providers()
                logger.debug("Available ONNX execution providers: %s", providers)
                if "DmlExecutionProvider" in providers:
                    logger.info("DirectML GPU provider detected. Configuring RapidOCR with DirectML...")
                    kwargs = {
                        "det_use_dml": True,
                        "cls_use_dml": True,
                        "rec_use_dml": True,
                    }
                elif "CUDAExecutionProvider" in providers:
                    logger.info("CUDA GPU provider detected. Configuring RapidOCR with CUDA...")
                    kwargs = {
                        "det_use_cuda": True,
                        "cls_use_cuda": True,
                        "rec_use_cuda": True,
                    }
            except Exception as exc:
                logger.debug("Could not inspect onnxruntime providers: %s", exc)

            try:
                self._engine = RapidOCR(**kwargs)
            except Exception as exc:
                if kwargs:
                    logger.warning(
                        "Initializing RapidOCR with GPU acceleration failed: %s. Falling back to CPU.",
                        exc,
                    )
                    self._engine = RapidOCR()
                else:
                    raise

            dummy_frame = np.zeros((48, 128, 3), dtype=np.uint8)
            try:
                self._engine(dummy_frame, use_cls=False)
            except Exception as exc:
                logger.debug("Warmup dummy inference encountered: %s", exc)
            logger.info("RapidOCR engine ready.")

    def _raw_recognize(self, image: np.ndarray) -> list[TextBlock]:
        """Execute RapidOCR inference on image in its local coordinate system."""
        try:
            result, _ = self._engine(image, use_cls=False)
        except Exception as exc:
            logger.error("RapidOCR inference failed: %s", exc)
            return []

        if not result:
            return []

        blocks: list[TextBlock] = []
        for item in result:
            if not item or len(item) < 3:
                continue

            box, raw_text, raw_score = item[0], item[1], item[2]
            try:
                confidence = float(raw_score)
            except (ValueError, TypeError):
                confidence = 0.0

            if confidence < self.min_confidence:
                continue

            text = str(raw_text).strip()
            if not text:
                continue

            try:
                xs = [float(pt[0]) for pt in box]
                ys = [float(pt[1]) for pt in box]
                left = int(min(xs))
                right = int(max(xs))
                top = int(min(ys))
                bottom = int(max(ys))

                if right <= left:
                    right = left + 1
                if bottom <= top:
                    bottom = top + 1

                line_h = float(max(1, bottom - top))
                blocks.append(
                    TextBlock(
                        text=text,
                        bbox=(left, top, right, bottom),
                        confidence=round(confidence, 4),
                        line_height=line_h,
                        line_count=1,
                    )
                )
            except Exception as exc:
                logger.debug("Skipping malformed OCR detection item %s: %s", item, exc)

        return blocks

    def recognize(
        self,
        image: np.ndarray,
        offset: tuple[int, int] = (0, 0),
    ) -> list[TextBlock]:
        """Extract text blocks using adaptive upscaling and map back to screen coordinates."""
        if image is None or image.size == 0:
            return []

        if self._engine is None:
            self.warmup()

        self._frame_count += 1

        # 1. Fixed numeric upscale mode
        if self.upscale != "auto":
            factor = float(self.upscale)
            self._current_factor = factor
            scaled_img = scale_image(image, factor)
            raw = self._raw_recognize(scaled_img)
            return remap_blocks_to_screen(raw, factor=factor, offset=offset)

        # 2. Auto mode: probe 1.0 every 20 frames, otherwise use remembered factor
        reprobe = (self._frame_count % 20 == 1) or (self._frame_count == 1)
        factor = 1.0 if reprobe else self._current_factor

        scaled_img = scale_image(image, factor)
        raw_first = self._raw_recognize(scaled_img)
        unscaled_first = remap_blocks_to_screen(raw_first, factor=factor, offset=(0, 0))
        median_h = calculate_median_line_height(unscaled_first)

        # If probed at 1.0 and text is detected but small, re-run on 2x upscale
        if factor == 1.0 and (raw_first and median_h < self.small_text_px):
            img_2x = scale_image(image, 2.0)
            raw_2x = self._raw_recognize(img_2x)
            unscaled_2x = remap_blocks_to_screen(raw_2x, factor=2.0, offset=(0, 0))

            count_1x = len(unscaled_first)
            count_2x = len(unscaled_2x)
            conf_1x = calculate_mean_confidence(unscaled_first)
            conf_2x = calculate_mean_confidence(unscaled_2x)

            if count_2x > count_1x or conf_2x > conf_1x:
                logger.debug(
                    "Adaptive upscale chosen: 2.0x (median_h=%.1f, count %d->%d, conf %.2f->%.2f)",
                    median_h,
                    count_1x,
                    count_2x,
                    conf_1x,
                    conf_2x,
                )
                self._current_factor = 2.0
                return remap_blocks_to_screen(raw_2x, factor=2.0, offset=offset)

            self._current_factor = 1.0
            return remap_blocks_to_screen(raw_first, factor=1.0, offset=offset)

        self._current_factor = factor
        return remap_blocks_to_screen(raw_first, factor=factor, offset=offset)
