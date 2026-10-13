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
from screen_translator.models import Region, TextBlock
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
    "screen_translator.ocr.base",
    "screen_translator.ocr.rapidocr_engine",
    "screen_translator.ocr.grouping",
    "screen_translator.translate.base",
    "screen_translator.translate.google_translator",
    "screen_translator.translate.cache",
    "screen_translator.ui.overlay_window",
    "screen_translator.ui.region_selector",
    "screen_translator.ui.tray",
    "screen_translator.ui.hotkeys",
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
        raise ValueError(f"Invalid --region format: '{region_str}'. Expected 'L,T,W,H' with positive W,H.") from exc


def run_console(args: argparse.Namespace) -> int:
    """Run console capture and OCR pipeline loop."""
    config = load_config()
    log_level = args.log_level or config.logging.level
    setup_logging(level=log_level)

    target_region = _parse_region(args.region) if args.region else (
        Region(*config.capture.region) if config.capture.region else None
    )

    debug_path = Path(args.debug_dir) if args.debug_dir else None
    if debug_path:
        debug_path.mkdir(parents=True, exist_ok=True)

    pipeline = create_pipeline(config, monitor=args.monitor)
    frame_counter = 0

    def handle_result(blocks: list[TextBlock]) -> None:
        nonlocal frame_counter
        frame_counter += 1

        if debug_path and pipeline.last_frame is not None:
            raw_path = debug_path / f"frame_{frame_counter:04d}_raw.png"
            cv2.imwrite(str(raw_path), pipeline.last_frame.image)

            annotated = pipeline.last_frame.image.copy()
            reg_left = pipeline.last_frame.region.left
            reg_top = pipeline.last_frame.region.top
            for b in blocks:
                pt1 = (b.bbox[0] - reg_left, b.bbox[1] - reg_top)
                pt2 = (b.bbox[2] - reg_left, b.bbox[3] - reg_top)
                cv2.rectangle(annotated, pt1, pt2, (0, 255, 0), 2)
            ann_path = debug_path / f"frame_{frame_counter:04d}_ocr.png"
            cv2.imwrite(str(ann_path), annotated)

        if not blocks:
            return

        ts_str = datetime.now().strftime("%H:%M:%S")
        for b in blocks:
            print(f"[{ts_str}] {b.bbox} conf={b.confidence:.2f} | {b.text}")
        print()
        sys.stdout.flush()

    if args.once:
        logger.info("Executing single capture pass (--once)...")
        res = pipeline.step(region=target_region)
        if res is not None:
            handle_result(res)
        pipeline.capturer.close()
        return 0

    stop_event = threading.Event()
    fps = float(config.capture.fps)
    logger.info("Starting console OCR loop at %.1f FPS (press Ctrl+C to exit)...", fps)

    try:
        pipeline.run(stop_event=stop_event, fps=fps, on_result=handle_result, region=target_region)
    except KeyboardInterrupt:
        logger.info("Interrupted by user. Exiting cleanly...")
    finally:
        stop_event.set()
        pipeline.capturer.close()

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
        help="Run continuous screen capture, change detection, and OCR printing to the console.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Perform a single capture and OCR pass and exit.",
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
        help="Directory to save raw and annotated frames with OCR bounding boxes.",
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

    if args.console or args.once:
        return run_console(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
