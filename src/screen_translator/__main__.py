"""Main CLI entry point for Screen Translator."""

from __future__ import annotations

import argparse
from datetime import datetime
import importlib
import logging
from pathlib import Path
import sys
import threading

import cv2

from screen_translator.app import create_pipeline
from screen_translator.config import load_config
from screen_translator.logging_setup import setup_logging
from screen_translator.models import Region, TextBlock, TranslatedBlock
from screen_translator.utils.win_utils import enable_dpi_awareness

logger = logging.getLogger("screen_translator")

MODULES_TO_VERIFY: list[str] = [
    "screen_translator.config",
    "screen_translator.logging_setup",
    "screen_translator.models",
    "screen_translator.pipeline",
    "screen_translator.app",
    "screen_translator.capture.base",
    "screen_translator.capture.mss_capturer",
    "screen_translator.capture.frame_diff",
    "screen_translator.capture.settle",
    "screen_translator.ocr.base",
    "screen_translator.ocr.rapidocr_engine",
    "screen_translator.ocr.grouping",
    "screen_translator.ocr.upscale",
    "screen_translator.translate.base",
    "screen_translator.translate.filters",
    "screen_translator.translate.google_translator",
    "screen_translator.translate.cache",
    "screen_translator.ui.overlay_window",
    "screen_translator.ui.region_selector",
    "screen_translator.ui.tray",
    "screen_translator.ui.hotkeys",
    "screen_translator.state",
    "screen_translator.benchmark",
    "screen_translator.utils.coords",
    "screen_translator.utils.stabilization",
    "screen_translator.utils.win_utils",
]


def run_check() -> int:
    """Validate configuration and verify all modules import successfully."""
    config = load_config()
    setup_logging(level=config.logging.level)

    logger.debug("Loading and verifying skeleton modules...")
    for mod_name in MODULES_TO_VERIFY:
        importlib.import_module(mod_name)
        logger.debug("Module loaded successfully: %s", mod_name)

    logger.info("OK: skeleton loaded")
    return 0


def _parse_region(region_str: str | None) -> Region | None:
    """Parse comma-separated 'L,T,W,H' into a Region dataclass."""
    if not region_str:
        return None
    try:
        parts = [int(p.strip()) for p in region_str.split(",")]
        if len(parts) != 4:
            raise ValueError
        return Region(left=parts[0], top=parts[1], width=parts[2], height=parts[3])
    except Exception as exc:
        raise ValueError(f"Invalid --region format: '{region_str}'. Expected 'L,T,W,H'.") from exc


