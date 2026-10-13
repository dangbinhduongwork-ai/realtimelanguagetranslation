"""Unit tests for SettleGate motion debouncing."""

from __future__ import annotations

from pathlib import Path
import sys

# Ensure src/ is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from screen_translator.capture.settle import SettleGate  # noqa: E402


class FakeClock:
    """Controllable monotonic clock for testing."""

    def __init__(self, start: float = 0.0) -> None:
        self._current = start

    def __call__(self) -> float:
        return self._current

    def advance(self, seconds: float) -> None:
        self._current += seconds


def test_settle_gate_fires_after_stillness() -> None:
    """Test that SettleGate fires after settle_ms of stillness."""
    clock = FakeClock(10.0)
    gate = SettleGate(settle_ms=300, max_wait_ms=1500, clock=clock)

    # Initial tick: change detected, but screen is moving
    assert gate.observe(changed=True, moving=True) is False
    assert gate.is_pending is True

    # Moving for 200 ms: should not fire
    clock.advance(0.200)
    assert gate.observe(changed=False, moving=True) is False

    # Motion stops! First still tick: still timer starts
    clock.advance(0.100)
    assert gate.observe(changed=False, moving=False) is False

    # Still for 200 ms total (< 300 ms): should not fire yet
    clock.advance(0.100)
    assert gate.observe(changed=False, moving=False) is False

    # Still for 350 ms total (>= 300 ms): fires!
    clock.advance(0.150)
    assert gate.observe(changed=False, moving=False) is True

    # After firing, gate is reset
    assert gate.is_pending is False


def test_settle_gate_does_not_fire_while_moving() -> None:
    """Test that SettleGate holds back OCR while screen is actively moving."""
    clock = FakeClock(0.0)
    gate = SettleGate(settle_ms=300, max_wait_ms=1500, clock=clock)

    assert gate.observe(changed=True, moving=True) is False

    # Continuous motion for 1000 ms (< 1500 ms max_wait)
    for _ in range(10):
        clock.advance(0.100)
        assert gate.observe(changed=True, moving=True) is False


def test_settle_gate_fires_at_max_wait_ms_while_moving() -> None:
    """Test that continuous motion forces a refresh once max_wait_ms is reached."""
    clock = FakeClock(0.0)
    gate = SettleGate(settle_ms=300, max_wait_ms=1000, clock=clock)

    # Change begins
    assert gate.observe(changed=True, moving=True) is False

    # Moving for 900 ms (< 1000 ms)
    clock.advance(0.900)
    assert gate.observe(changed=False, moving=True) is False

    # Moving for 1050 ms (>= 1000 ms): forces fire!
    clock.advance(0.150)
    assert gate.observe(changed=False, moving=True) is True

    # Resets after firing
    assert gate.is_pending is False


def test_settle_gate_pending_change_persists_across_ticks() -> None:
    """Test that once changed is seen, pending state persists even if changed is False next ticks."""
    clock = FakeClock(0.0)
    gate = SettleGate(settle_ms=300, max_wait_ms=1500, clock=clock)

    # Tick 1: change seen
    assert gate.observe(changed=True, moving=True) is False
    assert gate.is_pending is True

    # Tick 2, 3: changed is now False, but screen is still moving
    clock.advance(0.100)
    assert gate.observe(changed=False, moving=True) is False
    assert gate.is_pending is True

    clock.advance(0.100)
    assert gate.observe(changed=False, moving=True) is False
    assert gate.is_pending is True

    # Tick 4: motion stops, still for 350 ms -> fires!
    clock.advance(0.100)
    assert gate.observe(changed=False, moving=False) is False
    clock.advance(0.350)
    assert gate.observe(changed=False, moving=False) is True


def test_settle_gate_resets_after_firing() -> None:
    """Test that SettleGate returns to idle state after firing until next change."""
    clock = FakeClock(0.0)
    gate = SettleGate(settle_ms=200, max_wait_ms=1000, clock=clock)

    # Change and settle
    assert gate.observe(changed=True, moving=False) is False
    clock.advance(0.250)
    assert gate.observe(changed=False, moving=False) is True

    # Next tick with no change: returns False
    clock.advance(0.100)
    assert gate.observe(changed=False, moving=False) is False


def test_settle_gate_disabled_when_zero() -> None:
    """Test that settle_ms=0 disables debouncing and passes changed through immediately."""
    clock = FakeClock(0.0)
    gate = SettleGate(settle_ms=0, max_wait_ms=1500, clock=clock)

    assert gate.observe(changed=True, moving=True) is True
    assert gate.observe(changed=False, moving=True) is False
    assert gate.observe(changed=True, moving=False) is True
