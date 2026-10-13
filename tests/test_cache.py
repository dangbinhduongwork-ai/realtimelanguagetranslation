"""Unit tests for thread-safe TranslationCache."""

from __future__ import annotations

from pathlib import Path
import sys
import threading

import pytest

# Ensure src/ is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from screen_translator.translate.cache import TranslationCache  # noqa: E402


def test_cache_lru_eviction() -> None:
    """Test that least-recently-used entry is evicted when capacity is exceeded."""
    cache = TranslationCache(max_size=2)
    cache.put("one", "en", "vi", "một")
    cache.put("two", "en", "vi", "hai")

    # Accessing none yet; oldest is "one"
    cache.put("three", "en", "vi", "ba")

    assert len(cache) == 2
    assert cache.get("one", "en", "vi") is None  # evicted
    assert cache.get("two", "en", "vi") == "hai"
    assert cache.get("three", "en", "vi") == "ba"


def test_cache_get_refreshes_recency() -> None:
    """Test that get() moves entry to most recent, preventing its eviction."""
    cache = TranslationCache(max_size=2)
    cache.put("one", "en", "vi", "một")
    cache.put("two", "en", "vi", "hai")

    # Accessing "one" makes it MRU; "two" becomes LRU
    val = cache.get("one", "en", "vi")
    assert val == "một"

    cache.put("three", "en", "vi", "ba")

    assert len(cache) == 2
    assert cache.get("two", "en", "vi") is None  # "two" evicted
    assert cache.get("one", "en", "vi") == "một"
    assert cache.get("three", "en", "vi") == "ba"


def test_cache_whitespace_normalization() -> None:
    """Test that irregular whitespaces are normalized to a consistent key."""
    cache = TranslationCache(max_size=5)
    cache.put("  Hello   World  \n", "en", "vi", "Xin chào thế giới")

    assert cache.get("Hello World", "en", "vi") == "Xin chào thế giới"
    assert cache.get("  Hello \t World ", "en", "vi") == "Xin chào thế giới"


def test_cache_stats() -> None:
    """Test hits and misses counters."""
    cache = TranslationCache(max_size=5)
    assert cache.stats() == (0, 0)

    # Miss
    assert cache.get("unknown", "en", "vi") is None
    assert cache.stats() == (0, 1)

    # Put and Hit
    cache.put("known", "en", "vi", "biết")
    assert cache.get("known", "en", "vi") == "biết"
    assert cache.stats() == (1, 1)
    assert cache.hits == 1
    assert cache.misses == 1


def test_cache_thread_safety() -> None:
    """Test concurrent reads and writes across multiple threads without corruption."""
    cache = TranslationCache(max_size=50)
    errors: list[Exception] = []

    def worker(worker_id: int) -> None:
        try:
            for i in range(100):
                text = f"word_{worker_id}_{i % 20}"
                cache.put(text, "en", "vi", f"trans_{text}")
                cache.get(text, "en", "vi")
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(tid,)) for tid in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Encountered thread exceptions: {errors}"
    assert len(cache) <= 50
