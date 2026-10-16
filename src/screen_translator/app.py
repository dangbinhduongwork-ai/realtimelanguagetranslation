"""Application component factories, wiring, and GUI overlay execution."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
import signal
import sys
import tempfile

from PySide6.QtCore import QLockFile, QObject, QThread, QTimer, Qt, Signal
from PySide6.QtWidgets import QApplication

from screen_translator.capture.base import ScreenCapturer
from screen_translator.capture.dxcam_capturer import DxcamCapturer
from screen_translator.capture.frame_diff import ChangeDetector
from screen_translator.capture.mss_capturer import MssCapturer
from screen_translator.config import AppConfig
from screen_translator.logging_setup import setup_logging
from screen_translator.models import Region
from screen_translator.ocr.base import OcrEngine
from screen_translator.ocr.rapidocr_engine import RapidOcrEngine
from screen_translator.pipeline import Pipeline, PipelineWorker
from screen_translator.state import AppState, is_region_within_monitors, load_state, save_state
from screen_translator.translate import build_translator
from screen_translator.translate.base import Translator
from screen_translator.ui.hotkeys import GlobalHotkeys
from screen_translator.ui.overlay_window import OverlayWindow
from screen_translator.ui.region_selector import RegionSelector
from screen_translator.ui.tray import TrayIcon
from screen_translator.utils.coords import find_screen_with_largest_overlap
from screen_translator.utils.loop_watchdog import LoopWatchdog
from screen_translator.utils.win_utils import enable_dpi_awareness

logger = logging.getLogger(__name__)


class WorkerBridge(QObject):
    """Bridge for safely dispatching control signals from main thread to PipelineWorker."""

    start_worker = Signal()
    stop_worker = Signal()
    set_region = Signal(object)


def create_capturer(config: AppConfig, monitor: int | None = None) -> ScreenCapturer:
    """Create configured ScreenCapturer engine instance."""
    mon_idx = monitor if monitor is not None else config.capture.monitor
    if config.capture.backend == "dxcam":
        logger.debug("Creating DxcamCapturer for monitor %d", mon_idx)
        return DxcamCapturer(monitor_index=mon_idx)
    logger.debug("Creating MssCapturer for monitor %d", mon_idx)
    return MssCapturer(monitor_index=mon_idx)


def create_detector(config: AppConfig) -> ChangeDetector:
    """Create configured ChangeDetector engine instance."""
    logger.debug("Creating ChangeDetector with threshold %.4f", config.change_detection.threshold)
    return ChangeDetector(threshold=config.change_detection.threshold)


def create_ocr_engine(config: AppConfig) -> OcrEngine:
    """Create configured OcrEngine instance."""
    if config.ocr.engine == "rapidocr":
        logger.debug(
            "Creating RapidOcrEngine (min_confidence=%.2f, upscale=%s, small_text_px=%d)",
            config.ocr.min_confidence,
            config.ocr.upscale,
            config.ocr.small_text_px,
        )
        return RapidOcrEngine(
            min_confidence=config.ocr.min_confidence,
            upscale=config.ocr.upscale,
            small_text_px=config.ocr.small_text_px,
        )
    raise ValueError(f"Unknown OCR engine: {config.ocr.engine}")


def create_translator(config: AppConfig) -> Translator:
    """Create configured Translator instance with LRU cache."""
    logger.debug("Creating Translator for provider '%s'", config.translate.provider)
    return build_translator(config.translate)


def create_pipeline(
    config: AppConfig,
    monitor: int | None = None,
    translate: bool = True,
    watchdog: LoopWatchdog | None = None,
) -> Pipeline:
    """Create complete Pipeline instance from application configuration."""
    capturer = create_capturer(config, monitor=monitor)
    detector = create_detector(config)
    ocr_engine = create_ocr_engine(config)
    translator = create_translator(config) if translate else None

    return Pipeline(
        capturer=capturer,
        detector=detector,
        ocr_engine=ocr_engine,
        merge_lines=config.ocr.merge_lines,
        max_gap_ratio=config.ocr.max_gap_ratio,
        translator=translator,
        settle_ms=config.capture.settle_ms,
        max_wait_ms=config.capture.max_wait_ms,
        watchdog=watchdog,
        self_filter_ratio=config.overlay.self_filter_ratio,
    )


def run_overlay(config: AppConfig, args: argparse.Namespace) -> int:
    """Launch full Stage 4 transparent click-through overlay GUI application."""
    enable_dpi_awareness()

    lock_path = Path(tempfile.gettempdir()) / "screen_translator.lock"
    lock_file = QLockFile(str(lock_path))
    if not lock_file.tryLock(100):
        print("Another instance of Screen Translator is already running.")
        logger.warning("Another instance of Screen Translator is already running.")
        return 0

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    log_level = getattr(args, "log_level", None) or config.logging.level
    setup_logging(level=log_level)

    # 1. State resolution and connected monitors inspection
    screens = app.screens()
    saved_state = load_state()
    is_running = saved_state.is_running
    target_region: Region | None = None

    if getattr(args, "region", None):
        parts = [int(p.strip()) for p in args.region.split(",")]
        target_region = Region(*parts)
    elif saved_state.region is not None:
        mon_geoms = [
            (
                int(round(s.geometry().x() * s.devicePixelRatio())),
                int(round(s.geometry().y() * s.devicePixelRatio())),
                int(round(s.geometry().width() * s.devicePixelRatio())),
                int(round(s.geometry().height() * s.devicePixelRatio())),
            )
            for s in screens
        ]
        if is_region_within_monitors(saved_state.region, mon_geoms):
            target_region = Region(*saved_state.region)
        elif config.capture.region:
            target_region = Region(*config.capture.region)
    elif config.capture.region:
        target_region = Region(*config.capture.region)

    # 2. Target screen resolution
    if target_region is not None:
        target_screen = find_screen_with_largest_overlap(screens, target_region) or app.primaryScreen()
    else:
        mon_idx = getattr(args, "monitor", None) or config.capture.monitor
        target_screen = screens[mon_idx - 1] if (1 <= mon_idx <= len(screens)) else app.primaryScreen()

    # 3. Hotkeys & Tray Icon setup
    hk_cfg = config.hotkeys
    toggle_hint = hk_cfg.toggle.replace("<", "").replace(">", "").upper()
    select_hint = hk_cfg.select_region.replace("<", "").replace(">", "").upper()
    quit_hint = hk_cfg.quit.replace("<", "").replace(">", "").upper()

    hotkeys = GlobalHotkeys(
        toggle_key=hk_cfg.toggle,
        select_region_key=hk_cfg.select_region,
        quit_key=hk_cfg.quit,
    )
    tray = TrayIcon(
        toggle_key_hint=toggle_hint,
        select_key_hint=select_hint,
        quit_key_hint=quit_hint,
    )
    region_selector = RegionSelector()

    # 4. Pipeline & Worker assembly
    watchdog = LoopWatchdog(
        on_warning=lambda msg: tray.notify("Screen Translator", msg)
    )
    use_translation = not getattr(args, "no_translate", False)
    pipeline = create_pipeline(
        config,
        monitor=getattr(args, "monitor", None),
        translate=use_translation,
        watchdog=watchdog,
    )

    thread = QThread()
    worker = PipelineWorker(pipeline=pipeline, fps=config.capture.fps, region=target_region)
    worker.moveToThread(thread)

    bridge = WorkerBridge()
    bridge.start_worker.connect(worker.start, Qt.QueuedConnection)
    bridge.stop_worker.connect(worker.stop, Qt.QueuedConnection)
    bridge.set_region.connect(worker.set_region, Qt.QueuedConnection)

    # 5. Overlay Window setup
    overlay = OverlayWindow(
        font_family=config.overlay.font_family,
        font_size=config.overlay.font_size,
        opacity=config.overlay.opacity,
        background_color=config.overlay.background_color,
        text_color=config.overlay.text_color,
        show_region_border=config.overlay.show_region_border,
        tray_notifier=tray.notify,
    )
    overlay.set_target_screen(target_screen)
    if target_region is not None:
        overlay.set_active_region(target_region)

    worker.blocks_ready.connect(overlay.update_blocks, Qt.QueuedConnection)

    # 6. Interaction Handlers
    current_region: Region | None = target_region
    was_running_before_select = is_running

    def handle_toggle() -> None:
        nonlocal is_running
        if is_running:
            is_running = False
            bridge.stop_worker.emit()
            overlay.clear()
            overlay.hide()
            tray.update_state(is_running=False, region=current_region)
        else:
            is_running = True
            overlay.show()
            bridge.start_worker.emit()
            tray.update_state(is_running=True, region=current_region)
        reg_tuple = (
            (current_region.left, current_region.top, current_region.width, current_region.height)
            if current_region else None
        )
        save_state(AppState(region=reg_tuple, is_running=is_running))

    def handle_start_select() -> None:
        nonlocal was_running_before_select, is_running
        was_running_before_select = is_running
        if is_running:
            is_running = False
            bridge.stop_worker.emit()
        overlay.clear()
        overlay.hide()
        region_selector.start_selection()

    def handle_region_selected(new_region: Region) -> None:
        nonlocal current_region, is_running
        current_region = new_region
        best_screen = find_screen_with_largest_overlap(app.screens(), new_region) or app.primaryScreen()
        overlay.set_target_screen(best_screen)
        overlay.set_active_region(new_region)
        bridge.set_region.emit(new_region)

        is_running = True
        overlay.show()
        bridge.start_worker.emit()
        tray.update_state(is_running=True, region=current_region)
        save_state(
            AppState(
                region=(new_region.left, new_region.top, new_region.width, new_region.height),
                is_running=True,
            )
        )

    def handle_select_cancelled() -> None:
        nonlocal is_running
        if was_running_before_select:
            is_running = True
            overlay.show()
            bridge.start_worker.emit()
            tray.update_state(is_running=True, region=current_region)
        else:
            is_running = False
            tray.update_state(is_running=False, region=current_region)

    def handle_full_screen() -> None:
        nonlocal current_region
        current_region = None
        primary = app.primaryScreen()
        overlay.set_target_screen(primary)
        overlay.set_active_region(None)
        bridge.set_region.emit(None)
        tray.update_state(is_running=is_running, region=None)
        save_state(AppState(region=None, is_running=is_running))

    hotkeys.toggle.connect(handle_toggle)
    hotkeys.select_region.connect(handle_start_select)
    hotkeys.quit.connect(app.quit)

    tray.toggle_requested.connect(handle_toggle)
    tray.select_region_requested.connect(handle_start_select)
    tray.full_screen_requested.connect(handle_full_screen)
    tray.quit_requested.connect(app.quit)

    region_selector.region_selected.connect(handle_region_selected)
    region_selector.cancelled.connect(handle_select_cancelled)

    worker.error.connect(lambda msg: tray.notify("Pipeline Error", msg))

    # 7. Clean shutdown wiring
    def cleanup() -> None:
        logger.info("Cleaning up and terminating Screen Translator...")
        hotkeys.stop()
        bridge.stop_worker.emit()
        worker.stop()
        thread.quit()
        thread.wait(2000)
        tray.hide()
        pipeline.capturer.close()
        if lock_file.isLocked():
            lock_file.unlock()

    app.aboutToQuit.connect(cleanup)

    # 8. Start runtime services
    if is_running:
        overlay.show()
        thread.started.connect(worker.start)
    else:
        overlay.hide()

    tray.update_state(is_running=is_running, region=current_region)
    tray.show()
    hotkeys.start()
    thread.start()

    # 9. Terminal SIGINT handling
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    sig_timer = QTimer()
    sig_timer.timeout.connect(lambda: None)
    sig_timer.start(200)

    logger.info("Screen Translator running. System tray and hotkeys active.")
    return app.exec()


class ScreenTranslatorApp:
    """Coordinates lifecycle, worker threads, UI widgets, and dependency injection."""

    def __init__(self, config: AppConfig, args: argparse.Namespace | None = None) -> None:
        self.config = config
        self.args = args or argparse.Namespace(monitor=None, region=None, log_level=None, no_translate=False)

    def run(self) -> int:
        return run_overlay(self.config, self.args)
