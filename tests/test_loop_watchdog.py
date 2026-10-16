"""Unit tests for LoopWatchdog rate-limiter with fake clock."""

from __future__ import annotations

from screen_translator.utils.loop_watchdog import LoopWatchdog


class FakeClock:
    """Deterministic fake clock advancing time manually."""

    def __init__(self, start: float = 1000.0) -> None:
        self.current_time = start

    def __call__(self) -> float:
        return self.current_time

    def advance(self, seconds: float) -> None:
        self.current_time += seconds


def test_watchdog_normal_rate() -> None:
    """Verifies that runs below 6 per 10s trigger no cooldown."""
    clock = FakeClock()
    warnings: list[str] = []
    dog = LoopWatchdog(
        max_runs=6,
        window_seconds=10.0,
        cooldown_seconds=2.0,
        clock=clock,
        on_warning=warnings.append,
    )

    # 5 runs spaced 1.5s apart: within 10s, count <= 6 -> no cooldown
    for _ in range(5):
        cooldown = dog.record_run()
        assert cooldown == 0.0
        clock.advance(1.5)

    assert len(warnings) == 0


def test_watchdog_feedback_loop_triggers_cooldown() -> None:
    """Verifies that exceeding 6 runs in 10s enforces 2.0s cooldown and emits warning once."""
    clock = FakeClock()
    warnings: list[str] = []
    dog = LoopWatchdog(
        max_runs=6,
        window_seconds=10.0,
        cooldown_seconds=2.0,
        clock=clock,
        on_warning=warnings.append,
    )

    # 6 runs in rapid succession (1s each = 6 runs in 6s)
    for _ in range(6):
        cooldown = dog.record_run()
        assert cooldown == 0.0
        clock.advance(1.0)

    # 7th run at 7.0s (still within 10s window, count=7 > 6)
    cooldown7 = dog.record_run()
    assert cooldown7 == 2.0
    assert len(warnings) == 1

    # 8th run immediately after: cooldown continues, but warning is NOT spammed
    cooldown8 = dog.record_run()
    assert cooldown8 == 2.0
    assert len(warnings) == 1

    # Advance beyond 10s window (to 20.0s) -> old runs evicted
    clock.advance(11.0)
    cooldown_after = dog.record_run()
    assert cooldown_after == 0.0
