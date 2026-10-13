"""Screen capture subpackage."""

from screen_translator.capture.base import ScreenCapturer
from screen_translator.capture.frame_diff import ChangeDetector
from screen_translator.capture.mss_capturer import MssCapturer

__all__ = ["ScreenCapturer", "MssCapturer", "ChangeDetector"]
