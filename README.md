# Screen Translator

A Windows 10/11 desktop application that continuously reads English text on your screen (OCR), translates it to Vietnamese in real-time, and displays the translation as a transparent, click-through, always-on-top overlay placed directly over the original text.

Designed for live reading of English slides, chats, and shared presentation screens during online meetings.

---

## Features & Scope

- **Real-Time OCR**: Low-latency on-screen English text extraction using RapidOCR.
- **Smart Change Detection**: Compares frame changes to prevent unnecessary OCR compute when screens are static.
- **Paragraph Grouping**: Groups nearby text lines into unified paragraphs before translation for grammatical context.
- **Instant Translation & Caching**: Fast translation to Vietnamese with LRU caching to eliminate repeated API queries.
- **Transparent Click-Through Overlay**: Renders directly on top of screen content while passing all mouse clicks to underlying apps.
- **Capture Exclusion**: Configured with Windows display affinity to ensure the app's own overlay is never captured by the OCR pipeline.
- **On-Screen Text Only**: Focused strictly on visual text (no audio or speech recognition).

---

## Prerequisites

- **Operating System**: Windows 10 (Build 19041+) or Windows 11
- **Python**: 3.10, 3.11, or 3.12

---

## Setup & Installation

### 1. Create and Activate Virtual Environment

**PowerShell:**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Command Prompt (cmd):**
```cmd
python -m venv .venv
.\.venv\Scripts\activate.bat
```

### 2. Install Dependencies

```powershell
pip install -r requirements.txt -r requirements-dev.txt
```

---

## Verifying the Skeleton (`--check`)

To verify configuration loading and confirm that all modules import without errors:

**PowerShell:**
```powershell
$env:PYTHONPATH="src"
python -m screen_translator --check
```

**Command Prompt (cmd):**
```cmd
set PYTHONPATH=src
python -m screen_translator --check
```

Upon success, the command will log:
```
OK: skeleton loaded
```
and exit with code `0`.

---

## Running Console Mode (Stage 2: OCR + Translation)

Run the real-time screen capture, OCR, and English-to-Vietnamese translation pipeline in the console:

**Continuous loop (~2 FPS):**
```powershell
$env:PYTHONPATH="src"
python -m screen_translator --console
```

**Single capture pass (`--once`):**
```powershell
$env:PYTHONPATH="src"
python -m screen_translator --console --once
```

**Options:**
- `--no-translate`: Run OCR only without translation (Stage 1 behavior).
- `--monitor N`: Specify monitor index (default: from `config.yaml`, 1 = primary).
- `--region L,T,W,H`: Crop capture to specific screen rectangle (e.g., `--region 100,100,800,600`).
- `--debug-dir PATH`: Save raw frames (`frame_NNNN_raw.png`) and annotated frames (`frame_NNNN_ocr.png`) with green bounding boxes.
- `--log-level LEVEL`: Set log verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`).

**Console Output Format:**
```text
[11:30:15] (120, 240, 580, 290)
  EN: Welcome to our quarterly business review meeting.
  VI: Chào mừng bạn đến với cuộc họp đánh giá kinh doanh hàng quý của chúng tôi.
