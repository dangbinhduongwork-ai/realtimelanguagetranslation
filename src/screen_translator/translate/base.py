"""Abstract base class for translation engines."""

from __future__ import annotations

from abc import ABC, abstractmethod


class Translator(ABC):
    """Abstract interface for text translation providers."""

    @abstractmethod
    def translate(
        self,
        texts: list[str],
        source: str = "en",
        target: str = "vi",
    ) -> list[str]:
        """Translate a batch of strings from source language to target language.

        Args:
            texts: List of input strings to translate.
            source: Source language ISO code (e.g., 'en').
            target: Target language ISO code (e.g., 'vi').

        Returns:
            list[str]: Translated strings corresponding to input texts in order.
        """
