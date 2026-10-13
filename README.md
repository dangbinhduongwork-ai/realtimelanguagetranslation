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
├─ pytest.ini                 # Pytest configuration and markers
├─ .gitignore                 # Python, venv, and editor ignore rules
├─ config.yaml                # Application configuration
├─ src/screen_translator/
│  ├─ __init__.py
│  ├─ __main__.py             # Entry point supporting --check and --console
│  ├─ app.py                  # Component factory functions & wiring
│  ├─ config.py               # Loads & validates config.yaml into dataclasses
│  ├─ logging_setup.py        # Centralized logging configuration
│  ├─ models.py               # Frozen dataclasses (Region, Frame, TextBlock, TranslatedBlock)
│  ├─ pipeline.py             # Pipeline (capture-diff-OCR-translate loop) + PipelineWorker stub
│  ├─ capture/
│  │  ├─ __init__.py
│  │  ├─ base.py              # ScreenCapturer (ABC)
│  │  ├─ mss_capturer.py      # MssCapturer implementation (lazy thread-local)
│  │  └─ frame_diff.py        # ChangeDetector (downscaled cv2.absdiff)
│  ├─ ocr/
│  │  ├─ __init__.py
│  │  ├─ base.py              # OcrEngine (ABC)
│  │  ├─ rapidocr_engine.py   # RapidOcrEngine implementation (lazy ONNX loading)
│  │  └─ grouping.py          # group_lines() paragraph clustering
│  ├─ translate/
│  │  ├─ __init__.py          # build_translator factory
│  │  ├─ base.py              # Translator (ABC) & TranslationError
│  │  ├─ filters.py           # needs_translation() text filtering
│  │  ├─ google_translator.py # GoogleTranslator with ThreadPoolExecutor & retries
│  │  └─ cache.py             # TranslationCache (LRU) + CachedTranslator decorator
│  ├─ ui/
│  │  ├─ __init__.py
│  │  ├─ overlay_window.py    # Transparent click-through overlay (Stage 3)
│  │  ├─ region_selector.py   # Interactive screen region selector (Stage 4)
│  │  ├─ tray.py              # System tray icon and menu (Stage 4)
│  │  └─ hotkeys.py           # Global hotkeys listener (Stage 4)
│  └─ utils/
│     ├─ __init__.py
│     ├─ coords.py            # Physical native <-> Qt logical coordinate conversions
│     └─ win_utils.py         # Win32 DPI awareness, capture exclusion, click-through
└─ tests/
   ├─ test_config.py          # Configuration loading and schema validation
   ├─ test_imports.py         # Module imports, model invariants, factories
   ├─ test_coords.py          # Coordinate transformation and DPR scaling tests
   ├─ test_frame_diff.py      # Unit tests for ChangeDetector
   ├─ test_grouping.py        # Unit tests for group_lines() clustering
   ├─ test_filters.py         # Unit tests for translation filters
   ├─ test_cache.py           # Unit tests for LRU TranslationCache
   ├─ test_cached_translator.py # Unit tests for CachedTranslator deduplication & caching
   ├─ test_ocr_integration.py # Integration test for RapidOCR on synthetic image
   └─ test_google_integration.py # Integration test for live GoogleTranslator API
```

---

## Running the App

### 1. Transparent Overlay Mode (Default, Stage 3)
Run with no arguments to launch the transparent, click-through overlay window on your primary monitor:

```powershell
$env:PYTHONPATH="src"
python -m screen_translator
```
*(Press `Ctrl+C` in the terminal to cleanly exit).*

### 2. Console Mode (Stage 1 & 2)
```powershell
$env:PYTHONPATH="src"
python -m screen_translator --console
```

### Options:
- `--monitor N`: Target specific monitor index (1 = primary).
- `--region L,T,W,H`: Crop to rectangular pixel bounding box.
- `--no-translate`: Run OCR only without translation.
- `--log-level LEVEL`: Set log verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`).

---

## Manual Test Checklist (Stage 3 Overlay)

1. **Visual Translation**: Open a web page or PDF with English text and run `python -m screen_translator`: Vietnamese appears directly over the text within ~2 s.
2. **Click-Through**: Click a hyperlink or button underneath the overlay: clicks pass through directly to underlying apps.
3. **Capture Exclusion**: Take a screenshot with the Windows Snipping Tool: the overlay is NOT captured in the screenshot (`WDA_EXCLUDEFROMCAPTURE`).
4. **Feedback Loop Prevention**: Leave the screen static for 10 s with `--log-level DEBUG`: logs repeatedly report `"no change"` (verifies OCR does not capture our own overlay).
5. **DPI Scaling**: Test at Windows display scaling 100%, 125%, and 150%: box positions and font scaling maintain correct alignment.
6. **Dynamic Refresh**: Scroll the page or change screens: the overlay updates cleanly with no stale or duplicated bounding boxes.

---

## Development Roadmap

- **Stage 0 [DONE]**: Project scaffold, interfaces, configurations, models, Windows ctypes helpers, and test suite.
- **Stage 1 [DONE]**: Screen capture (MSS) + change detection (cv2.absdiff) + OCR (RapidOCR) + line grouping to paragraphs.
- **Stage 2 [DONE]**: Deep-translator integration (GoogleTranslator) + thread-safe LRU cache + non-translatable text filtering.
- **Stage 3 [DONE]**: Transparent click-through overlay window with capture exclusion and per-monitor scaling.
- **Stage 4**: Hotkeys, region selector, tray icon, performance tuning.
