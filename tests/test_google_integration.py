"""Live integration test for GoogleTranslator."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

# Ensure src/ is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from screen_translator.translate.filters import VIETNAMESE_DIACRITICS  # noqa: E402
from screen_translator.translate.google_translator import GoogleTranslator  # noqa: E402


@pytest.mark.integration
def test_google_translator_hello_world() -> None:
    """Live API test: translates 'Hello world' to Vietnamese with diacritics."""
    translator = GoogleTranslator()
    results = translator.translate(["Hello world"], source="en", target="vi")

    assert len(results) == 1
    translated = results[0]

    # Result must differ from input
    assert translated.strip().lower() != "hello world"

    # Result must contain Vietnamese diacritics (e.g. 'Xin chào thế giới')
    has_diacritic = any(char in VIETNAMESE_DIACRITICS for char in translated)
    assert has_diacritic, f"Expected Vietnamese diacritic in translation: '{translated}'"
