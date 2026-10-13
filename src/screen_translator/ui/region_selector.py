"""Interactive screen region selection tool."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget

from screen_translator.models import Region


class RegionSelector(QWidget):
    """Full-screen interactive widget enabling click-and-drag screen region selection."""

    region_selected = Signal(object)  # Emits Region
    cancelled = Signal()              # Emits when user cancels (e.g. presses Escape)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize RegionSelector widget.

        Args:
            parent: Optional parent QWidget.
        """
        super().__init__(parent)
        raise NotImplementedError("RegionSelector is scheduled for Stage 4")

    def start_selection(self) -> None:
        """Display full-screen translucent canvas and begin mouse capture."""
        raise NotImplementedError("RegionSelector is scheduled for Stage 4")
