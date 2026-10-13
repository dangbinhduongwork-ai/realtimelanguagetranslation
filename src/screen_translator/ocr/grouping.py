"""Pure functions to cluster adjacent line-level text blocks into coherent paragraphs."""

from __future__ import annotations

from screen_translator.models import TextBlock


def _can_merge(prev: TextBlock, curr: TextBlock, max_gap_ratio: float) -> bool:
    """Check if curr line can be merged into the paragraph containing prev line.

    Merge line B into paragraph A only if ALL hold:
    1. vertical gap <= max_gap_ratio * line height
    2. horizontal overlap >= 50% of the narrower block
    3. height ratio within 0.7 - 1.4 (similar font size)
    """
    h_prev = max(1, prev.bbox[3] - prev.bbox[1])
    h_curr = max(1, curr.bbox[3] - curr.bbox[1])

    # 1. Height ratio check (similar font size)
    ratio_1 = h_curr / h_prev
    ratio_2 = h_prev / h_curr
    if not (0.7 <= ratio_1 <= 1.4 and 0.7 <= ratio_2 <= 1.4):
        return False

    # 2. Vertical gap check (curr must be below prev)
    v_gap = curr.bbox[1] - prev.bbox[3]
    # Allow small negative gap (slight OCR box overlap) down to -30% line height
    if v_gap < -0.3 * h_prev:
        return False
    if v_gap > max_gap_ratio * h_prev:
        return False

    # 3. Horizontal overlap check (>= 50% of narrower block)
    overlap = max(0, min(prev.bbox[2], curr.bbox[2]) - max(prev.bbox[0], curr.bbox[0]))
    w_prev = max(1, prev.bbox[2] - prev.bbox[0])
    w_curr = max(1, curr.bbox[2] - curr.bbox[0])
    narrower = min(w_prev, w_curr)

    if (overlap / narrower) < 0.5:
        return False

    return True


def group_lines(
    blocks: list[TextBlock],
    max_gap_ratio: float = 0.8,
) -> list[TextBlock]:
    """Group vertically adjacent text blocks into coherent multi-line paragraphs.

    Args:
        blocks: List of raw detected line-level text blocks.
        max_gap_ratio: Maximum vertical distance ratio between lines to group them together.

    Returns:
        list[TextBlock]: Grouped paragraph text blocks with merged bounding boxes and joined text.
    """
    if not blocks:
        return []

    # Sort in reading order (top coordinate first, then left coordinate)
    sorted_blocks = sorted(blocks, key=lambda b: (b.bbox[1], b.bbox[0]))

    paragraphs: list[list[TextBlock]] = []

    for block in sorted_blocks:
        best_para_idx: int | None = None
        min_v_gap = float("inf")

        for idx, para in enumerate(paragraphs):
            last_line = para[-1]
            if _can_merge(last_line, block, max_gap_ratio):
                v_gap = abs(block.bbox[1] - last_line.bbox[3])
                if v_gap < min_v_gap:
                    min_v_gap = v_gap
                    best_para_idx = idx

        if best_para_idx is not None:
            paragraphs[best_para_idx].append(block)
        else:
            paragraphs.append([block])

    grouped_results: list[TextBlock] = []
    for para in paragraphs:
        merged_text = " ".join(b.text.strip() for b in para if b.text.strip())
        if not merged_text:
            continue

        min_left = min(b.bbox[0] for b in para)
        min_top = min(b.bbox[1] for b in para)
        max_right = max(b.bbox[2] for b in para)
        max_bottom = max(b.bbox[3] for b in para)
        mean_conf = sum(b.confidence for b in para) / len(para)

        grouped_results.append(
            TextBlock(
                text=merged_text,
                bbox=(min_left, min_top, max_right, max_bottom),
                confidence=round(mean_conf, 4),
            )
        )

    # Sort resulting paragraphs in reading order
    return sorted(grouped_results, key=lambda b: (b.bbox[1], b.bbox[0]))
