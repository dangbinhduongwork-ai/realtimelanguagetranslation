# Screen Translator - Agent Guidelines & Architecture Rules

## Project Goal & Scope
"Screen Translator" is a Windows 10/11 desktop app that continuously reads English text on the screen (OCR),
translates it to Vietnamese, and displays the translation as a transparent, click-through,
always-on-top overlay placed over the original text.
- Use case: Reading English slides / chat / shared screens during live meetings.
- Scope: On-screen text ONLY. No audio, no speech recognition.

## Tech Stack (Fixed)
- Python 3.10 - 3.12, Windows only
- UI: PySide6 (overlay, tray icon, region selector)
- Screen capture: mss
- Image processing: numpy, opencv-python-headless (frame change detection)
- OCR: rapidocr-onnxruntime (behind an interface)
- Translation: deep-translator (GoogleTranslator) behind an interface
- Config: PyYAML
- Global hotkeys: pynput
- Tests: pytest (in requirements-dev.txt)
- Do not add any other third-party dependency.

## Architecture Rules
1. **Pipeline**:
   `capture` -> `change detection` -> `OCR` -> `group lines into paragraphs` -> `translate (with cache)` -> `overlay`.
2. **Threading**:
   UI runs on the main Qt thread. The pipeline runs in a separate `QThread` worker.
   They communicate ONLY via Qt signals/slots. Never touch widgets from the worker.
3. **Engine Interfaces**:
   Capture, OCR, and translation are each an abstract base class (`abc.ABC`) in `base.py` with one concrete implementation, selectable via config, so engines can be swapped later.
4. **Data Models**:
   Pure data lives in `models.py` as frozen dataclasses.
5. **Dependency Injection**:
   No global mutable state. Use constructor dependency injection. Wiring happens only in `app.py`.
6. **Code Quality**:
   Use `logging` (never `print`), type hints everywhere, docstrings on every public class/function, PEP8, keep each file under ~200 lines.
7. **Windows Specifics**:
   All Windows-specific code is isolated in `utils/win_utils.py`:
   - Enable per-monitor DPI awareness (must be called before `QApplication` is created).
   - `exclude_window_from_capture(hwnd)`: `SetWindowDisplayAffinity` with `WDA_EXCLUDEFROMCAPTURE` (0x11), so our own overlay is never captured by OCR (fall back to a logged warning if unsupported).
   - `make_click_through(hwnd)`: `WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW`.

## Architecture Additions (Stage 1)
- `Pipeline`: Plain Python execution class in `pipeline.py` running capture -> change detection -> OCR -> grouping (pacing loop with target FPS, thread-safe, independent of Qt). `PipelineWorker` remains stubbed for Stage 3 Qt integration.
- `ocr.max_gap_ratio` added to config (default 0.8) for vertical line clustering in `group_lines()`.
- Component factory functions added to `app.py` (`create_capturer`, `create_detector`, `create_ocr_engine`, `create_pipeline`).
- `RapidOcrEngine.warmup()` exposed for preloading ONNX models.

## Architecture Additions (Stage 2)
- `translate/filters.py`: `needs_translation()` skips short symbols, pure numbers, and Vietnamese diacritics.
- `GoogleTranslator`: Deep-translator runner with concurrent `ThreadPoolExecutor(max_workers=4)`, sentence chunking (>4500 chars), and exponential backoff retry. Raises `TranslationError`.
- `TranslationCache`: Thread-safe LRU cache with whitespace normalization, stats tracking (`hits`, `misses`), and capacity eviction.
- `CachedTranslator`: Decorator handling cache queries, batch deduplication, and caching of successful unique requests.
- `Pipeline`: Optionally receives `translator` to produce `list[TranslatedBlock]`. On `TranslationError`, resets detector, backs off 2s, and returns `None` without crashing.