```

On exit (Ctrl+C or completion), cache and latency statistics are printed:
```text
--- Session Statistics ---
Cache stats: 14 hits, 3 misses (82.4% hit rate)
Average OCR latency: 142.5 ms
Average Translate latency: 310.2 ms
```

---

## Running Tests

Run the unit tests (skipping slow integration tests by default):
```powershell
$env:PYTHONPATH="src"
pytest
```

Run integration tests (requires network access for Google Translator & RapidOCR inference):
```powershell
$env:PYTHONPATH="src"
pytest -m integration
```

---

## Project Structure

```
screen-translator/
├─ AGENTS.md                  # Architecture rules, guidelines & conventions
├─ README.md                  # Project overview, setup, usage & roadmap
├─ requirements.txt           # Production dependencies
├─ requirements-dev.txt       # Development & testing dependencies
├─ requirements-build.txt     # Packaging dependencies (PyInstaller)
├─ pytest.ini                 # Pytest configuration and markers
├─ .gitignore                 # Python, venv, and editor ignore rules
├─ config.yaml                # Application configuration
├─ run_app.py                 # PyInstaller application entry script
├─ screen_translator.spec     # PyInstaller build specification
├─ scripts/
│  ├─ make_icon.py            # Generates assets/app.ico using PySide6 QPainter
│  └─ build.ps1               # Automated build, smoke test & packaging script
├─ src/screen_translator/
│  ├─ __init__.py             # Exposes __version__
│  ├─ __main__.py             # Entry point supporting --check, --deep, --console, --bench
│  ├─ app.py                  # Component factory functions, WorkerBridge & wiring
│  ├─ benchmark.py            # Latency and CPU benchmarking suite
│  ├─ config.py               # Loads & validates config.yaml into dataclasses
│  ├─ logging_setup.py        # Windowed-safe logging configuration (rotating file)
│  ├─ models.py               # Frozen dataclasses (Region, Frame, TextBlock, TranslatedBlock)
│  ├─ paths.py                # Runtime path resolution, frozen bundle & config detection
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
│     └─ win_utils.py         # Win32 DPI awareness, capture exclusion, click-through, fatal dialog
└─ tests/
   ├─ test_config.py          # Configuration loading and schema validation
   ├─ test_paths.py           # Path resolution, frozen bundle, config precedence tests
   ├─ test_logging_setup.py   # Windowed logger safety (None stdout/stderr)
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

---

## Running the Complete App (Stage 4)

Launch the complete application with system tray, global hotkeys, drag-to-select region selector, and transparent overlay:

```powershell
$env:PYTHONPATH="src"
python -m screen_translator
```

### Global Hotkeys

| Hotkey | Action | Description |
|---|---|---|
| `Ctrl+Alt+T` | Toggle Start / Pause | Pauses background OCR/translation (CPU drops to ~0%) and hides overlay. Press again to resume. |
| `Ctrl+Alt+R` | Select Region | Dims all monitors; drag a rectangle with crosshairs to capture only that area. |
| `Ctrl+Alt+Q` | Quit Application | Safely stops background threads, removes tray icon, releases locks, and exits. |
| `Esc` / Right-click | Cancel Selection | Cancels active region selection with no changes to current settings. |

*(Shortcut key combinations can be customized in `config.yaml` under `hotkeys`)*

### System Tray & Context Menu

- **Tray Icon**: Rendered programmatically (green rounded square with letter **T** while running, gray when paused).
- **Left-Click**: Toggles between Start and Pause.
- **Tooltip**: Displays current status (`Running` / `Paused`) and active region coordinates (`W x H @ (X, Y)`).
- **Context Menu**:
  - `Pause (Ctrl+Alt+T)` / `Start (Ctrl+Alt+T)`
  - `Select region... (Ctrl+Alt+R)`
  - `Full screen`: Resets capture to full primary monitor.
  - `Quit (Ctrl+Alt+Q)`: Clean shutdown.
- **Throttled Notifications**: Pipeline errors display balloon warnings throttled to at most 1 message per 30 seconds.

### State Persistence & Single-Instance

- **Persistent Settings**: The last chosen capture region and running state are automatically saved to `%APPDATA%/ScreenTranslator/state.json`. On restart, the saved region is restored only if it still intersects a connected monitor.
- **Single Instance Guard**: Uses `QLockFile` in the system temporary directory. Launching a second instance prints `Another instance of Screen Translator is already running.` and exits immediately.
- **Active Region Border**: When a custom region is active, a subtle dashed border (`overlay.show_region_border: true`) marks the bounding box.

---

## Performance Tuning (Stage 5A)

### 1. Motion Debouncing (`capture.settle_ms` & `capture.max_wait_ms`)
During continuous mouse scrolling or slide deck transitions, running OCR on every frame wastes computing power and reads half-rendered text.
- **`capture.settle_ms`** (default: `300` ms): The pipeline waits for screen motion to stop for this duration before triggering OCR. Set to `0` to disable debouncing.
- **`capture.max_wait_ms`** (default: `1500` ms): An upper bound timeout that guarantees periodic OCR updates even during persistent animations (e.g., video or continuous tickers).
- **Reference commit**: Once a frame triggers OCR, `detector.commit(frame)` locks that image as the new baseline, preventing spurious secondary triggers immediately following motion.

