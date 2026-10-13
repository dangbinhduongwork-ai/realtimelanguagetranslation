"""Unit tests for hotkey parsing and validation."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

# Ensure src/ is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from screen_translator.ui.hotkeys import (  # noqa: E402
    GlobalHotkeys,
    validate_hotkey_string,
)


def test_valid_hotkeys() -> None:
    """Test valid pynput hotkey strings."""
    assert validate_hotkey_string("<ctrl>+<alt>+t") is True
    assert validate_hotkey_string("<ctrl>+<shift>+r") is True
    assert validate_hotkey_string("<cmd>+q") is True
    assert validate_hotkey_string("<f12>") is True


def test_invalid_hotkeys() -> None:
    """Test malformed or empty hotkey strings."""
    assert validate_hotkey_string("") is False
    assert validate_hotkey_string("<unknown_key_sequence>") is False
    assert validate_hotkey_string("<+++>") is False


def test_global_hotkeys_init_validation() -> None:
    """Test that GlobalHotkeys rejects invalid hotkeys during construction."""
    # Valid
    gh = GlobalHotkeys(
        toggle_key="<ctrl>+<alt>+t",
        select_region_key="<ctrl>+<alt>+r",
        quit_key="<ctrl>+<alt>+q",
    )
    assert gh is not None

    # Invalid toggle key
    with pytest.raises(ValueError, match="Invalid hotkey definition"):
        GlobalHotkeys(toggle_key="invalid_key_str")
