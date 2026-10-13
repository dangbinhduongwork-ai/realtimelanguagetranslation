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

## Staging Roadmap
- **Stage 0 [DONE]**: Scaffold project (folders, files, interfaces, config, tests, skeleton verification).
- **Stage 1 [DONE]**: Capture (MSS) + change detection (cv2.absdiff) + OCR (RapidOCR) + grouping -> console output.
- **Stage 2 [DONE]**: Translation (GoogleTranslator) + thread-safe LRU cache + filters.
- **Stage 3 [DONE]**: Overlay window (click-through, transparent, excluded from capture).
- **Stage 4**: Hotkeys, region selector, tray icon, performance tuning.