## Architecture Additions (Stage 3)
- `utils/coords.py`: Pure functions `native_to_local()` and `local_to_native()` converting between native physical pixels (mss / OCR) and Qt logical pixels based on screen origin and DPR.
- `PipelineWorker(QObject)`: QThread worker driving `Pipeline.step()` with a single-shot re-arming `QTimer`, avoiding thread blocks and handling `stop()` and `set_region()` slots immediately.
- `OverlayWindow(QWidget)`: Transparent always-on-top click-through overlay targeting a single `QScreen`. Calls `win_utils.make_click_through(hwnd)` and `win_utils.exclude_window_from_capture(hwnd)` on `showEvent`. Dynamically scales font down to 9 px or extends box downward to fit translated text.
- `run_overlay(config, args)` in `app.py`: Glues QApplication, OverlayWindow, and PipelineWorker in a QThread with clean Ctrl+C signal handling.

## Architecture Additions (Stage 4)
- `state.py`: Persistent `AppState` with atomic temp-file replace in `%APPDATA%/ScreenTranslator/state.json`. Tolerant of corrupt/missing files, validates saved regions against connected monitor coordinates.
- `ui/hotkeys.py`: `GlobalHotkeys(QObject)` wrapping `pynput.keyboard.GlobalHotKeys` in a dedicated background listener thread. Parses and validates shortcut syntax at startup and emits pure Qt signals (`toggle`, `select_region`, `quit`).
- `ui/region_selector.py`: Multi-monitor interactive region selection using frameless, dimmed (alpha ~0.3) crosshair overlay windows. Renders live dimension badge, enforces minimum 50x30 px cutoff, and converts selections to physical native screen coordinates via `local_to_native()`.
- `ui/tray.py`: `TrayIcon(QSystemTrayIcon)` rendering dynamic `QPainter` rounded-square icons (green=running, gray=paused), left-click toggle, context menu with hotkey hints, and 30s throttled balloon notifications.
- `app.py`: Central orchestration wiring `WorkerBridge` queued signal dispatch, `QLockFile` single-instance check, automatic monitor overlap selection via `find_screen_with_largest_overlap()`, and clean termination.
- `ui/overlay_window.py`: Optional dashed border rendered around active region when `overlay.show_region_border` is enabled.

## Architecture Additions (Stage 5A)
- `capture/settle.py`: `SettleGate` debouncing continuous motion (scrolling, slide transitions) with `settle_ms` stillness threshold and `max_wait_ms` force-refresh timeout.
- `capture/frame_diff.py`: Added `rolling=True` mode for previous-tick motion comparison and `commit(image)` to sync baseline upon OCR triggering.
- `ocr/upscale.py`: Helper functions (`calculate_median_line_height`, `calculate_mean_confidence`, `scale_image`, `remap_blocks_to_screen`) for adaptive image upscaling.
- `ocr/rapidocr_engine.py`: Adaptive 2x upscale on small text (median line height < `small_text_px`) with re-probing every 20 frames and coordinate remapping.
- `utils/stabilization.py`: Pure function `blocks_equivalent(prev, new, tol_px=4)` preventing redundant repaints and overlay flicker on static/jittery text.
- `benchmark.py`: Command `--bench [--frames N]` measuring average and p95 latencies for capture, diff, OCR, grouping, translation, and CPU load.

