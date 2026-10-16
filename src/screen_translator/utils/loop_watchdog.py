"""Loop watchdog to detect and rate-limit OCR feedback loops."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
import logging
import time

logger = logging.getLogger(__name__)


class LoopWatchdog:
    """Monitors OCR execution frequency and enforces backoff when a feedback loop is detected."""

    def __init__(
        self,
        max_runs: int = 16,
        window_seconds: float = 10.0,
        cooldown_seconds: float = 2.0,
        clock: Callable[[], float] = time.monotonic,
        on_warning: Callable[[str], None] | None = None,
    ) -> None:
        """Initialize loop watchdog.

        Args:
            max_runs: Maximum allowed runs within window_seconds before triggering limiter.
            window_seconds: Time window for counting OCR runs (default 10.0s).
            cooldown_seconds: Minimum delay between runs during feedback loop (default 2.0s).
            clock: Time function returning seconds (for deterministic testing).
            on_warning: Optional callback invoked when watchdog triggers.
        """
        self.max_runs = max_runs
        self.window_seconds = window_seconds
        self.cooldown_seconds = cooldown_seconds
        self.clock = clock
        self.on_warning = on_warning

        self._run_timestamps: deque[float] = deque()
        self._last_warning_time: float = 0.0
        self._last_run_time: float = 0.0

    def record_run(self) -> float:
        """Record an OCR run and return recommended backoff sleep in seconds (0.0 if normal).

        Returns:
            float: Recommended delay in seconds before next run.
        """
        now = self.clock()
        self._last_run_time = now

        # Evict timestamps outside rolling window
        cutoff = now - self.window_seconds
        while self._run_timestamps and self._run_timestamps[0] < cutoff:
            self._run_timestamps.popleft()

        self._run_timestamps.append(now)

        # Check threshold
        if len(self._run_timestamps) > self.max_runs:
            msg = "possible feedback loop: high OCR execution rate detected"
            # Log warning once per active window episode
            if now - self._last_warning_time > self.window_seconds:
                logger.warning(msg)
                self._last_warning_time = now
                if self.on_warning:
                    self.on_warning("Possible feedback loop detected; rate limiter active.")
            return self.cooldown_seconds

        return 0.0

    def reset(self) -> None:
        """Reset watchdog history."""
        self._run_timestamps.clear()
        self._last_warning_time = 0.0
