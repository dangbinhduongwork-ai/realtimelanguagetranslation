"""Global keyboard shortcuts listener using pynput."""

from __future__ import annotations

import logging
from pynput import keyboard
from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)


def validate_hotkey_string(key_str: str) -> bool:
    """Validate whether key_str matches pynput hotkey syntax.

    Args:
        key_str: Key combination string (e.g., '<ctrl>+<alt>+t').

    Returns:
        bool: True if string can be parsed by pynput, False otherwise.
    """
    if not key_str or not isinstance(key_str, str):
        return False
    try:
        keys = keyboard.HotKey.parse(key_str)
        return len(keys) > 0
    except Exception:
        return False


class GlobalHotkeys(QObject):
    """Listens for system-wide keyboard shortcuts in a background thread and emits Qt signals."""

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
            ValueError: If any key string cannot be parsed by pynput.
        """
        super().__init__(parent)
        self.toggle_key = toggle_key
        self.select_region_key = select_region_key
        self.quit_key = quit_key
        self._listener: keyboard.GlobalHotKeys | None = None

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
                    "Expected pynput format such as '<ctrl>+<alt>+t'."
                )

    def start(self) -> None:
        """Start global keyboard hook in background listener thread."""
        if self._listener is not None:
            return

        try:
            mapping = {
                self.toggle_key: self.toggle.emit,
                self.select_region_key: self.select_region.emit,
                self.quit_key: self.quit.emit,
            }
            self._listener = keyboard.GlobalHotKeys(mapping)
            self._listener.start()
            logger.info(
                "GlobalHotkeys registered: toggle=%s, select=%s, quit=%s",
                self.toggle_key,
                self.select_region_key,
                self.quit_key,
            )
        except Exception as exc:
            logger.error("Failed to register GlobalHotKeys: %s", exc)

    def stop(self) -> None:
        """Stop background listener and release OS keyboard hook."""
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception as exc:
                logger.debug("Error stopping GlobalHotKeys: %s", exc)
            finally:
                self._listener = None
            logger.info("GlobalHotkeys stopped")
