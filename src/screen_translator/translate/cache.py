"""Thread-safe in-memory LRU translation cache and CachedTranslator decorator."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Sequence
import logging
import threading

from screen_translator.translate.base import Translator
from screen_translator.translate.filters import needs_translation

logger = logging.getLogger(__name__)


def normalize_text(text: str) -> str:
    """Normalize text by collapsing consecutive whitespace and stripping ends."""
    return " ".join(text.strip().split())


class TranslationCache:
    """Thread-safe LRU translation cache implemented with OrderedDict and Lock."""

    def __init__(self, max_size: int = 2000) -> None:
        """Initialize the translation cache.

        Args:
            max_size: Maximum capacity before oldest (least recently used) entries are evicted.
        """
        self.max_size = max(0, int(max_size))
        self._cache: OrderedDict[tuple[str, str, str], str] = OrderedDict()
        self._lock = threading.Lock()
        self._hits: int = 0
        self._misses: int = 0

    @property
    def hits(self) -> int:
        """Total number of successful cache lookups."""
        with self._lock:
            return self._hits

    @property
    def misses(self) -> int:
        """Total number of cache misses."""
        with self._lock:
            return self._misses

    def stats(self) -> tuple[int, int]:
        """Return (hits, misses) tuple."""
        with self._lock:
            return (self._hits, self._misses)

    def get(self, text: str, source: str, target: str) -> str | None:
        """Lookup cached translation for normalized text, refreshing recency on hit."""
        key = (source, target, normalize_text(text))
        with self._lock:
            if key in self._cache:
                self._hits += 1
                self._cache.move_to_end(key)
                return self._cache[key]
            self._misses += 1
            return None

    def put(self, text: str, source: str, target: str, translated: str) -> None:
        """Store translation in cache, evicting LRU entry if capacity is exceeded."""
        if self.max_size <= 0:
            return

        key = (source, target, normalize_text(text))
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = translated
            if len(self._cache) > self.max_size:
                self._cache.popitem(last=False)

    def clear(self) -> None:
        """Clear all stored entries from the cache."""
        with self._lock:
            self._cache.clear()

    def __len__(self) -> int:
        """Return current number of items in cache."""
        with self._lock:
            return len(self._cache)


class CachedTranslator(Translator):
    """Decorator around a Translator providing caching, deduplication, and non-translatable filtering."""

    def __init__(self, inner: Translator, cache: TranslationCache) -> None:
        """Initialize cached decorator.

        Args:
            inner: Underlying Translator engine queried on cache misses.
            cache: Thread-safe TranslationCache storage instance.
        """
        self.inner = inner
        self.cache = cache

    def translate(
        self,
        texts: list[str],
        source: str = "en",
        target: str = "vi",
    ) -> list[str]:
        """Translate texts with caching, filtering, and deduplicated miss queries.

        1. Non-translatable texts (symbols, digits, target language) are returned unchanged.
        2. Known texts are served from cache without querying inner translator.
        3. Identical misses within the batch are deduplicated.
        4. Inner translator is called ONCE for the unique misses.
        5. Results are saved in cache and returned in original input order.
        """
        if not texts:
            return []

        results: list[str | None] = [None] * len(texts)
        misses_map: dict[str, list[int]] = {}

        for idx, text in enumerate(texts):
            # 1. Check if translation is needed
            if not needs_translation(text, source_lang=source):
                results[idx] = text
                continue

            # 2. Check cache
            cached_value = self.cache.get(text, source=source, target=target)
            if cached_value is not None:
                results[idx] = cached_value
            else:
                norm = normalize_text(text)
                misses_map.setdefault(norm, []).append(idx)

        # 3. Query inner translator for unique misses
        if misses_map:
            unique_misses = list(misses_map.keys())
            logger.debug(
                "Cache miss for %d unique texts (out of %d total items). Querying %s...",
                len(unique_misses),
                len(texts),
                type(self.inner).__name__,
            )

            # Any exception here bubbles up; failed results are NEVER cached
            translated_misses = self.inner.translate(unique_misses, source=source, target=target)

            for miss_text, translated_text in zip(unique_misses, translated_misses):
                self.cache.put(miss_text, source=source, target=target, translated=translated_text)
                for idx in misses_map[miss_text]:
                    results[idx] = translated_text

        return [res if res is not None else "" for res in results]

    def get_and_reset_api_calls(self) -> int:
        """Forward API call count retrieval to inner translator."""
        if hasattr(self.inner, "get_and_reset_api_calls"):
            return self.inner.get_and_reset_api_calls()
        return 0
