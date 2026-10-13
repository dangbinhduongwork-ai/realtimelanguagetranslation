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
│     └─ win_utils.py         # Win32 DPI awareness, capture exclusion, click-through
└─ tests/
   ├─ test_config.py          # Configuration loading and schema validation
   ├─ test_imports.py         # Module imports, model invariants, factories
   ├─ test_frame_diff.py      # Unit tests for ChangeDetector
   ├─ test_grouping.py        # Unit tests for group_lines() clustering
   ├─ test_filters.py         # Unit tests for translation filters
   ├─ test_cache.py           # Unit tests for LRU TranslationCache
   ├─ test_cached_translator.py # Unit tests for CachedTranslator deduplication & caching
   ├─ test_ocr_integration.py # Integration test for RapidOCR on synthetic image
   └─ test_google_integration.py # Integration test for live GoogleTranslator API
```

---

## Development Roadmap

- **Stage 0 [DONE]**: Project scaffold, interfaces, configurations, models, Windows ctypes helpers, and test suite.
- **Stage 1 [DONE]**: Screen capture (MSS) + change detection (cv2.absdiff) + OCR (RapidOCR) + line grouping to paragraphs.
- **Stage 2 [DONE]**: Deep-translator integration (GoogleTranslator) + thread-safe LRU cache + non-translatable text filtering.
- **Stage 3**: Transparent click-through overlay window with capture exclusion.
- **Stage 4**: Global hotkeys, interactive region selector, system tray icon, and performance tuning.
