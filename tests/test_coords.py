"""Unit tests for coordinate transformation between native physical and Qt logical coordinates."""

from __future__ import annotations

from pathlib import Path
import sys
import pytest

# Ensure src/ is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from screen_translator.utils.coords import local_to_native, native_to_local  # noqa: E402


@pytest.mark.parametrize("dpr", [1.0, 1.25, 1.5, 2.0])
def test_native_to_local_standard_origin(dpr: float) -> None:
    """Test native_to_local with origin (0, 0) across different device pixel ratios."""
    native_bbox = (100, 200, 500, 400)
    local_bbox = native_to_local(native_bbox, screen_origin=(0, 0), dpr=dpr)

    expected_left = int(round(100 / dpr))
    expected_top = int(round(200 / dpr))
    expected_right = int(round(500 / dpr))
    expected_bottom = int(round(400 / dpr))

    assert local_bbox == (expected_left, expected_top, expected_right, expected_bottom)


def test_nonzero_screen_origin() -> None:
    """Test secondary monitor offset with positive origin."""
    screen_origin = (1920, 0)
    dpr = 1.25
    native_bbox = (2020, 100, 2520, 300)  # On second monitor: x in [1920, 1920+1920]

    local_bbox = native_to_local(native_bbox, screen_origin=screen_origin, dpr=dpr)
    # rel = (100, 100, 600, 300)
    assert local_bbox == (80, 80, 480, 240)


def test_negative_screen_origin() -> None:
    """Test secondary monitor located to the left or above primary monitor (negative origin)."""
    screen_origin = (-1920, 0)
    dpr = 1.0
    native_bbox = (-1820, 50, -1320, 250)

    local_bbox = native_to_local(native_bbox, screen_origin=screen_origin, dpr=dpr)
    # -1820 - (-1920) = 100
    # -1320 - (-1920) = 600
    assert local_bbox == (100, 50, 600, 250)


@pytest.mark.parametrize("dpr", [1.0, 1.25, 1.5, 2.0])
@pytest.mark.parametrize(
    "origin",
    [(0, 0), (1920, 0), (-1920, 0), (0, -1080), (-1920, -1080)],
)
def test_coords_round_trip(dpr: float, origin: tuple[int, int]) -> None:
    """Test native <-> local round trip conversion preserves coordinate boundaries."""
    initial_local = (50, 80, 350, 220)
    native = local_to_native(initial_local, screen_origin=origin, dpr=dpr)
    recovered_local = native_to_local(native, screen_origin=origin, dpr=dpr)

    assert recovered_local == initial_local