### 2. Adaptive Small-Text Upscale (`ocr.upscale` & `ocr.small_text_px`)
- **`ocr.upscale`** (default: `"auto"`): When set to `"auto"`, the engine inspects the median text height in unscaled screen coordinates. If the median line height is below `ocr.small_text_px` (default: `14` px), it automatically re-runs OCR on a 2x bicubic upscaled frame and retains the result if detection count or mean confidence improves. It re-probes 1.0x every 20 frames to avoid permanent upscale overhead when viewing standard-sized text. You can also specify fixed numeric multipliers (`1.0`, `1.5`, `2.0`).
- **Screen Coordinate Remapping**: Regardless of upscale factor, all bounding boxes are automatically scaled back and offset to physical screen pixels.

### 3. Result Stabilization & Flicker Prevention
- **`blocks_equivalent(tol_px=4)`**: Text and bounding box coordinates are compared against the last emitted blocks. If detected text is identical and bounding boxes have jittered by less than 4 pixels, the pipeline suppresses re-emission, eliminating overlay flicker and redundant widget repainting on static screens.

### 4. Benchmarking Mode (`--bench`)
Run the built-in benchmark to measure component latency and CPU utilization across N frames:

```powershell
$env:PYTHONPATH="src"
python -m screen_translator --bench --frames 20
```

To benchmark without network translation:
```powershell
$env:PYTHONPATH="src"
python -m screen_translator --bench --frames 20 --no-translate
```

**Example Benchmark Output:**
```text
====================================================================
                SCREEN TRANSLATOR PERFORMANCE BENCHMARK
====================================================================
  Frames measured    : 20
  Active upscale     : 1.0x (config: auto)
  Translation        : Enabled (Google)
  Approx CPU usage   : 8.4%
--------------------------------------------------------------------
  Pipeline Stage          Mean (ms)    p95 (ms)    Min (ms)    Max (ms)
--------------------------------------------------------------------
  Capture (MSS)               12.30       15.10        9.80       16.40
  Diff (cv2.absdiff)           1.40        2.10        1.10        2.40
  OCR (RapidOCR)              85.20      102.50       78.10      110.30
  Grouping                     0.30        0.50        0.20        0.60
  Translate (Google/LRU)       0.15        0.30        0.10        0.40
--------------------------------------------------------------------
  Total Pipeline              99.35      120.50       89.30      130.10
====================================================================
```

---

## Distribution & Packaging (Stage 5B)

Screen Translator can be compiled into a standalone Windows folder bundle (`dist/ScreenTranslator`) that runs on Windows 10/11 machines **without requiring Python** or any external dependencies installed.

### 1. Building the Executable

Run the automated build script in PowerShell:

```powershell
# Standard production build + smoke test + release ZIP:
.\scripts\build.ps1 -Clean -Zip

# Debug build with an attached console window:
.\scripts\build.ps1 -Console
```

The script performs the following end-to-end steps:
1. **Checks Python environment**: Verifies Python 3.10 - 3.12.
2. **Installs dependencies**: `requirements.txt` and `requirements-build.txt` (PyInstaller).
3. **Generates App Icon**: Uses PySide6 (`scripts/make_icon.py`) to render `assets/app.ico` (256x256).
4. **Packages with PyInstaller**: Compiles `run_app.py` using `screen_translator.spec` in `--onedir` windowed mode (`console=False`, `upx=False`).
5. **Runs Automated Smoke Test**: Executes `dist\ScreenTranslator\ScreenTranslator.exe --check --deep` with `Start-Process -Wait -PassThru` and ensures zero exit code (verifies that RapidOCR ONNX models and configurations are bundled and inferring properly).
6. **Produces Release ZIP**: Creates `dist\ScreenTranslator-<version>-win64.zip` and prints bundle sizes.

### 2. Configuration, Logs, and State Storage

- **Configuration Resolution Order**:
  1. `--config <path>`: Explicit CLI parameter.
  2. **Portable Mode**: `config.yaml` placed in the same folder as `ScreenTranslator.exe`.
  3. **User Profile**: `%APPDATA%\ScreenTranslator\config.yaml`. On first launch, the bundled default configuration is copied here automatically if no configuration exists.
- **Log Files**:
  - Saved to `%APPDATA%\ScreenTranslator\logs\app.log` via `RotatingFileHandler` (1 MB max size, up to 3 backups).
  - In windowed executable mode, standard output is directed safely to `os.devnull` with crash dialog popups via Win32 `MessageBoxW`.
