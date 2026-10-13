"""State persistence for remembering screen regions and execution settings."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import logging
import os
from pathlib import Path

from screen_translator.paths import data_dir

logger = logging.getLogger(__name__)


@dataclass
class AppState:
    """Persistent application state."""

    region: tuple[int, int, int, int] | None = None
    is_running: bool = True


def get_default_state_path() -> Path:
    """Return default state.json path inside %APPDATA%/ScreenTranslator."""
    return data_dir() / "state.json"


def load_state(path: Path | None = None) -> AppState:
    """Load persistent state from disk, gracefully handling missing or corrupted files.

    Args:
        path: Optional explicit state file path.

    Returns:
        AppState: Stored state or default AppState on any read/parse failure.
    """
    target = path or get_default_state_path()
    if not target.is_file():
        logger.debug("State file %s does not exist; using defaults", target)
        return AppState()

    try:
        with open(target, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            logger.warning("Corrupt state file %s (not a dict); using defaults", target)
            return AppState()

        raw_region = data.get("region")
        parsed_region = (
            tuple(raw_region)
            if isinstance(raw_region, (list, tuple)) and len(raw_region) == 4
            else None
        )
        is_running = bool(data.get("is_running", True))

        return AppState(region=parsed_region, is_running=is_running)
    except Exception as exc:
        logger.warning("Failed to load state from %s: %s; using defaults", target, exc)
        return AppState()


def save_state(state: AppState, path: Path | None = None) -> None:
    """Atomically save state to disk using a temporary file rename.

    Args:
        state: AppState instance to write.
        path: Optional explicit state file path.
    """
    target = path or get_default_state_path()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        temp_file = target.with_suffix(".tmp")

        payload = asdict(state)
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        temp_file.replace(target)
        logger.debug("Successfully saved state to %s", target)
    except Exception as exc:
        logger.error("Failed to save state to %s: %s", target, exc)


def is_region_within_monitors(
    region: tuple[int, int, int, int] | None,
    monitor_geometries: list[tuple[int, int, int, int]],
) -> bool:
    """Verify if a rectangular region overlaps with any active monitor.

    Args:
        region: (left, top, width, height) in native physical coordinates.
        monitor_geometries: List of (m_left, m_top, m_width, m_height) for active monitors.

    Returns:
        bool: True if region intersects at least one monitor, False otherwise.
    """
    if region is None or len(region) != 4:
        return False

    l, t, w, h = region
    if w <= 0 or h <= 0:
        return False

    r, b = l + w, t + h

    for ml, mt, mw, mh in monitor_geometries:
        mr, mb = ml + mw, mt + mh
        overlap_x = max(0, min(r, mr) - max(l, ml))
        overlap_y = max(0, min(b, mb) - max(t, mt))
        if overlap_x > 0 and overlap_y > 0:
            return True

    return False
