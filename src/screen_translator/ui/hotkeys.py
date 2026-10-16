"""Global keyboard shortcuts listener using native Win32 RegisterHotKey API."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import logging
import threading

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012

SPECIAL_VK_MAP: dict[str, int] = {
    "esc": 0x1B,
    "escape": 0x1B,
    "space": 0x20,
    "enter": 0x0D,
    "return": 0x0D,
    "tab": 0x09,
    "backspace": 0x08,
    "insert": 0x2D,
    "delete": 0x2E,
    "home": 0x24,
    "end": 0x23,
    "pageup": 0x21,
    "prior": 0x21,
    "pagedown": 0x22,
    "next": 0x22,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
}
for _i in range(1, 25):
    SPECIAL_VK_MAP[f"f{_i}"] = 0x70 + (_i - 1)


def parse_hotkey_string(key_str: str) -> tuple[int, int] | None:
    """Parse shortcut string into Win32 (modifiers, vk_code).

    Args:
        key_str: Key combination string (e.g. '<ctrl>+<alt>+t', '<cmd>+q', '<f12>').

    Returns:
        tuple[int, int] | None: (modifiers, vk_code) if valid, None otherwise.
    """
    if not key_str or not isinstance(key_str, str):
        return None

    tokens = [t.strip() for t in key_str.split("+")]
    if any(not t for t in tokens):
        return None

    mods = 0
    vk: int | None = None

    for token in tokens:
        clean = token.lower()
        if clean.startswith("<") and clean.endswith(">") and len(clean) > 2:
            clean = clean[1:-1].strip()

        if not clean:
            return None

        if clean in ("ctrl", "control"):
            mods |= MOD_CONTROL
        elif clean in ("alt", "menu"):
            mods |= MOD_ALT
        elif clean in ("shift",):
            mods |= MOD_SHIFT
        elif clean in ("win", "cmd", "super"):
            mods |= MOD_WIN
        else:
            if vk is not None:
                return None  # Multiple key codes not allowed
            if len(clean) == 1 and clean.isalnum():
                vk = ord(clean.upper())
            elif clean in SPECIAL_VK_MAP:
                vk = SPECIAL_VK_MAP[clean]
            else:
                return None

    if vk is None:
        return None

    return (mods, vk)


def validate_hotkey_string(key_str: str) -> bool:
    """Validate whether key_str matches valid hotkey syntax.

    Args:
        key_str: Key combination string (e.g., '<ctrl>+<alt>+t').

    Returns:
        bool: True if string can be parsed, False otherwise.
    """
    return parse_hotkey_string(key_str) is not None


class GlobalHotkeys(QObject):
    """Listens for system-wide shortcuts via native Win32 RegisterHotKey in a background thread."""

    toggle = Signal()
    select_region = Signal()
    quit = Signal()

    def __init__(
        self,
        toggle_key: str = "<ctrl>+<alt>+t",
        select_region_key: str = "<ctrl>+<alt>+r",
        quit_key: str = "<ctrl>+<alt>+q",
        parent: QObject | None = None,
    ) -> None:
        """Initialize and validate hotkey configurations.

        Args:
            toggle_key: Shortcut string to toggle translation overlay pause/resume.
            select_region_key: Shortcut string to activate interactive region selection.
            quit_key: Shortcut string to terminate the application.
            parent: Optional parent QObject.

        Raises:
            ValueError: If any key string cannot be parsed.
        """
        super().__init__(parent)
        self.toggle_key = toggle_key
        self.select_region_key = select_region_key
        self.quit_key = quit_key

        self._thread: threading.Thread | None = None
        self._thread_id: int = 0
        self._stop_event = threading.Event()
        self._started_event = threading.Event()

        self._validate_all()

    def _validate_all(self) -> None:
        for name, key_str in [
            ("toggle", self.toggle_key),
            ("select_region", self.select_region_key),
            ("quit", self.quit_key),
        ]:
            if not validate_hotkey_string(key_str):
                raise ValueError(
                    f"Invalid hotkey definition for '{name}': '{key_str}'. "
                    "Expected shortcut format such as '<ctrl>+<alt>+t'."
                )

    def start(self) -> None:
        """Start global hotkeys message loop in background thread."""
        if self._thread is not None and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._started_event.clear()
        self._thread = threading.Thread(
            target=self._run_message_loop,
            name="GlobalHotkeysListener",
            daemon=True,
        )
        self._thread.start()
        self._started_event.wait(timeout=2.0)
        logger.info(
            "GlobalHotkeys registered: toggle=%s, select=%s, quit=%s",
            self.toggle_key,
            self.select_region_key,
            self.quit_key,
        )

    def _run_message_loop(self) -> None:
        """Windows thread message loop receiving WM_HOTKEY events."""
        self._thread_id = int(kernel32.GetCurrentThreadId())

        # Ensure calling thread has a Windows message queue
        msg = wintypes.MSG()
        user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)

        hotkey_defs = {
            1: self.toggle_key,
            2: self.select_region_key,
            3: self.quit_key,
        }

        registered_ids: list[int] = []
        for hid, key_str in hotkey_defs.items():
            parsed = parse_hotkey_string(key_str)
            if parsed is None:
                continue
            mods, vk = parsed
            ok = user32.RegisterHotKey(None, hid, mods | MOD_NOREPEAT, vk)
            if not ok:
                ok = user32.RegisterHotKey(None, hid, mods, vk)
            if ok:
                registered_ids.append(hid)
            else:
                logger.warning("RegisterHotKey failed for '%s' (id=%d, vk=%d)", key_str, hid, vk)

        self._started_event.set()

        try:
            while not self._stop_event.is_set():
                ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if ret <= 0:
                    break
                if msg.message == WM_HOTKEY:
                    hid = int(msg.wParam)
                    if hid == 1:
                        self.toggle.emit()
                    elif hid == 2:
                        self.select_region.emit()
                    elif hid == 3:
                        self.quit.emit()
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        finally:
            for hid in registered_ids:
                user32.UnregisterHotKey(None, hid)
            self._thread_id = 0

    def stop(self) -> None:
        """Stop background listener and release hotkeys."""
        self.cleanup()

    def cleanup(self) -> None:
        """Release all registered hotkeys and stop background thread."""
        self._stop_event.set()
        if self._thread_id != 0:
            user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None
        self._thread_id = 0
        logger.info("GlobalHotkeys stopped")
