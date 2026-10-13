"""Platform and helper utilities package."""

from screen_translator.utils.win_utils import (
    enable_dpi_awareness,
    exclude_window_from_capture,
    make_click_through,
)

__all__ = [
    "enable_dpi_awareness",
    "exclude_window_from_capture",
    "make_click_through",
]
