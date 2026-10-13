"""Text filtering utilities for translation readiness."""

from __future__ import annotations

import re

# Comprehensive set of accented Vietnamese characters (lowercase and uppercase)
VIETNAMESE_DIACRITICS: frozenset[str] = frozenset(
    "àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ"
    "ÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴĐ"
)


def needs_translation(text: str, source_lang: str = "en") -> bool:
    """Determine whether a given text string requires translation.

    Returns False if:
    - Text contains fewer than 2 letters (ignoring digits, whitespace, and punctuation).
    - Text consists solely of numbers or symbols.
    - Text already contains Vietnamese diacritics (treated as already in target language).

    Args:
        text: Input string to evaluate.
        source_lang: Expected source language (default 'en').

    Returns:
        bool: True if text should be forwarded to the translation engine, False otherwise.
    """
    if not text:
        return False

    # Check if already in Vietnamese (contains Vietnamese diacritics)
    if any(char in VIETNAMESE_DIACRITICS for char in text):
        return False

    # Count alphabetical letters (Unicode-aware)
    letters = [ch for ch in text if ch.isalpha()]
    if len(letters) < 2:
        return False

    return True
