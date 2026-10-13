"""Unit tests for state persistence."""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile

import pytest

# Ensure src/ is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from screen_translator.state import (  # noqa: E402
    AppState,
    is_region_within_monitors,
    load_state,
    save_state,
)


def test_missing_file_returns_default() -> None:
    """Test that reading a non-existent state file returns default AppState."""
    non_existent = Path(tempfile.gettempdir()) / "non_existent_state_file_12345.json"
    state = load_state(non_existent)
    assert state.region is None
    assert state.is_running is True


def test_corrupt_file_returns_default() -> None:
    """Test that a corrupt / malformed JSON state file safely falls back to defaults."""
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".json") as f:
        f.write("{invalid json content ...")
        temp_path = Path(f.name)

    try:
        state = load_state(temp_path)
        assert state.region is None
        assert state.is_running is True
    finally:
        temp_path.unlink(missing_ok=True)


def test_atomic_write_and_reload() -> None:
    """Test saving and loading valid state with atomic write."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        state_file = Path(tmp_dir) / "sub" / "state.json"
        saved = AppState(region=(100, 200, 800, 600), is_running=False)
        save_state(saved, state_file)

        assert state_file.is_file()
        loaded = load_state(state_file)
        assert loaded.region == (100, 200, 800, 600)
        assert loaded.is_running is False


def test_is_region_within_monitors() -> None:
    """Test region validation against connected monitors."""
    monitors = [(0, 0, 1920, 1080), (1920, 0, 1920, 1080)]

    # Overlaps monitor 1
    assert is_region_within_monitors((100, 100, 500, 400), monitors) is True
    # Overlaps monitor 2
    assert is_region_within_monitors((2000, 100, 500, 400), monitors) is True
    # Outside any monitor
    assert is_region_within_monitors((-5000, -5000, 100, 100), monitors) is False
    # None or invalid region
    assert is_region_within_monitors(None, monitors) is False
    assert is_region_within_monitors((0, 0, 0, 0), monitors) is False
