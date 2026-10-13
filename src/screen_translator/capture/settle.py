"""Settle gate to debounce screen motion (scrolling, slide transitions)."""

from __future__ import annotations

from collections.abc import Callable
import logging
import time

logger = logging.getLogger(__name__)


class SettleGate:
    """Delays OCR until screen motion has settled or maximum wait duration expires.

    - Remember a pending change once `changed` is observed (persists across ticks).
    - Fires (returns True) when screen is not moving for `settle_ms` of stillness.
    - Fires (returns True) when `max_wait_ms` has elapsed since change started, ensuring
      continuous motion or animations (e.g., video) still refresh periodically.
    - If `settle_ms <= 0`, gate is disabled and immediately returns `changed`.
    """

    def __init__(
        self,
        settle_ms: int = 300,
        max_wait_ms: int = 1500,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Initialize SettleGate.

        Args:
            settle_ms: Minimum duration of stillness (ms) required before triggering OCR.
                       0 or negative disables the gate.
            max_wait_ms: Maximum duration (ms) to wait while motion continues before forcing OCR.
            clock: Monotonic time supplier (seconds float), injectable for testing.
        """
        self.settle_ms = max(0, int(settle_ms))
        self.max_wait_ms = max(0, int(max_wait_ms))
        self.clock = clock

        self._pending_change: bool = False
        self._pending_start_time: float | None = None
        self._still_start_time: float | None = None

    @property
    def is_pending(self) -> bool:
        """Return True if a change is currently waiting to settle."""
        return self._pending_change

    def reset(self) -> None:
        """Reset pending change and stillness timers."""
        self._pending_change = False
        self._pending_start_time = None
        self._still_start_time = None

    def observe(self, changed: bool, moving: bool) -> bool:
        """Observe change and motion indicators for the current frame tick.

        Args:
            changed: Whether frame differs from the last settled/processed reference.
            moving: Whether frame differs from the immediately previous frame tick.

        Returns:
            bool: True if pipeline should run OCR on this frame; False otherwise.
        """
        if self.settle_ms <= 0:
            # Gate disabled: pass through change detection directly
            return changed

        now = self.clock()

        # Rule 1: Remember a pending change once seen; persists across subsequent ticks
        if changed and not self._pending_change:
            self._pending_change = True
            self._pending_start_time = now
            self._still_start_time = None if moving else now

        if not self._pending_change:
            self._still_start_time = None
            return False

        # Rule 2: Force fire if max_wait_ms has elapsed since pending change began
        if self._pending_start_time is not None:
            elapsed_pending_ms = (now - self._pending_start_time) * 1000.0
            if elapsed_pending_ms >= self.max_wait_ms:
                logger.debug("SettleGate: Forced fire after max_wait_ms (%.1f ms)", elapsed_pending_ms)
                self.reset()
                return True

        # Rule 3: Stillness tracking
        if moving:
            # Screen is actively moving -> reset stillness timer
            self._still_start_time = None
            return False

        # Not moving: start or check stillness duration
        if self._still_start_time is None:
            self._still_start_time = now

        still_elapsed_ms = (now - self._still_start_time) * 1000.0
        if still_elapsed_ms >= self.settle_ms:
            logger.debug("SettleGate: Fired after screen settled (%.1f ms still)", still_elapsed_ms)
            self.reset()
            return True

        return False
