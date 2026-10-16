"""Main CLI entry point for Screen Translator."""

from __future__ import annotations

import argparse
from datetime import datetime
import importlib
import logging
import os
from pathlib import Path
import sys
import threading
import traceback

import cv2

from screen_translator import __version__
from screen_translator.app import create_pipeline
from screen_translator.config import load_config
from screen_translator.logging_setup import setup_logging
from screen_translator.models import Region, TextBlock, TranslatedBlock
from screen_translator.utils.win_utils import enable_dpi_awareness, show_fatal_error

logger = logging.getLogger("screen_translator")

MODULES_TO_VERIFY: list[str] = [
    "screen_translator.config",
    "screen_translator.logging_setup",
    "screen_translator.models",
    "screen_translator.paths",
    "screen_translator.pipeline",
    "screen_translator.app",
    "screen_translator.capture.base",
    "screen_translator.capture.mss_capturer",
    "screen_translator.capture.dxcam_capturer",
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
    "screen_translator.ui.layout",
    "screen_translator.ui.overlay_window",
    "screen_translator.ui.region_selector",
    "screen_translator.ui.tray",
    "screen_translator.ui.hotkeys",
    "screen_translator.state",
    "screen_translator.benchmark",
    "screen_translator.utils.coords",
    "screen_translator.utils.loop_watchdog",
    "screen_translator.utils.overlay_filter",
    "screen_translator.utils.stabilization",
    "screen_translator.utils.win_utils",
]


def run_check(deep: bool = False, config_path: str | Path | None = None) -> int:
    """Validate configuration, verify module imports, and optionally test OCR inference."""
    try:
        config = load_config(config_path)
        setup_logging(level=config.logging.level)

        logger.debug("Loading and verifying application modules...")
        for mod_name in MODULES_TO_VERIFY:
            importlib.import_module(mod_name)
            logger.debug("Module loaded successfully: %s", mod_name)

        if deep:
            logger.info("Running deep verification on RapidOCR neural models...")
            import numpy as np
            from screen_translator.app import create_ocr_engine

            img = np.full((160, 500, 3), 255, dtype=np.uint8)
            cv2.putText(
                img,
                "Hello World",
                (40, 105),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.8,
                (0, 0, 0),
                3,
                cv2.LINE_AA,
            )
            engine = create_ocr_engine(config)
            blocks = engine.recognize(img)
            detected = " ".join(b.text for b in blocks).lower()
            if "hello" not in detected:
                logger.critical("Deep check failed: Expected 'hello' in '%s'", detected)
                if sys.stderr is not None:
                    print(f"Deep check FAILED: Expected 'hello', got: '{detected}'", file=sys.stderr)
                return 1

            logger.info("OK: deep check passed (ONNX models and inference verified)")
            if sys.stdout is not None:
                print("OK: deep check passed")
            return 0

        logger.info("OK: skeleton loaded")
        if sys.stdout is not None:
            print("OK: skeleton loaded")
        return 0
    except Exception as exc:
        logger.critical("Self-check failed: %s", exc, exc_info=True)
        if sys.stderr is not None:
            print(f"Check FAILED: {exc}", file=sys.stderr)
        return 1