def run_console(args: argparse.Namespace) -> int:
    """Run console capture, OCR, and translation pipeline loop."""
    config = load_config()
    log_level = args.log_level or config.logging.level
    setup_logging(level=log_level)

    target_region = _parse_region(args.region) if args.region else (
        Region(*config.capture.region) if config.capture.region else None
    )

    debug_path = Path(args.debug_dir) if args.debug_dir else None
    if debug_path:
        debug_path.mkdir(parents=True, exist_ok=True)

    use_translation = not args.no_translate
    pipeline = create_pipeline(config, monitor=args.monitor, translate=use_translation)

    frame_counter = 0
    ocr_latencies: list[float] = []
    translate_latencies: list[float] = []

    def handle_result(blocks: list[TranslatedBlock] | list[TextBlock]) -> None:
        nonlocal frame_counter
        frame_counter += 1

        if pipeline.last_ocr_time > 0:
            ocr_latencies.append(pipeline.last_ocr_time)
        if pipeline.last_translate_time > 0:
            translate_latencies.append(pipeline.last_translate_time)

        if debug_path and pipeline.last_frame is not None:
            raw_path = debug_path / f"frame_{frame_counter:04d}_raw.png"
            cv2.imwrite(str(raw_path), pipeline.last_frame.image)

            annotated = pipeline.last_frame.image.copy()
            reg_l = pipeline.last_frame.region.left
            reg_t = pipeline.last_frame.region.top
            for item in blocks:
                bbox = item.source.bbox if isinstance(item, TranslatedBlock) else item.bbox
                pt1 = (bbox[0] - reg_l, bbox[1] - reg_t)
                pt2 = (bbox[2] - reg_l, bbox[3] - reg_t)
                cv2.rectangle(annotated, pt1, pt2, (0, 255, 0), 2)
            ann_path = debug_path / f"frame_{frame_counter:04d}_ocr.png"
            cv2.imwrite(str(ann_path), annotated)

        if not blocks:
            return

        ts_str = datetime.now().strftime("%H:%M:%S")
        for item in blocks:
            if isinstance(item, TranslatedBlock):
                print(f"[{ts_str}] {item.source.bbox}")
                print(f"  EN: {item.source.text}")
                print(f"  VI: {item.translated_text}")
            else:
                print(f"[{ts_str}] {item.bbox} conf={item.confidence:.2f} | {item.text}")
        print()
        sys.stdout.flush()

    stop_event = threading.Event()
    fps = float(config.capture.fps)

    try:
        if args.once:
            logger.info("Executing single pass (--once)...")
            res = pipeline.step(region=target_region)
            if res is not None:
                handle_result(res)
        else:
            logger.info("Starting console loop at %.1f FPS (press Ctrl+C to exit)...", fps)
            pipeline.run(stop_event=stop_event, fps=fps, on_result=handle_result, region=target_region)
    except KeyboardInterrupt:
        logger.info("Interrupted by user. Exiting cleanly...")
    finally:
        stop_event.set()
        pipeline.capturer.close()

        # Print final session performance and cache statistics
        print("\n--- Session Statistics ---")
        if pipeline.translator and hasattr(pipeline.translator, "cache"):
            hits, misses = pipeline.translator.cache.stats()
            total = hits + misses
            rate = (hits / total * 100) if total > 0 else 0.0
            print(f"Cache stats: {hits} hits, {misses} misses ({rate:.1f}% hit rate)")
        if ocr_latencies:
            avg_ocr = (sum(ocr_latencies) / len(ocr_latencies)) * 1000
            print(f"Average OCR latency: {avg_ocr:.1f} ms")
        if translate_latencies:
            avg_tr = (sum(translate_latencies) / len(translate_latencies)) * 1000
            print(f"Average Translate latency: {avg_tr:.1f} ms")

    return 0


def main() -> int:
    """Parse CLI options and dispatch actions."""
    enable_dpi_awareness()

    if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        prog="screen_translator",
        description="Screen Translator: Real-time on-screen OCR and translation overlay for Windows.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate configuration and ensure all project modules load without error.",
    )
    parser.add_argument(
        "--console",
        action="store_true",
        help="Run continuous screen capture, OCR, and translation printing to the console.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Perform a single capture and translation pass and exit.",
    )
    parser.add_argument(
        "--no-translate",
        action="store_true",
        help="Disable translation and print raw OCR text only (Stage 1 mode).",
    )
    parser.add_argument(
        "--monitor",
        type=int,
        default=None,
        help="Monitor index to capture (1-based, 1 is primary).",
    )
    parser.add_argument(
        "--region",
        type=str,
        default=None,
        help="Screen region to capture in 'left,top,width,height' pixel format.",
    )
    parser.add_argument(
        "--debug-dir",
        type=str,
        default=None,
        help="Directory to save raw and annotated frames.",
    )
    parser.add_argument(
        "--bench",
        action="store_true",
        help="Run performance benchmark measuring pipeline latencies and CPU load.",
    )
    parser.add_argument(
        "--frames",
        type=int,
        default=20,
        help="Number of frames to benchmark (default: 20).",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default=None,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Override logging verbosity level.",
    )

    args = parser.parse_args()

    if args.check:
        return run_check()

    if args.bench:
        from screen_translator.benchmark import run_bench
        return run_bench(args)

    if args.console or args.once:
        return run_console(args)

    # Default (no flags): launch transparent GUI overlay window mode
    from screen_translator.app import run_overlay
    config = load_config()
    return run_overlay(config, args)


if __name__ == "__main__":
    sys.exit(main())
