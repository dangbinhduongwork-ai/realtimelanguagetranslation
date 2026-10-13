"""Translation subpackage exposing translators, cache, filters, and factory."""

from __future__ import annotations

from typing import Any

from screen_translator.translate.base import TranslationError, Translator
from screen_translator.translate.cache import CachedTranslator, TranslationCache
from screen_translator.translate.filters import needs_translation
from screen_translator.translate.google_translator import GoogleTranslator

__all__ = [
    "Translator",
    "GoogleTranslator",
    "TranslationCache",
    "CachedTranslator",
    "TranslationError",
    "needs_translation",
    "build_translator",
]


def build_translator(cfg: Any) -> CachedTranslator:
    """Factory creating a CachedTranslator configured from AppConfig or TranslateConfig.

    Args:
        cfg: AppConfig or TranslateConfig instance.

    Returns:
        CachedTranslator: Configured translator decorator with LRU cache.

    Raises:
        ValueError: If provider is unrecognized.
    """
    translate_cfg = cfg.translate if hasattr(cfg, "translate") else cfg
    provider = getattr(translate_cfg, "provider", "google")
    cache_size = getattr(translate_cfg, "cache_size", 2000)

    supported = ["google"]
    if provider == "google":
        inner = GoogleTranslator()
        cache = TranslationCache(max_size=cache_size)
        return CachedTranslator(inner=inner, cache=cache)

    raise ValueError(f"Unknown translation provider: '{provider}'. Supported providers: {supported}")
