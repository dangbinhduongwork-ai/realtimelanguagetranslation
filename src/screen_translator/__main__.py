"""Main CLI entry point for Screen Translator."""

from __future__ import annotations

import argparse
import importlib
import logging
import sys

logger = logging.getLogger("screen_translator")

MODULES_TO_VERIFY: list[str] = [
    "screen_translator.config",
    "screen_translator.logging_setup",
    "screen_translator.models",
    "screen_translator.pipeline",
    "screen_translator.app",
    "screen_translator.capture.base",
    "screen_translator.capture.mss_capturer",
    "screen_translator.capture.frame_diff",
    "screen_translator.ocr.base",
    "screen_translator.ocr.rapidocr_engine",
    "screen_translator.ocr.grouping",
    "screen_translator.translate.base",
    "screen_translator.translate.google_translator",
    "screen_translator.translate.cache",
    "screen_translator.ui.overlay_window",
    "screen_translator.ui.region_selector",
    "screen_translator.ui.tray",
    "screen_translator.ui.hotkeys",
    "screen_translator.utils.win_utils",
]


def run_check() -> int:
    """Validate configuration and verify all modules import successfully.

    Returns:
        int: Exit status code (0 for success).
    """
    from screen_translator.config import load_config
    from screen_translator.logging_setup import setup_logging

    config = load_config()
    setup_logging(level=config.logging.level)

    logger.debug("Loading and verifying skeleton modules...")
    for mod_name in MODULES_TO_VERIFY:
        importlib.import_module(mod_name)
        logger.debug("Module loaded successfully: %s", mod_name)

    logger.info("OK: skeleton loaded")
    return 0


def main() -> int:
    """Parse CLI options and execute commands."""
    parser = argparse.ArgumentParser(
        prog="screen_translator",
        description="Screen Translator: Real-time on-screen OCR and translation overlay for Windows.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate configuration and ensure all project modules load without error.",
    )

    args = parser.parse_args()

    if args.check:
        return run_check()

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
