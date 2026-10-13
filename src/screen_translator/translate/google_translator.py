"""Google Translator provider via deep-translator with concurrency and retry logic."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import re
import time

from deep_translator import GoogleTranslator as DeepGoogleTranslator

from screen_translator.translate.base import TranslationError, Translator

logger = logging.getLogger(__name__)

MAX_CHARACTERS_PER_REQUEST = 4500
MAX_CONCURRENT_WORKERS = 4
RETRY_DELAYS_SECONDS = (0.5, 1.0)


def _split_into_chunks(text: str, max_chars: int = MAX_CHARACTERS_PER_REQUEST) -> list[str]:
    """Split text longer than max_chars at sentence boundaries or whitespace."""
    if len(text) <= max_chars:
        return [text]

    sentences = re.split(r"(?<=[.!?\n])\s+", text)
    chunks: list[str] = []
    current_chunk = ""

    for sentence in sentences:
        if not sentence.strip():
            continue

        if len(current_chunk) + len(sentence) + 1 <= max_chars:
            current_chunk = f"{current_chunk} {sentence}".strip() if current_chunk else sentence
        else:
            if current_chunk:
                chunks.append(current_chunk)

            # If a single sentence exceeds max_chars, split by words
            if len(sentence) > max_chars:
                words = sentence.split()
                sub_chunk = ""
                for word in words:
                    if len(sub_chunk) + len(word) + 1 <= max_chars:
                        sub_chunk = f"{sub_chunk} {word}".strip() if sub_chunk else word
                    else:
                        if sub_chunk:
                            chunks.append(sub_chunk)
                        sub_chunk = word
                if sub_chunk:
                    chunks.append(sub_chunk)
                current_chunk = ""
            else:
                current_chunk = sentence

    if current_chunk:
        chunks.append(current_chunk)

    return chunks if chunks else [text]


class GoogleTranslator(Translator):
    """Translates text batches concurrently using deep-translator with retries and chunking."""

    def __init__(self, max_workers: int = MAX_CONCURRENT_WORKERS) -> None:
        """Initialize GoogleTranslator client.

        Args:
            max_workers: Maximum number of worker threads for concurrent translation.
        """
        self.max_workers = max_workers

    def _translate_single(self, text: str, source: str, target: str) -> str:
        """Translate a single text string with chunking and exponential backoff retry.

        Args:
            text: Input string.
            source: Source language code.
            target: Target language code.

        Returns:
            str: Translated text.

        Raises:
            TranslationError: If all retry attempts fail.
        """
        if not text.strip():
            return text

        translator_client = DeepGoogleTranslator(source=source, target=target)
        chunks = _split_into_chunks(text)
        translated_chunks: list[str] = []

        for chunk in chunks:
            chunk_to_translate = chunk.strip()
            if not chunk_to_translate:
                continue

            last_error: Exception | None = None
            translated_part: str | None = None

            total_attempts = len(RETRY_DELAYS_SECONDS) + 1
            for attempt in range(total_attempts):
                try:
                    res = translator_client.translate(chunk_to_translate)
                    if res is not None:
                        translated_part = res
                        break
                except Exception as exc:
                    last_error = exc
                    if attempt < len(RETRY_DELAYS_SECONDS):
                        delay = RETRY_DELAYS_SECONDS[attempt]
                        logger.warning(
                            "Translation error on attempt %d/%d (backing off %.1fs): %s",
                            attempt + 1,
                            total_attempts,
                            delay,
                            exc,
                        )
                        time.sleep(delay)

            if translated_part is None:
                err_msg = (
                    f"Google translation failed after {total_attempts} attempts "
                    f"for text '{chunk_to_translate[:60]}...': {last_error}"
                )
                logger.error(err_msg)
                raise TranslationError(err_msg) from last_error

            translated_chunks.append(translated_part)

        return " ".join(translated_chunks)

    def translate(
        self,
        texts: list[str],
        source: str = "en",
        target: str = "vi",
    ) -> list[str]:
        """Translate a batch of texts concurrently preserving order.

        Args:
            texts: List of strings to translate.
            source: Source language code.
            target: Target language code.

        Returns:
            list[str]: Translated output strings in corresponding order.

        Raises:
            TranslationError: If any item fails translation after retries.
        """
        if not texts:
            return []

        # Execute concurrent calls using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(texts))) as executor:
            futures = [
                executor.submit(self._translate_single, text, source, target)
                for text in texts
            ]
            # Collecting in order of submitted futures ensures matching index output
            results = [f.result() for f in futures]

        return results
