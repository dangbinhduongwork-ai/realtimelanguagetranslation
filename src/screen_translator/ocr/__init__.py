"""OCR subpackage."""

from screen_translator.ocr.base import OcrEngine
from screen_translator.ocr.grouping import group_lines
from screen_translator.ocr.rapidocr_engine import RapidOcrEngine

__all__ = ["OcrEngine", "RapidOcrEngine", "group_lines"]