## Complete Project Structure
```
screen-translator/
├─ AGENTS.md                  # Architecture rules, guidelines & conventions
├─ README.md                  # Project overview, setup, usage & roadmap
├─ requirements.txt           # Production dependencies
├─ requirements-dev.txt       # Development & testing dependencies
├─ pytest.ini                 # Pytest configuration and markers
├─ .gitignore                 # Git ignore rules
├─ config.yaml                # Application configuration
├─ src/screen_translator/
│  ├─ __init__.py
│  ├─ __main__.py             # Entry point supporting --check, --console, and --bench
│  ├─ app.py                  # Component factory functions, WorkerBridge & wiring
│  ├─ benchmark.py            # Latency and CPU benchmarking suite
│  ├─ config.py               # Loads & validates config.yaml into dataclasses
│  ├─ logging_setup.py        # Centralized logging configuration
│  ├─ models.py               # Frozen dataclasses (Region, Frame, TextBlock, TranslatedBlock)
│  ├─ pipeline.py             # Pipeline loop + PipelineWorker (QObject in QThread)
│  ├─ state.py                # AppState persistence to %APPDATA%/ScreenTranslator/state.json
│  ├─ capture/
│  │  ├─ __init__.py
│  │  ├─ base.py              # ScreenCapturer (ABC)
│  │  ├─ mss_capturer.py      # MssCapturer implementation (lazy thread-local)
│  │  ├─ frame_diff.py        # ChangeDetector (downscaled cv2.absdiff, rolling mode, commit)
│  │  └─ settle.py            # SettleGate (motion debouncing & max_wait timeout)
│  ├─ ocr/
│  │  ├─ __init__.py
│  │  ├─ base.py              # OcrEngine (ABC)
│  │  ├─ rapidocr_engine.py   # RapidOcrEngine implementation with adaptive upscale
│  │  ├─ grouping.py          # group_lines() paragraph clustering
│  │  └─ upscale.py           # Adaptive upscale calculations & coordinate remapping
│  ├─ translate/
│  │  ├─ __init__.py          # build_translator factory
│  │  ├─ base.py              # Translator (ABC) & TranslationError
│  │  ├─ filters.py           # needs_translation() text filtering
│  │  ├─ google_translator.py # GoogleTranslator with ThreadPoolExecutor & retries
│  │  └─ cache.py             # TranslationCache (LRU) + CachedTranslator decorator
│  ├─ ui/
│  │  ├─ __init__.py
│  │  ├─ overlay_window.py    # Transparent click-through overlay with dashed border
│  │  ├─ region_selector.py   # Multi-screen interactive drag-to-select region overlay
│  │  ├─ tray.py              # System tray icon (dynamic QPainter, menu, notifications)
│  │  └─ hotkeys.py           # GlobalHotkeys listener (pynput in background thread)
│  └─ utils/
│     ├─ __init__.py
│     ├─ coords.py            # Coordinate transformations & monitor overlap resolution
│     ├─ stabilization.py     # blocks_equivalent() visual jitter stabilizer
│     └─ win_utils.py         # Win32 DPI awareness, capture exclusion, click-through
└─ tests/
   ├─ test_config.py          # Configuration loading and schema validation
   ├─ test_imports.py         # Module imports, model invariants, factories
   ├─ test_coords.py          # Coordinate transformation and DPR scaling tests
   ├─ test_frame_diff.py      # Unit tests for ChangeDetector (standard, rolling, commit)
   ├─ test_settle_gate.py     # Unit tests for SettleGate with fake clock
   ├─ test_blocks_equivalent.py # Unit tests for blocks_equivalent stabilization
   ├─ test_upscale.py         # Unit tests for adaptive upscale helpers
   ├─ test_grouping.py        # Unit tests for group_lines() clustering
   ├─ test_filters.py         # Unit tests for translation filters
   ├─ test_cache.py           # Unit tests for LRU TranslationCache
   ├─ test_cached_translator.py # Unit tests for CachedTranslator deduplication & caching
   ├─ test_state.py           # Unit tests for AppState persistence & validation
   ├─ test_hotkeys_parse.py   # Unit tests for hotkey syntax validation
   ├─ test_ocr_integration.py # Integration test for RapidOCR (standard & small text)
   └─ test_google_integration.py # Integration test for live GoogleTranslator API
```

## Staging Roadmap
- **Stage 0 [DONE]**: Scaffold project (folders, files, interfaces, config, tests, skeleton verification).
- **Stage 1 [DONE]**: Capture (MSS) + change detection (cv2.absdiff) + OCR (RapidOCR) + grouping -> console output.
- **Stage 2 [DONE]**: Translation (GoogleTranslator) + thread-safe LRU cache + filters.
- **Stage 3 [DONE]**: Overlay window (click-through, transparent, excluded from capture).
- **Stage 4 [DONE]**: Hotkeys, region selector, tray icon, state persistence, single-instance guard.
- **Stage 5A [DONE]**: Adaptive upscale, motion settle gate, result stabilization, benchmark suite.


