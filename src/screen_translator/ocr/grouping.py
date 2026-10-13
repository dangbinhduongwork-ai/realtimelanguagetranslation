"""Algorithms to cluster and merge fragmented lines into coherent paragraphs."""

from __future__ import annotations

from screen_translator.models import TextBlock


def group_lines(
    blocks: list[TextBlock],
    max_gap_ratio: float = 1.5,
) -> list[TextBlock]:
    """Group vertically adjacent text blocks into coherent multi-line paragraphs.

    Args:
        blocks: List of raw detected line-level text blocks.
        max_gap_ratio: Maximum line spacing multiplier allowed between adjacent lines in a paragraph.

    Returns:
        list[TextBlock]: Grouped paragraph text blocks with merged bounding boxes and joined text.
    """
    raise NotImplementedError("group_lines is scheduled for Stage 1")