def run_check_exclusion(backend: str = "mss") -> int:
    """Run diagnostic verifying whether screen capture excludes our overlay window."""
    import time
    import numpy as np
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QPainter
    from PySide6.QtWidgets import QApplication, QWidget
    from screen_translator.capture.dxcam_capturer import DxcamCapturer
    from screen_translator.capture.mss_capturer import MssCapturer
    from screen_translator.models import Region
    from screen_translator.utils.win_utils import (
        exclude_window_from_capture,
        get_window_display_affinity,
        get_windows_build_number,
        make_click_through,
    )

    enable_dpi_awareness()
    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    screen = app.primaryScreen()
    dpr = screen.devicePixelRatio() if screen else 1.0

    class MagentaTestWindow(QWidget):
        def __init__(self) -> None:
            super().__init__(
                None,
                Qt.FramelessWindowHint
                | Qt.WindowStaysOnTopHint
                | Qt.Tool
                | Qt.WindowTransparentForInput,
            )
            self.setAttribute(Qt.WA_TranslucentBackground, True)
            self.setAttribute(Qt.WA_ShowWithoutActivating, True)
            self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            self.setGeometry(200, 200, 400, 250)

        def paintEvent(self, event) -> None:
            painter = QPainter(self)
            painter.fillRect(0, 0, 400, 250, QColor(255, 0, 255))
            painter.end()

    window = MagentaTestWindow()
    window.show()
    app.processEvents()

    hwnd = int(window.winId())
    build = get_windows_build_number()

    # Apply exclusion then click-through (matching app order)
    res_excl = exclude_window_from_capture(hwnd)
    res_click = make_click_through(hwnd)
    aff = get_window_display_affinity(hwnd)

    logger.info("Windows build: %d", build)
    logger.info("exclude_window_from_capture(HWND=%s): %s", hwnd, res_excl)
    logger.info("GetWindowDisplayAffinity(HWND=%s): %s", hwnd, f"{aff:#x}" if aff is not None else "None")

    if sys.stdout is not None:
        print(f"Windows build number: {build}")
        print(f"SetWindowDisplayAffinity applied: {res_excl}")
        print(f"GetWindowDisplayAffinity readback: {f'0x{aff:x}' if aff is not None else 'None'}")

    # Wait 700ms for desktop compositor and capture buffer to settle
    start_time = time.monotonic()
    while time.monotonic() - start_time < 0.700:
        app.processEvents()
        time.sleep(0.02)

    # Capture the exact 400x250 area in physical native pixels
    phys_x = int(round(200 * dpr))
    phys_y = int(round(200 * dpr))
    phys_w = int(round(400 * dpr))
    phys_h = int(round(250 * dpr))
    test_region = Region(left=phys_x, top=phys_y, width=phys_w, height=phys_h)

    capturer = DxcamCapturer() if backend.lower() == "dxcam" else MssCapturer()
    try:
        frame = capturer.grab(test_region)
        img = frame.image  # BGR format from OpenCV / MSS
        # Magenta: B >= 180, G <= 70, R >= 180
        magenta_mask = (img[:, :, 0] > 180) & (img[:, :, 1] < 70) & (img[:, :, 2] > 180)
        magenta_fraction = float(np.mean(magenta_mask))

        if sys.stdout is not None:
            print(f"Backend tested: {backend}")
            print(f"Near-magenta pixel fraction: {magenta_fraction:.2%}")

        if magenta_fraction < 0.01:
            logger.info("PASS: capture exclusion works with %s (fraction: %.2f%%)", backend, magenta_fraction * 100)
            if sys.stdout is not None:
                print(f"PASS: capture exclusion works with {backend}")
            return 0
        else:
            logger.error("FAIL: capture exclusion DOES NOT work with %s (fraction: %.2f%%)", backend, magenta_fraction * 100)
            if sys.stderr is not None:
                print(
                    f"FAIL: capture exclusion DOES NOT work with {backend}, overlay text will be captured (magenta fraction: {magenta_fraction:.2%})",
                    file=sys.stderr,
                )
            return 1
    finally:
        capturer.close()
        window.close()


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
    config = load_config(args.config)
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
            raw_file = debug_path / f"frame_{frame_counter:04d}_raw.png"
            cv2.imwrite(str(raw_file), pipeline.last_frame.image)

            annotated = pipeline.last_frame.image.copy()
            for b in blocks:
                box = b.source.bbox if isinstance(b, TranslatedBlock) else b.bbox
                x1, y1, x2, y2 = box
                rx, ry = pipeline.last_frame.region.left, pipeline.last_frame.region.top
                lx1, ly1, lx2, ly2 = x1 - rx, y1 - ry, x2 - rx, y2 - ry
                cv2.rectangle(annotated, (lx1, ly1), (lx2, ly2), (0, 255, 0), 2)
            ann_file = debug_path / f"frame_{frame_counter:04d}_ocr.png"
            cv2.imwrite(str(ann_file), annotated)

        now_str = datetime.now().strftime("%H:%M:%S")
        for b in blocks:
            if isinstance(b, TranslatedBlock):
                print(f"[{now_str}] ({b.source.bbox[0]}, {b.source.bbox[1]}, {b.source.bbox[2]}, {b.source.bbox[3]})")
                print(f"  EN: {b.source.text}")
                print(f"  VI: {b.translated_text}")
            else:
                print(f"[{now_str}] ({b.bbox[0]}, {b.bbox[1]}, {b.bbox[2]}, {b.bbox[3]})")
                print(f"  OCR: {b.text} (conf: {b.confidence:.2f})")

    stop_event = threading.Event()

    try:
        if args.once:
            logger.info("Executing single capture pass...")
            result = pipeline.step(region=target_region)
            if result is not None:
                handle_result(result)
            return 0

        logger.info("Starting continuous pipeline. Press Ctrl+C to terminate.")
        pipeline.run(stop_event=stop_event, fps=config.capture.fps, on_result=handle_result, region=target_region)
    except KeyboardInterrupt:
        logger.info("Stopping pipeline loop...")
    finally:
        stop_event.set()
        pipeline.capturer.close()

        print("\n--- Session Statistics ---")
        if pipeline.translator and hasattr(pipeline.translator, "cache"):
            stats = pipeline.translator.cache.stats
            hits, misses, rate = stats["hits"], stats["misses"], stats["hit_rate"] * 100
            print(f"Cache stats: {hits} hits, {misses} misses ({rate:.1f}% hit rate)")
        if ocr_latencies:
            print(f"Average OCR latency: {sum(ocr_latencies) / len(ocr_latencies) * 1000:.1f} ms")
        if translate_latencies:
            print(f"Average Translate latency: {sum(translate_latencies) / len(translate_latencies) * 1000:.1f} ms")

    return 0


