"""Unit tests for logging configuration under windowed (no stdout) environments."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys

import pytest

# Ensure src/ is on sys.path for direct pytest execution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from screen_translator.logging_setup import setup_logging


def test_logging_setup_windowed_stdout_none(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Test setup_logging handles sys.stdout and sys.stderr being None without crashing."""
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)

    log_file = tmp_path / "app.log"
    setup_logging(level="DEBUG", log_file=log_file)

    root = logging.getLogger()
    # Confirm no console StreamHandler was attached for stdout
    stream_handlers = [h for h in root.handlers if isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler)]
    assert len(stream_handlers) == 0

    # Confirm rotating file handler is present and active
    file_handlers = [h for h in root.handlers if isinstance(h, RotatingFileHandler)]
    assert len(file_handlers) == 1
    assert file_handlers[0].maxBytes == 1_048_576
    assert file_handlers[0].backupCount == 3

    # Emit a test log and verify it is written to the log file
    test_logger = logging.getLogger("test_windowed")
    test_logger.info("Windowed logging test passed successfully")

    # Flush handlers
    for h in root.handlers:
        h.flush()

    assert log_file.is_file()
    content = log_file.read_text(encoding="utf-8")
    assert "Windowed logging test passed successfully" in content


def test_logging_setup_with_console_stdout(tmp_path: Path) -> None:
    """Test setup_logging adds console StreamHandler when sys.stdout exists."""
    log_file = tmp_path / "console_test.log"
    setup_logging(level="INFO", log_file=log_file)

    root = logging.getLogger()
    # File handler must be configured
    file_handlers = [h for h in root.handlers if isinstance(h, RotatingFileHandler)]
    assert len(file_handlers) == 1

    test_logger = logging.getLogger("test_console")
    test_logger.info("Console test log entry")

    for h in root.handlers:
        h.flush()

    assert log_file.is_file()
    assert "Console test log entry" in log_file.read_text(encoding="utf-8")
