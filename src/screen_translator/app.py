"""Application wiring, dependency injection, and lifecycle coordination."""

from __future__ import annotations

import logging

from screen_translator.config import AppConfig

logger = logging.getLogger(__name__)


class ScreenTranslatorApp:
    """Coordinates lifecycle, worker threads, UI widgets, and dependency injection."""

    def __init__(self, config: AppConfig) -> None:
        """Construct application and wire all dependencies via constructor injection.

        Args:
            config: Validated application configuration dataclass.
        """
        raise NotImplementedError("Application wiring is scheduled for Stage 4")

    def run(self) -> int:
        """Execute the Qt application event loop.

        Returns:
            int: Exit status code.
        """
        raise NotImplementedError("Application execution is scheduled for Stage 4")
