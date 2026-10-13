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

## Staging Roadmap
- **Stage 0**: Scaffold project (folders, files, interfaces, config, tests, skeleton verification).
- **Stage 1**: Capture + change detection + OCR (console output).
- **Stage 2**: Translation + cache.
- **Stage 3**: Overlay window (click-through, transparent, excluded from capture).
- **Stage 4**: Hotkeys, region selector, tray icon, performance tuning.
