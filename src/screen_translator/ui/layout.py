"""Pure layout calculation functions for overlay typography and line fitting.

Independent of Qt widgets to allow clean unit testing and deterministic geometry.
"""

from __future__ import annotations

from collections.abc import Sequence
import statistics

# Allowed font sizes (in logical pixels) to enforce typographic consistency
FONT_PIXEL_SNAPS: list[int] = [11, 12, 13, 14, 16, 18, 20, 24, 28, 32, 40]
MIN_FONT_PX: int = 11
MAX_FONT_PX: int = 40


def font_px_for(line_height_px: float) -> int:
    """Calculate snapped target font pixel size from single-line height.

    Formula:
    1. Base size = round(line_height_px * 0.80)
    2. Clamped to [11, 40]
    3. Snapped to nearest value in [11, 12, 13, 14, 16, 18, 20, 24, 28, 32, 40]

    Args:
        line_height_px: Original single-line text height in pixels.

    Returns:
        int: Snapped typographic font size in logical pixels.
    """
    if line_height_px <= 0:
        return MIN_FONT_PX

    raw = int(round(line_height_px * 0.80))
    clamped = max(MIN_FONT_PX, min(MAX_FONT_PX, raw))

    # Snap to nearest size in FONT_PIXEL_SNAPS (favor smaller on exact tie)
    best_snap = min(FONT_PIXEL_SNAPS, key=lambda s: (abs(s - clamped), s))
    return best_snap


def bucket_line_heights(heights: Sequence[float]) -> dict[float, float]:
    """Cluster line heights within 15% into shared buckets represented by bucket median.

    Args:
        heights: List or sequence of line height values in pixels.

    Returns:
        dict[float, float]: Mapping from each original height to its bucket median.
    """
    if not heights:
        return {}

    # Sort unique valid heights
    unique_sorted = sorted({float(h) for h in heights if h > 0})
    if not unique_sorted:
        return {h: float(h) for h in heights}

    clusters: list[list[float]] = []
    current_cluster: list[float] = [unique_sorted[0]]

    for h in unique_sorted[1:]:
        cluster_base = current_cluster[0]
        # Check if within 15% of cluster base
        if (h - cluster_base) / max(1e-5, cluster_base) <= 0.15:
            current_cluster.append(h)
        else:
            clusters.append(current_cluster)
            current_cluster = [h]
    if current_cluster:
        clusters.append(current_cluster)

    mapping: dict[float, float] = {}
    for cluster in clusters:
        med = float(statistics.median(cluster))
        for item in cluster:
            mapping[item] = med

    # Populate any non-positive items as themselves
    for h in heights:
        if h not in mapping:
            mapping[h] = float(h)

    return mapping


def bbox_iou(box1: tuple[int, int, int, int], box2: tuple[int, int, int, int]) -> float:
    """Compute Intersection over Union (IoU) of two bounding boxes (l, t, r, b)."""
    l1, t1, r1, b1 = box1
    l2, t2, r2, b2 = box2
    inter_l = max(l1, l2)
    inter_t = max(t1, t2)
    inter_r = min(r1, r2)
    inter_b = min(b1, b2)
    if inter_r <= inter_l or inter_b <= inter_t:
        return 0.0

    inter_area = (inter_r - inter_l) * (inter_b - inter_t)
    area1 = max(1, (r1 - l1) * (b1 - t1))
    area2 = max(1, (r2 - l2) * (b2 - t2))
    union_area = area1 + area2 - inter_area
    return float(inter_area) / max(1.0, float(union_area))


def find_cached_layout(
    box: tuple[int, int, int, int],
    text: str,
    cached_layouts: Sequence[tuple[tuple[int, int, int, int], str, int, int]],
    tol_px: int = 4,
    min_iou: float = 0.6,
) -> tuple[int, int] | None:
    """Find previously computed (font_px, box_height) if box and text match a previous frame.

    Args:
        box: Current local bounding box (l, t, r, b).
        text: Current translated text.
        cached_layouts: Sequence of (box, text, font_px, height) from previous frame.
        tol_px: Coordinate tolerance in pixels (default 4px).
        min_iou: Minimum IoU overlap to consider match if tolerance exceeded (default 0.6).

    Returns:
        tuple[int, int] | None: (font_px, box_height) if matched, None otherwise.
    """
    l, t, r, b = box
    text_clean = text.strip()
    for c_box, c_text, c_font_px, c_height in cached_layouts:
        if c_text.strip() != text_clean:
            continue
        c_l, c_t, c_r, c_b = c_box
        # 1. Coordinate tolerance within tol_px
        if (
            abs(l - c_l) <= tol_px
            and abs(t - c_t) <= tol_px
            and abs(r - c_r) <= tol_px
            and abs(b - c_b) <= tol_px
        ):
            return (c_font_px, c_height)

        # 2. IoU overlap >= min_iou
        if bbox_iou(box, c_box) >= min_iou:
            return (c_font_px, c_height)

    return None

