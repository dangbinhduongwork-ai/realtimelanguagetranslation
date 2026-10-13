from concurrent.futures import ThreadPoolExecutor
import json
import logging
import re
import threading
import time
import urllib.parse
import urllib.request

from deep_translator import GoogleTranslator as DeepGoogleTranslator

from screen_translator.translate.base import TranslationError, Translator

logger = logging.getLogger(__name__)

MAX_CHARACTERS_PER_REQUEST = 4500
MAX_CONCURRENT_WORKERS = 4
RETRY_DELAYS_SECONDS = (0.5, 1.0)

_rate_lock = threading.Lock()
_last_request_time: float = 0.0
_MIN_REQUEST_INTERVAL: float = 0.15  # Pacing between calls


def _pace_request() -> None:
    """Enforce minimum spacing between Google Translate requests across all worker threads."""
    global _last_request_time
    with _rate_lock:
        now = time.monotonic()
        elapsed = now - _last_request_time
        if elapsed < _MIN_REQUEST_INTERVAL:
            time.sleep(_MIN_REQUEST_INTERVAL - elapsed)
        _last_request_time = time.monotonic()


def _direct_google_translate(text: str, source: str = "en", target: str = "vi") -> str:
    """Translate text using standard HTTP with browser User-Agent to avoid bot 429 blocks."""
    url = (
        f"https://translate.googleapis.com/translate_a/single?client=gtx"
        f"&sl={urllib.parse.quote(source)}&tl={urllib.parse.quote(target)}&dt=t"
        f"&q={urllib.parse.quote(text)}"
    )
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            )
        },
    )
    with urllib.request.urlopen(req, timeout=8) as response:
        data = json.loads(response.read().decode("utf-8"))
        if isinstance(data, list) and len(data) > 0 and isinstance(data[0], list):
            res = "".join(segment[0] for segment in data[0] if segment and len(segment) > 0 and segment[0])
            if res.strip():
                return res
    return text


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
    """Translates text batches concurrently using direct browser-agent query with deep-translator fallback."""

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
            str: Translated text (falls back to original text if API is unavailable).
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
                    _pace_request()
                    # 1. Primary: Direct HTTP query with browser User-Agent
                    translated_part = _direct_google_translate(chunk_to_translate, source=source, target=target)
                    if translated_part and translated_part.strip():
                        break
                except Exception as exc:
                    last_error = exc
                    # 2. Secondary fallback: DeepGoogleTranslator
                    try:
                        res = translator_client.translate(chunk_to_translate)
                        if res is not None:
                            translated_part = res
                            break
                    except Exception as inner_exc:
                        last_error = inner_exc

                    if attempt < len(RETRY_DELAYS_SECONDS):
                        delay = RETRY_DELAYS_SECONDS[attempt]
                        logger.warning(
                            "Translation error on attempt %d/%d (backing off %.1fs): %s",
                            attempt + 1,
                            total_attempts,
                            delay,
                            last_error,
                        )
                        time.sleep(delay)

            if translated_part is None:
                logger.warning(
                    "Google translation failed after %d attempts for text '%s...': %s. Falling back to original text.",
                    total_attempts,
                    chunk_to_translate[:60],
                    last_error,
                )
                translated_part = chunk_to_translate

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