def main() -> int:
    """Parse CLI options and dispatch actions with windowed safety and exception handling."""
    # Windowed safety: Ensure sys.stdout and sys.stderr are valid file-like streams
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    elif hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")
    elif hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    # Global unhandled exception hook showing native dialog box
    def _fatal_excepthook(exctype, value, tb):
        trace = "".join(traceback.format_exception(exctype, value, tb))
        logger.critical("Uncaught fatal exception:\n%s", trace)
        show_fatal_error(
            "Screen Translator - Fatal Error",
            f"An unexpected error occurred:\n\n{value}\n\nCheck logs for details.",
        )
        if sys.__excepthook__ is not None:
            sys.__excepthook__(exctype, value, tb)

    sys.excepthook = _fatal_excepthook

    enable_dpi_awareness()

    parser = argparse.ArgumentParser(
        prog="ScreenTranslator",
        description="Screen Translator: Real-time on-screen OCR and translation overlay for Windows.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"Screen Translator {__version__}",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to custom configuration YAML file.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate configuration and ensure all project modules load without error.",
    )
    parser.add_argument(
        "--deep",
        action="store_true",
        help="Perform deep verification testing bundled OCR neural models and inference.",
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
        "--check-exclusion",
        action="store_true",
        help="Run diagnostic test verifying whether capture exclusion works with the selected backend.",
    )
    parser.add_argument(
        "--backend",
        type=str,
        default="mss",
        choices=["mss", "dxcam"],
        help="Capture backend to test with --check-exclusion ('mss' or 'dxcam').",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default=None,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Override logging verbosity level.",
    )

    args = parser.parse_args()

    if args.check_exclusion:
        return run_check_exclusion(backend=args.backend)

    if args.check or args.deep:
        return run_check(deep=args.deep, config_path=args.config)

    if args.bench:
        from screen_translator.benchmark import run_bench
        return run_bench(args)

    if args.console or args.once:
        return run_console(args)

    # Default (no flags): launch transparent GUI overlay window mode
    from screen_translator.app import run_overlay
    config = load_config(args.config)
    return run_overlay(config, args)


if __name__ == "__main__":
    sys.exit(main())
