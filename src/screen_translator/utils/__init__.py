"""Platform and helper utilities package."""

from screen_translator.utils.coords import local_to_native, native_to_local
from screen_translator.utils.win_utils import (
    enable_dpi_awareness,
    exclude_window_from_capture,
    make_click_through,
)

__all__ = [
    "enable_dpi_awareness",
    "exclude_window_from_capture",
    "make_click_through",
    "native_to_local",
    "local_to_native",
]