- **Saved State**:
  - Remembers selected screen region and active state in `%APPDATA%\ScreenTranslator\state.json`.

### 3. Windows SmartScreen & Antivirus False Positives

- **Unsigned Executable**: Because the release binary is not signed with an expensive Extended Validation (EV) certificate, Windows SmartScreen will show *"Windows protected your PC"* on first launch.
  - Click **"More info"** -> Click **"Run anyway"**.
- **Antivirus Heuristics**: Global hotkey monitoring relies on Windows low-level keyboard hooks (`pynput.keyboard._win32`), which some generic antivirus engines flag as heuristic false positives. The application is completely open-source and performs no telemetry.

### 4. Uninstallation

Screen Translator requires no registry changes or system installers. To completely uninstall:
1. Delete the application directory / unzipped `ScreenTranslator/` folder.
2. Delete the user data directory: `%APPDATA%\ScreenTranslator`.

---

## Troubleshooting

- **"Another instance of Screen Translator is already running."**: An existing process is active or the previous session did not close. Check Windows Task Manager for `ScreenTranslator.exe` or delete `%TEMP%/screen_translator.lock`.
- **Global hotkey not responding**: Ensure no other application (e.g. graphics driver utilities) has registered an exclusive system hook on `Ctrl+Alt+T` / `Ctrl+Alt+R`. Custom hotkeys can be assigned in `config.yaml`.
- **Overlay alignment on multi-monitor setups**: When dragging a region onto a secondary monitor, the overlay automatically identifies the screen with the largest overlap and aligns using native physical device pixel ratios.
- **High CPU usage when idle**: When paused via `Ctrl+Alt+T` or tray icon, the single-shot pipeline timer stops completely, reducing CPU consumption to near 0%.

---

## Manual Test Checklist

1. **Start the app**: The system tray icon appears (green 'T'). Press `Ctrl+Alt+T` -> pauses (overlay disappears, tray turns gray). Press again -> resumes.
2. **Select Region (`Ctrl+Alt+R`)**: Screen dims across all connected monitors. Drag a rectangle -> only that area is translated, and a dashed border is visible around the active region.
3. **Cancel Selection**: Press `Ctrl+Alt+R`, then press `Esc` or right-click -> dims disappear, pipeline resumes previous state with no change.
4. **State Persistence**: Restart the app -> the previously selected region and running state are restored from `%APPDATA%/ScreenTranslator/state.json`.
5. **Multi-Monitor (if available)**: Select a region on the second monitor -> the overlay automatically shifts to that monitor and aligns coordinates accurately.
6. **Clean Exit**: Press `Ctrl+Alt+Q` or choose `Quit` from the tray menu -> exits cleanly with no leftover background processes in Task Manager.
7. **Single-Instance Guard**: Launch a second instance in another terminal -> prints `"Another instance of Screen Translator is already running."` and exits immediately.
8. **Motion Settle**: Scroll a long webpage -> notice OCR does not spam during scrolling; translates shortly after motion settles.
9. **No Static Flicker**: Leave the screen static -> overlay remains crisp with 0 repainting/flickering.
10. **Standalone Windows Executable**: Build and run on a machine without Python installed -> tray icon appears, OCR and translation function seamlessly.

---

## Development Roadmap

- **Stage 0 [DONE]**: Project scaffold, interfaces, configurations, models, Windows ctypes helpers, and test suite.
- **Stage 1 [DONE]**: Screen capture (MSS) + change detection (cv2.absdiff) + OCR (RapidOCR) + line grouping to paragraphs.
- **Stage 2 [DONE]**: Deep-translator integration (GoogleTranslator) + thread-safe LRU cache + non-translatable text filtering.
- **Stage 3 [DONE]**: Transparent click-through overlay window with capture exclusion and per-monitor scaling.
- **Stage 4 [DONE]**: Global hotkeys, drag-to-select region selector, system tray icon, state persistence, single-instance guard.
- **Stage 5A [DONE]**: Adaptive upscale, motion settle gate, result stabilization, benchmark suite.
- **Stage 5B [DONE]**: Standalone Windows executable packaging with PyInstaller (--onedir, windowed, assets/app.ico, build.ps1, automated smoke test & zip distribution).


