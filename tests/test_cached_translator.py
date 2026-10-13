"""Unit tests for CachedTranslator decorator."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

# Ensure src/ is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from screen_translator.translate.base import TranslationError, Translator  # noqa: E402
from screen_translator.translate.cache import CachedTranslator, TranslationCache  # noqa: E402


class FakeTranslator(Translator):
    """Mock translator tracking call counts and received texts."""

    def __init__(self) -> None:
        self.call_count: int = 0
        self.received_batches: list[list[str]] = []

    def translate(
        self,
        texts: list[str],
        source: str = "en",
        target: str = "vi",
    ) -> list[str]:
        self.call_count += 1
        self.received_batches.append(list(texts))
        return [f"VI({t})" for t in texts]


class FailingTranslator(Translator):
    """Mock translator that unconditionally raises TranslationError."""

    def translate(
        self,
        texts: list[str],
        source: str = "en",
        target: str = "vi",
    ) -> list[str]:
        raise TranslationError("Simulated network outage")


def test_second_identical_call_uses_cache() -> None:
    """Test that subsequent identical queries trigger 0 calls to inner translator."""
    fake = FakeTranslator()
    cache = TranslationCache(max_size=100)
    cached_trans = CachedTranslator(inner=fake, cache=cache)

    res1 = cached_trans.translate(["Welcome user"])
    assert res1 == ["VI(Welcome user)"]
    assert fake.call_count == 1

    # Second identical call
    res2 = cached_trans.translate(["Welcome user"])
    assert res2 == ["VI(Welcome user)"]
    assert fake.call_count == 1  # No additional call!


def test_duplicates_in_single_batch_translated_once() -> None:
    """Test that duplicated texts within the same batch are deduplicated for the inner call."""
    fake = FakeTranslator()
    cache = TranslationCache(max_size=100)
    cached_trans = CachedTranslator(inner=fake, cache=cache)

    batch = ["apple", "apple", "banana", "apple"]
    res = cached_trans.translate(batch)

    assert fake.call_count == 1
    assert fake.received_batches[0] == ["apple", "banana"]
    assert res == ["VI(apple)", "VI(apple)", "VI(banana)", "VI(apple)"]


def test_non_translatable_texts_never_reach_inner() -> None:
    """Test that numbers, symbols, and already-target texts bypass inner translator."""
    fake = FakeTranslator()
    cache = TranslationCache(max_size=100)
    cached_trans = CachedTranslator(inner=fake, cache=cache)

    batch = ["123", "---", "Hello", "Xin chào bạn"]
    res = cached_trans.translate(batch)

    assert fake.call_count == 1
    assert fake.received_batches[0] == ["Hello"]
    assert res == ["123", "---", "VI(Hello)", "Xin chào bạn"]


def test_order_is_strictly_preserved() -> None:
    """Test that original text order is preserved with mixed cached, uncached, and bypassed items."""
    fake = FakeTranslator()
    cache = TranslationCache(max_size=100)
    cache.put("two", "en", "vi", "CACHED_TWO")
    cached_trans = CachedTranslator(inner=fake, cache=cache)

    batch = ["one", "two", "999", "three"]
    res = cached_trans.translate(batch)

    assert fake.call_count == 1
    assert fake.received_batches[0] == ["one", "three"]
    assert res == ["VI(one)", "CACHED_TWO", "999", "VI(three)"]


def test_failing_inner_translator_caches_nothing() -> None:
    """Test that when inner translator raises TranslationError, nothing is cached."""
    failing = FailingTranslator()
    cache = TranslationCache(max_size=100)
    cached_trans = CachedTranslator(inner=failing, cache=cache)

    with pytest.raises(TranslationError, match="Simulated network outage"):
        cached_trans.translate(["test failing text"])

    assert len(cache) == 0
    assert cache.get("test failing text", "en", "vi") is None
