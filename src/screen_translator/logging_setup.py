"""Centralized logging configuration for Screen Translator."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys

from screen_translator.paths import data_dir


def setup_logging(level: str = "INFO", log_file: str | Path | None = None) -> None:
    """Configure application logging for rotating file and optional console output.

    - Console output is enabled ONLY if sys.stdout is present (avoids crashes in windowed exes).
    - Always logs to RotatingFileHandler at data_dir()/logs/app.log (1 MB x 3 backup files).

    Args:
        level: Logging level name ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL').
        log_file: Optional explicit file path to persist log output.
    """
    numeric_level = getattr(logging, str(level).upper(), logging.INFO)
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Clear pre-existing handlers to prevent duplicate entries
    if root_logger.handlers:
        root_logger.handlers.clear()

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 1. Console stream handler (only when a valid console stdout stream exists)
    if sys.stdout is not None:
        try:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(numeric_level)
            console_handler.setFormatter(formatter)
            root_logger.addHandler(console_handler)
        except Exception:
            pass

    # 2. Rotating file handler (default: %APPDATA%/ScreenTranslator/logs/app.log)
    target_log_path = Path(log_file) if log_file else (data_dir() / "logs" / "app.log")
    try:
        target_log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            target_log_path,
            maxBytes=1_048_576,  # 1 MB
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except Exception as exc:
        if sys.stderr is not None:
            print(f"Warning: Failed to initialize file logger at {target_log_path}: {exc}", file=sys.stderr)

    logging.getLogger(__name__).debug("Logging configured at level %s", str(level).upper())
