"""Global keyboard shortcut manager using pynput."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class GlobalHotkeys(QObject):
    """Listens for global key combinations via pynput and emits Qt signals."""

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
        """Initialize hotkey listener specifications.

        Args:
            toggle_key: String representation of shortcut to toggle translation overlay.
            select_region_key: String representation of shortcut to activate region selector.
            quit_key: String representation of shortcut to exit the application.
            parent: Optional parent QObject.
        """
        super().__init__(parent)
        raise NotImplementedError("GlobalHotkeys is scheduled for Stage 4")

    def start(self) -> None:
        """Start listening for keyboard events in a background daemon thread."""
        raise NotImplementedError("GlobalHotkeys is scheduled for Stage 4")

    def stop(self) -> None:
        """Stop background listener and unregister shortcuts."""
        raise NotImplementedError("GlobalHotkeys is scheduled for Stage 4")
