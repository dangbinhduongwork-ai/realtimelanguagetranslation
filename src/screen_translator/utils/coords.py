"""Coordinate transformation utilities between native physical pixels and Qt logical pixels."""

from __future__ import annotations


def native_to_local(
    bbox: tuple[int, int, int, int],
    screen_origin: tuple[int, int],
    dpr: float = 1.0,
) -> tuple[int, int, int, int]:
    """Convert native physical screen bbox to Qt local widget coordinates.

    Args:
        bbox: (left, top, right, bottom) in physical native screen pixels.
        screen_origin: (origin_x, origin_y) native coordinates of the target screen.
        dpr: Device pixel ratio (screen scaling factor, e.g. 1.0, 1.25, 1.5, 2.0).

    Returns:
        tuple[int, int, int, int]: (local_left, local_top, local_right, local_bottom) in Qt logical pixels.
    """
    scale = max(0.01, float(dpr))
    origin_x, origin_y = screen_origin
    left, top, right, bottom = bbox

    local_left = int(round((left - origin_x) / scale))
    local_top = int(round((top - origin_y) / scale))
    local_right = int(round((right - origin_x) / scale))
    local_bottom = int(round((bottom - origin_y) / scale))

    return (local_left, local_top, local_right, local_bottom)


def local_to_native(
    local_bbox: tuple[int, int, int, int],
    screen_origin: tuple[int, int],
    dpr: float = 1.0,
) -> tuple[int, int, int, int]:
    """Convert Qt local widget coordinates back to physical native screen coordinates.

    Inverse of native_to_local.

    Args:
        local_bbox: (local_left, local_top, local_right, local_bottom) in Qt logical pixels.
        screen_origin: (origin_x, origin_y) native coordinates of the target screen.
        dpr: Device pixel ratio (screen scaling factor).

    Returns:
        tuple[int, int, int, int]: (native_left, native_top, native_right, native_bottom) in physical screen pixels.
    """
    scale = max(0.01, float(dpr))
    origin_x, origin_y = screen_origin
    local_left, local_top, local_right, local_bottom = local_bbox

    native_left = int(round(local_left * scale + origin_x))
    native_top = int(round(local_top * scale + origin_y))
    native_right = int(round(local_right * scale + origin_x))
    native_bottom = int(round(local_bottom * scale + origin_y))

    return (native_left, native_top, native_right, native_bottom)
