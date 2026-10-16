"""Unit tests for joined batch translation and per-item fallback."""

from __future__ import annotations

import math
from unittest.mock import MagicMock, patch

from screen_translator.translate.google_translator import GoogleTranslator


def test_joined_batch_single_call_and_order_preserved() -> None:
    """Verifies joined batch mode makes <= ceil(total_chars/4500) calls and preserves item order."""
    texts = [
        "First sentence to translate.",
        "Second sentence to translate.",
        "Third sentence to translate.",
        "Fourth sentence to translate.",
    ]
    total_chars = sum(len(t) for t in texts) + len(texts) - 1
    max_expected_calls = math.ceil(total_chars / 4500)

    call_log: list[str] = []

    def fake_direct(text: str, source: str = "en", target: str = "vi") -> str:
        call_log.append(text)
        # Return uppercase mock translation joined with newline
        lines = text.split("\n")
        return "\n".join(f"[VI] {l.strip()}" for l in lines)

    translator = GoogleTranslator(batch_mode="joined")

    with patch("screen_translator.translate.google_translator._direct_google_translate", side_effect=fake_direct):
        results = translator.translate(texts, source="en", target="vi")

    # Joined mode should execute in exactly 1 call (< 4500 chars)
    assert len(call_log) <= max_expected_calls
    assert len(results) == 4
    for orig, res in zip(texts, results):
        assert res == f"[VI] {orig}"


def test_joined_batch_mismatch_falls_back_to_per_item() -> None:
    """Verifies that a line count mismatch triggers per-item fallback only for that chunk."""
    texts = [
        "Paragraph item 1.",
        "Paragraph item 2.",
        "Paragraph item 3.",
    ]
    call_log: list[str] = []

    def fake_direct(text: str, source: str = "en", target: str = "vi") -> str:
        call_log.append(text)
        if "\n" in text:
            # Simulate Google Translate accidentally collapsing lines into 2 parts instead of 3
            return "[VI] Part 1\n[VI] Part 2"
        # Per-item translation
        return f"[VI] {text.strip()}"

    translator = GoogleTranslator(batch_mode="joined")

    with patch("screen_translator.translate.google_translator._direct_google_translate", side_effect=fake_direct):
        results = translator.translate(texts, source="en", target="vi")

    # Call 1 was joined, then 3 per-item calls after mismatch detection
    assert len(call_log) == 1 + 3
    assert len(results) == 3
    assert results == [
        "[VI] Paragraph item 1.",
        "[VI] Paragraph item 2.",
        "[VI] Paragraph item 3.",
    ]
