"""Windows-specific utilities for DPI awareness, window capture affinity, and click-through."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import logging
import sys

logger = logging.getLogger(__name__)

# Win32 Constants
GWL_EXSTYLE: int = -20
WS_EX_LAYERED: int = 0x00080000
WS_EX_TRANSPARENT: int = 0x00000020
WS_EX_TOOLWINDOW: int = 0x00000080
WDA_EXCLUDEFROMCAPTURE: int = 0x00000011
DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2: int = -4


def enable_dpi_awareness() -> bool:
    """Enable per-monitor DPI awareness v2 on Windows.

    Must be called before QApplication is instantiated to prevent scaling artifacts.

    Returns:
        bool: True if DPI awareness was successfully applied, False otherwise.
    """
    if sys.platform != "win32":
        logger.warning("enable_dpi_awareness called on non-Windows platform")
        return False

    # 1. Preferred: SetProcessDpiAwarenessContext (Windows 10 Build 1607+)
    try:
        user32 = ctypes.windll.user32
        if hasattr(user32, "SetProcessDpiAwarenessContext"):
            user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
            user32.SetProcessDpiAwarenessContext.restype = wintypes.BOOL
            if user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)):
                logger.info("Enabled Per-Monitor DPI Awareness V2")
                return True
    except Exception as exc:
        logger.debug("SetProcessDpiAwarenessContext failed: %s", exc)

    # 2. Fallback: SetProcessDpiAwareness via shcore (Windows 8.1+)
    try:
        shcore = ctypes.windll.shcore
        if hasattr(shcore, "SetProcessDpiAwareness"):
            shcore.SetProcessDpiAwareness.argtypes = [ctypes.c_int]
            shcore.SetProcessDpiAwareness.restype = ctypes.c_long
            if shcore.SetProcessDpiAwareness(2) == 0:  # PROCESS_PER_MONITOR_DPI_AWARE = 2
                logger.info("Enabled Per-Monitor DPI Awareness via shcore")
                return True
    except Exception as exc:
        logger.debug("SetProcessDpiAwareness via shcore failed: %s", exc)

    # 3. Fallback: SetProcessDPIAware via user32 (Windows Vista+)
    try:
        user32 = ctypes.windll.user32
        if hasattr(user32, "SetProcessDPIAware"):
            user32.SetProcessDPIAware.argtypes = []
            user32.SetProcessDPIAware.restype = wintypes.BOOL
            if user32.SetProcessDPIAware():
                logger.info("Enabled System DPI Awareness via user32")
                return True
    except Exception as exc:
        logger.debug("SetProcessDPIAware failed: %s", exc)

    logger.warning("Failed to enable any DPI awareness on this system")
    return False


def exclude_window_from_capture(hwnd: int) -> bool:
    """Exclude the window from screen capture using SetWindowDisplayAffinity.

    Uses WDA_EXCLUDEFROMCAPTURE (0x11) so our own overlay is never captured by our OCR.
    Supported on Windows 10 Version 2004 (Build 19041) and newer.

    Args:
        hwnd: Native window handle (HWND).

    Returns:
        bool: True if affinity was applied, False otherwise.
    """
    if sys.platform != "win32":
        logger.warning("exclude_window_from_capture called on non-Windows platform")
        return False

    try:
        user32 = ctypes.windll.user32
        user32.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
        user32.SetWindowDisplayAffinity.restype = wintypes.BOOL

        success = user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
        if not success:
            err = ctypes.get_last_error()
            logger.warning(
                "SetWindowDisplayAffinity failed with error code %d. "
                "Window capture exclusion may not be supported on this Windows version.",
                err,
            )
            return False

        logger.info("Window %s successfully excluded from screen capture (affinity set)", hwnd)
        return True
    except Exception as exc:
        logger.warning("Error excluding window %s from screen capture: %s", hwnd, exc)
        return False


def make_click_through(hwnd: int) -> bool:
    """Set window extended styles to make it click-through, transparent, and toolwindow.

    Applies WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW.

    Args:
        hwnd: Native window handle (HWND).

    Returns:
        bool: True if styles were set, False otherwise.
    """
    if sys.platform != "win32":
        logger.warning("make_click_through called on non-Windows platform")
        return False

    try:
        user32 = ctypes.windll.user32

        # 64-bit / 32-bit compatible function resolution
        if hasattr(user32, "GetWindowLongPtrW"):
            get_style = user32.GetWindowLongPtrW
            set_style = user32.SetWindowLongPtrW
            get_style.argtypes = [wintypes.HWND, ctypes.c_int]
            get_style.restype = ctypes.c_ssize_t
            set_style.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
            set_style.restype = ctypes.c_ssize_t
        else:
            get_style = user32.GetWindowLongW
            set_style = user32.SetWindowLongW
            get_style.argtypes = [wintypes.HWND, ctypes.c_int]
            get_style.restype = wintypes.LONG
            set_style.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]
            set_style.restype = wintypes.LONG

        current_style = get_style(hwnd, GWL_EXSTYLE)
        new_style = current_style | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW
        result = set_style(hwnd, GWL_EXSTYLE, new_style)

        if result == 0 and ctypes.get_last_error() != 0:
            err = ctypes.get_last_error()
            logger.warning("SetWindowLongPtr failed for HWND %s (error code %d)", hwnd, err)
            return False

        logger.info(
            "Window %s configured as click-through (WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW)",
            hwnd,
        )
        return True
    except Exception as exc:
        logger.warning("Error making window %s click-through: %s", hwnd, exc)
        return False
