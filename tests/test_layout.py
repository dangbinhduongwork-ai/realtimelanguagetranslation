"""Unit tests for ui/layout.py font snapping and line height bucketing."""

from __future__ import annotations

from screen_translator.ui.layout import (
    FONT_PIXEL_SNAPS,
    bucket_line_heights,
    font_px_for,
)


def test_font_px_for_clamps() -> None:
    """Verifies that font_px_for clamps values between 11 and 40."""
    # Very small lines clamp to 11
    assert font_px_for(5.0) == 11
    assert font_px_for(0.0) == 11
    assert font_px_for(-10.0) == 11

    # Very large lines clamp to 40
    assert font_px_for(60.0) == 40
    assert font_px_for(100.0) == 40


def test_font_px_for_snaps() -> None:
    """Verifies snapping to standard typography scale."""
    for snap in FONT_PIXEL_SNAPS:
        # Ideal line height giving exactly snap: snap / 0.8
        lh = snap / 0.8
        assert font_px_for(lh) == snap

    # Height 20.0 * 0.80 = 16.0 -> 16
    assert font_px_for(20.0) == 16
    # Height 18.0 * 0.80 = 14.4 -> snaps to 14
    assert font_px_for(18.0) == 14
    # Height 25.0 * 0.80 = 20.0 -> snaps to 20
    assert font_px_for(25.0) == 20


def test_font_px_jitter_stability() -> None:
    """Verifies that +/- 1px jitter in line height results in identical font size."""
    base_lh = 20.0  # 20 * 0.8 = 16
    size_base = font_px_for(base_lh)
    size_minus = font_px_for(base_lh - 1.0)
    size_plus = font_px_for(base_lh + 1.0)

    assert size_base == 16
    assert size_minus == 16
    assert size_plus == 16


def test_bucket_line_heights() -> None:
    """Verifies clustering of heights within 15% to their bucket median."""
    heights = [19.0, 20.0, 21.0, 40.0]
    mapping = bucket_line_heights(heights)

    # 19.0, 20.0, 21.0 are within 15% (21 - 19) / 19 = 10.5%
    # Median is 20.0
    assert mapping[19.0] == 20.0
    assert mapping[20.0] == 20.0
    assert mapping[21.0] == 20.0

    # 40.0 is separate cluster
    assert mapping[40.0] == 40.0


def test_bucket_determinism() -> None:
    """Verifies deterministic mapping regardless of input order."""
    h1 = [25.0, 24.0, 26.0]
    h2 = [26.0, 24.0, 25.0]

    m1 = bucket_line_heights(h1)
    m2 = bucket_line_heights(h2)

    assert m1[24.0] == m2[24.0] == 25.0
    assert m1[25.0] == m2[25.0] == 25.0
    assert m1[26.0] == m2[26.0] == 25.0


def test_temporal_stability_matching() -> None:
    """Verifies that bounding boxes matching within 4px or IoU >= 0.6 reuse cached font size and height."""
    from screen_translator.ui.layout import find_cached_layout

    cache = [
        ((100, 100, 300, 150), "Chào mừng bạn đến với ứng dụng", 16, 55),
    ]

    # 1. Exact match
    res = find_cached_layout((100, 100, 300, 150), "Chào mừng bạn đến với ứng dụng", cache)
    assert res == (16, 55)

    # 2. Within 4px jitter
    res_jitter = find_cached_layout((102, 98, 299, 153), "Chào mừng bạn đến với ứng dụng", cache, tol_px=4)
    assert res_jitter == (16, 55)

    # 3. Changed text does not match
    res_diff_text = find_cached_layout((100, 100, 300, 150), "Văn bản khác", cache)
    assert res_diff_text is None

    # 4. Beyond 4px jitter but IoU >= 0.6
    # Box (105, 105, 305, 155): width 200, height 50. Shifted by 5px.
    # Area = 10000. Intersection (105, 105, 300, 150): w=195, h=45 -> 8775. IoU = 8775 / 11225 = 0.78 >= 0.6
    res_iou = find_cached_layout((105, 105, 305, 155), "Chào mừng bạn đến với ứng dụng", cache)
    assert res_iou == (16, 55)

    # 5. Distant box fails
    res_far = find_cached_layout((500, 500, 700, 550), "Chào mừng bạn đến với ứng dụng", cache)
    assert res_far is None

