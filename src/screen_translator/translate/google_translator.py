from concurrent.futures import ThreadPoolExecutor
import logging
import re
import threading
import time

from deep_translator import GoogleTranslator as DeepGoogleTranslator
import requests
from requests.adapters import HTTPAdapter

from screen_translator.translate.base import TranslationError, Translator

logger = logging.getLogger(__name__)

MAX_CHARACTERS_PER_REQUEST = 4500
MAX_CONCURRENT_WORKERS = 4
RETRY_DELAYS_SECONDS = (0.5, 1.0)

DEFAULT_CLIENTS = ("dict-chrome-ex", "gtx", "webapp")
_client_lock = threading.Lock()
_current_client_idx: int = 0

_session: requests.Session | None = None
_session_lock = threading.Lock()

_rate_lock = threading.Lock()
_last_request_time: float = 0.0
_MIN_REQUEST_INTERVAL: float = 0.15  # Pacing between calls


def _get_session() -> requests.Session:
    """Thread-safe lazy initialization of requests.Session with connection pooling."""
    global _session
    if _session is None:
        with _session_lock:
            if _session is None:
                s = requests.Session()
                s.headers.update({
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/122.0.0.0 Safari/537.36"
                    )
                })
                adapter = HTTPAdapter(
                    pool_connections=MAX_CONCURRENT_WORKERS * 2,
                    pool_maxsize=MAX_CONCURRENT_WORKERS * 2,
                    max_retries=1,
                )
                s.mount("https://", adapter)
                s.mount("http://", adapter)
                _session = s
    return _session


def _pace_request() -> None:
    """Enforce minimum spacing between Google Translate requests across all worker threads without blocking."""
    global _last_request_time
    wait_time = 0.0
    with _rate_lock:
        now = time.monotonic()
        scheduled_time = max(now, _last_request_time + _MIN_REQUEST_INTERVAL)
        wait_time = scheduled_time - now
        _last_request_time = scheduled_time

    if wait_time > 0:
        time.sleep(wait_time)


def _direct_google_translate(text: str, source: str = "en", target: str = "vi") -> str:
    """Translate text using pooled HTTP session with browser User-Agent and client rotation."""
    global _current_client_idx
    session = _get_session()

    with _client_lock:
        start_idx = _current_client_idx

    last_error: Exception | None = None
    for attempt in range(len(DEFAULT_CLIENTS)):
        client_name = DEFAULT_CLIENTS[(start_idx + attempt) % len(DEFAULT_CLIENTS)]
        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            "client": client_name,
            "sl": source,
            "tl": target,
            "dt": "t",
            "q": text,
        }
        try:
            resp = session.get(url, params=params, timeout=8)
            if resp.status_code in (429, 403):
                logger.warning(
                    "Google Translate client '%s' returned HTTP %d, rotating to next client...",
                    client_name,
                    resp.status_code,
                )
                with _client_lock:
                    _current_client_idx = (start_idx + attempt + 1) % len(DEFAULT_CLIENTS)
                continue

            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list) and len(data) > 0 and isinstance(data[0], list):
                res = "".join(segment[0] for segment in data[0] if segment and len(segment) > 0 and segment[0])
                if res.strip():
                    return res
            return text
        except requests.HTTPError as exc:
            last_error = exc
            status = exc.response.status_code if exc.response is not None else 0
            if status in (429, 403):
                logger.warning(
                    "Google Translate client '%s' raised HTTP %d: %s. Rotating...",
                    client_name,
                    status,
                    exc,
                )
                with _client_lock:
                    _current_client_idx = (start_idx + attempt + 1) % len(DEFAULT_CLIENTS)
                continue
            raise
        except Exception as exc:
            last_error = exc
            raise

    if last_error:
        raise last_error
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

    def __init__(
        self,
        max_workers: int = MAX_CONCURRENT_WORKERS,
        batch_mode: str = "joined",
    ) -> None:
        """Initialize GoogleTranslator client.

        Args:
            max_workers: Maximum number of worker threads for concurrent translation.
            batch_mode: Batching mode ('joined' or 'per_item').
        """
        self.max_workers = max_workers
        self.batch_mode = batch_mode
        self._api_call_count: int = 0
        self._call_count_lock = threading.Lock()

    def get_and_reset_api_calls(self) -> int:
        """Atomically return and reset the count of HTTP API requests made."""
        with self._call_count_lock:
            calls = self._api_call_count
            self._api_call_count = 0
            return calls

    def _record_api_call(self) -> None:
        """Increment API call counter."""
        with self._call_count_lock:
            self._api_call_count += 1

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
                    self._record_api_call()
                    # 1. Primary: Direct HTTP query with browser User-Agent
                    translated_part = _direct_google_translate(chunk_to_translate, source=source, target=target)
                    if translated_part and translated_part.strip():
                        break
                except Exception as exc:
                    last_error = exc
                    # 2. Secondary fallback: DeepGoogleTranslator
                    try:
                        self._record_api_call()
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

    def _translate_chunk(self, chunk: list[str], source: str, target: str) -> list[str]:
        """Translate a chunk of joined strings and verify count, falling back to per-item on mismatch."""
        if not chunk:
            return []
        if len(chunk) == 1:
            return [self._translate_single(chunk[0], source, target)]

        joined_query = "\n".join(chunk)
        res_joined = self._translate_single(joined_query, source, target)

        parts = [p.strip() for p in res_joined.split("\n")]
        # Count check
        if len(parts) == len(chunk):
            return parts

        logger.warning(
            "Joined batch count mismatch: expected %d items, got %d. Falling back to per-item for chunk.",
            len(chunk),
            len(parts),
        )
        return [self._translate_single(item, source, target) for item in chunk]

    def _translate_joined_batch(
        self,
        texts: list[str],
        source: str,
        target: str,
    ) -> list[str]:
        """Translate batch by joining texts with '\\n' into requests of <= 4500 chars."""
        # 1. Normalize texts so none contain internal newlines
        cleaned = [re.sub(r"[\r\n]+", " ", t).strip() for t in texts]

        # 2. Partition into chunks <= 4500 characters
        chunks: list[list[str]] = []
        current_chunk: list[str] = []
        current_len: int = 0

        for t in cleaned:
            # 1 char for '\n' separator
            item_len = len(t) + (1 if current_chunk else 0)
            if current_chunk and (current_len + item_len > MAX_CHARACTERS_PER_REQUEST):
                chunks.append(current_chunk)
                current_chunk = [t]
                current_len = len(t)
            else:
                current_chunk.append(t)
                current_len += item_len

        if current_chunk:
            chunks.append(current_chunk)

        # 3. Translate chunks concurrently with ThreadPoolExecutor
        workers = min(self.max_workers, max(1, len(chunks)))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [
                executor.submit(self._translate_chunk, chunk, source, target)
                for chunk in chunks
            ]
            chunk_results = [f.result() for f in futures]

        # Flatten chunk results preserving original order
        results: list[str] = []
        for c_res in chunk_results:
            results.extend(c_res)

        return results

    def translate(
        self,
        texts: list[str],
        source: str = "en",
        target: str = "vi",
    ) -> list[str]:
        """Translate a batch of texts preserving order.

        Uses joined batching when batch_mode='joined', or per-item execution when batch_mode='per_item'.
        """
        if not texts:
            return []

        if self.batch_mode == "joined":
            return self._translate_joined_batch(texts, source, target)

        # per_item mode
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(texts))) as executor:
            futures = [
                executor.submit(self._translate_single, text, source, target)
                for text in texts
            ]
            return [f.result() for f in futures]
