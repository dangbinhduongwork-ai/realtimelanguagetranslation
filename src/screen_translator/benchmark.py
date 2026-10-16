"""Performance benchmark utility measuring pipeline component latencies and CPU load."""

from __future__ import annotations

import argparse
import time
import numpy as np

from screen_translator.app import (
    create_capturer,
    create_detector,
    create_ocr_engine,
    create_translator,
)
from screen_translator.config import load_config
from screen_translator.logging_setup import setup_logging
from screen_translator.models import Region
from screen_translator.ocr.grouping import group_lines
from screen_translator.utils.win_utils import enable_dpi_awareness


def _parse_region(region_str: str | None) -> Region | None:
    """Parse comma-separated 'L,T,W,H' into a Region dataclass."""
    if not region_str:
        return None
    try:
        parts = [int(p.strip()) for p in region_str.split(",")]
        if len(parts) == 4:
            return Region(left=parts[0], top=parts[1], width=parts[2], height=parts[3])
    except Exception:
        pass
    return None


def run_bench(args: argparse.Namespace) -> int:
    """Execute performance benchmark on current screen or region.

    Forces capture, change detection, OCR, grouping, and translation on every frame
    to measure peak execution timings and compute 95th percentile metrics.

    Args:
        args: Parsed CLI arguments containing frames, monitor, region, no_translate.

    Returns:
        int: Exit status code (0 on success).
    """
    enable_dpi_awareness()
    config = load_config()

    # Suppress verbose debug logs during benchmark output
    setup_logging(level=getattr(args, "log_level", None) or "WARNING")

    target_region = _parse_region(getattr(args, "region", None))
    if target_region is None and config.capture.region:
        target_region = Region(*config.capture.region)

    mon_idx = getattr(args, "monitor", None) if getattr(args, "monitor", None) is not None else config.capture.monitor
    num_frames = max(1, getattr(args, "frames", 20))
    use_translation = not getattr(args, "no_translate", False)

    capturer = create_capturer(config, monitor=mon_idx)
    detector = create_detector(config)
    ocr_engine = create_ocr_engine(config)
    translator = create_translator(config) if use_translation else None

    if hasattr(ocr_engine, "warmup"):
        ocr_engine.warmup()

    print(f"\n[Bench] Warming up and capturing {num_frames} frames (monitor={mon_idx}, region={target_region})...")

    cap_ms: list[float] = []
    diff_ms: list[float] = []
    ocr_ms: list[float] = []
    grp_ms: list[float] = []
    trn_ms: list[float] = []
    tot_ms: list[float] = []

    t_wall_start = time.perf_counter()
    t_proc_start = time.process_time()

    try:
        for _ in range(num_frames):
            t0 = time.perf_counter()
            frame = capturer.grab(target_region)
            t1 = time.perf_counter()

            detector.has_changed(frame.image)
            t2 = time.perf_counter()

            offset = (frame.region.left, frame.region.top)
            raw_blocks = ocr_engine.recognize(frame.image, offset=offset)
            t3 = time.perf_counter()

            if config.ocr.merge_lines and raw_blocks:
                blocks = group_lines(raw_blocks, max_gap_ratio=config.ocr.max_gap_ratio)
            else:
                blocks = raw_blocks
            t4 = time.perf_counter()

            if use_translation and translator and blocks:
                texts = [b.text for b in blocks]
                translator.translate(texts)
            t5 = time.perf_counter()

            cap_ms.append((t1 - t0) * 1000.0)
            diff_ms.append((t2 - t1) * 1000.0)
            ocr_ms.append((t3 - t2) * 1000.0)
            grp_ms.append((t4 - t3) * 1000.0)
            if use_translation:
                trn_ms.append((t5 - t4) * 1000.0)
            tot_ms.append((t5 - t0) * 1000.0)
    finally:
        capturer.close()

    t_wall_end = time.perf_counter()
    t_proc_end = time.process_time()

    wall_duration = max(0.001, t_wall_end - t_wall_start)
    proc_duration = max(0.0, t_proc_end - t_proc_start)
    cpu_percent = (proc_duration / wall_duration) * 100.0

    factor = getattr(ocr_engine, "current_upscale_factor", 1.0)

    def stats(arr: list[float]) -> tuple[float, float, float, float]:
        if not arr:
            return (0.0, 0.0, 0.0, 0.0)
        return (
            float(np.mean(arr)),
            float(np.percentile(arr, 95)),
            float(np.min(arr)),
            float(np.max(arr)),
        )

    print("\n" + "=" * 68)
    print("                SCREEN TRANSLATOR PERFORMANCE BENCHMARK")
    print("=" * 68)
    print(f"  Frames measured    : {num_frames}")
    print(f"  Capture backend    : {capturer.__class__.__name__} ({config.capture.backend})")
    print(f"  Active upscale     : {factor:.1f}x (config: {config.ocr.upscale})")
    print(f"  Translation        : {'Enabled (batch: ' + config.translate.batch_mode + ')' if use_translation else 'Disabled (--no-translate)'}")
    print(f"  Approx CPU usage   : {cpu_percent:.1f}%")
    print("-" * 68)
    print(f"  {'Pipeline Stage':<22} {'Mean (ms)':>10} {'p95 (ms)':>10} {'Min (ms)':>10} {'Max (ms)':>10}")
    print("-" * 68)

    cap_name = f"Capture ({config.capture.backend.upper()})"
    for name, data in [
        (cap_name, cap_ms),
        ("Diff (cv2.absdiff)", diff_ms),
        ("OCR (RapidOCR)", ocr_ms),
        ("Grouping", grp_ms),
    ]:
        m, p, mn, mx = stats(data)
        print(f"  {name:<22} {m:>10.2f} {p:>10.2f} {mn:>10.2f} {mx:>10.2f}")

    if use_translation:
        m, p, mn, mx = stats(trn_ms)
        print(f"  {'Translate (Batch/LRU)':<22} {m:>10.2f} {p:>10.2f} {mn:>10.2f} {mx:>10.2f}")

    print("-" * 68)
    m, p, mn, mx = stats(tot_ms)
    print(f"  {'Total Pipeline':<22} {m:>10.2f} {p:>10.2f} {mn:>10.2f} {mx:>10.2f}")
    print("=" * 68 + "\n")

    return 0
