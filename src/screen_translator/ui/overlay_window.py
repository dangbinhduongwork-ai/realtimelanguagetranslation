"""Transparent, click-through, always-on-top overlay window."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from screen_translator.models import TranslatedBlock


class OverlayWindow(QWidget):
    """Transparent overlay rendering translated text blocks directly above source text."""

    def __init__(
        self,
        font_family: str = "Segoe UI",
        font_size: int = 14,
        opacity: float = 0.9,
        background_color: str = "#000000",
        text_color: str = "#FFFFFF",
        parent: QWidget | None = None,
    ) -> None:
        """Initialize overlay window visual styling and window flags.

        Args:
            font_family: Font family name used to render translated text.
            font_size: Font size in points.
            opacity: Opacity level between 0.0 (transparent) and 1.0 (opaque).
            background_color: Hex color string for translation block background.
            text_color: Hex color string for translated text characters.
            parent: Optional parent QWidget.
        """
        super().__init__(parent)
        raise NotImplementedError("OverlayWindow is scheduled for Stage 3")

    def update_blocks(self, blocks: list[TranslatedBlock]) -> None:
        """Update and repaint the rendered translation blocks on screen.

        Args:
            blocks: List of translated blocks containing screen bounding boxes.
        """
        raise NotImplementedError("OverlayWindow is scheduled for Stage 3")

    def clear(self) -> None:
        """Clear all active translation blocks from the overlay."""
        raise NotImplementedError("OverlayWindow is scheduled for Stage 3")

    def toggle_visible(self) -> None:
        """Toggle overlay visibility state between visible and hidden."""
        raise NotImplementedError("OverlayWindow is scheduled for Stage 3")
