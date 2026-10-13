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


class _MockGeom:
    def __init__(self, x: int, y: int, w: int, h: int) -> None:
        self._x, self._y, self._w, self._h = x, y, w, h

    def x(self) -> int:
        return self._x

    def y(self) -> int:
        return self._y

    def width(self) -> int:
        return self._w

    def height(self) -> int:
        return self._h


class _MockScreen:
    def __init__(self, name: str, x: int, y: int, w: int, h: int, dpr: float = 1.0) -> None:
        self.name = name
        self._geom = _MockGeom(x, y, w, h)
        self._dpr = dpr

    def geometry(self) -> _MockGeom:
        return self._geom

    def devicePixelRatio(self) -> float:
        return self._dpr


def test_find_screen_with_largest_overlap() -> None:
    """Test screen matching based on maximal intersection area."""
    from screen_translator.models import Region
    from screen_translator.utils.coords import find_screen_with_largest_overlap

    s1 = _MockScreen("Monitor1", 0, 0, 1920, 1080, 1.0)
    s2 = _MockScreen("Monitor2", 1920, 0, 1920, 1080, 1.0)
    screens = [s1, s2]

    # No screens
    assert find_screen_with_largest_overlap([], None) is None

    # Region is None -> returns first screen
    assert find_screen_with_largest_overlap(screens, None) is s1

    # Region entirely inside Monitor 1
    r1 = Region(100, 100, 400, 300)
    assert find_screen_with_largest_overlap(screens, r1) is s1

    # Region entirely inside Monitor 2
    r2 = Region(2100, 100, 400, 300)
    assert find_screen_with_largest_overlap(screens, r2) is s2

    # Region straddling both monitors but with 80% on Monitor 2
    # Monitor 1 has (1800 to 1920) = 120 px width
    # Monitor 2 has (1920 to 2400) = 480 px width
    r_straddle = Region(1800, 200, 600, 300)
    assert find_screen_with_largest_overlap(screens, r_straddle) is s2

