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

## Running Tests

Run the test suite using `pytest`:

**PowerShell:**
```powershell
$env:PYTHONPATH="src"
pytest
```

**Command Prompt (cmd):**
```cmd
set PYTHONPATH=src
pytest
```

---

## Project Structure

```
screen-translator/
├─ AGENTS.md                  # Architecture rules and coding conventions
├─ README.md                  # Project overview and development guide
├─ requirements.txt           # Production dependencies
├─ requirements-dev.txt       # Development & testing dependencies
├─ .gitignore                 # Python, venv, and editor ignore rules
├─ config.yaml                # Application configuration
├─ src/screen_translator/
│  ├─ __init__.py
│  ├─ __main__.py             # Entry point; supports `--check`
│  ├─ app.py                  # Builds components and wires dependencies
│  ├─ config.py               # Loads & validates config.yaml into dataclasses
│  ├─ logging_setup.py        # Centralized logging configuration
│  ├─ models.py               # Frozen dataclasses (Region, Frame, TextBlock, TranslatedBlock)
│  ├─ pipeline.py             # PipelineWorker(QObject) running the capture-OCR-translate loop
│  ├─ capture/
│  │  ├─ __init__.py
│  │  ├─ base.py              # ScreenCapturer (ABC)
│  │  ├─ mss_capturer.py      # MSS implementation
│  │  └─ frame_diff.py        # ChangeDetector for frame diffing
│  ├─ ocr/
│  │  ├─ __init__.py
│  │  ├─ base.py              # OcrEngine (ABC)
│  │  ├─ rapidocr_engine.py   # RapidOCR ONNX Runtime implementation
│  │  └─ grouping.py          # Line to paragraph grouping
│  ├─ translate/
│  │  ├─ __init__.py
│  │  ├─ base.py              # Translator (ABC)
│  │  ├─ google_translator.py # Google Translator implementation
│  │  └─ cache.py             # TranslationCache + CachedTranslator decorator
│  ├─ ui/
│  │  ├─ __init__.py
│  │  ├─ overlay_window.py    # Transparent click-through overlay QWidget
│  │  ├─ region_selector.py   # Interactive screen region selector
│  │  ├─ tray.py              # System tray icon and menu
│  │  └─ hotkeys.py           # Global hotkeys listener (pynput)
│  └─ utils/
│     ├─ __init__.py
│     └─ win_utils.py         # Win32 DPI awareness, capture exclusion, click-through
└─ tests/
   ├─ test_config.py          # Tests for configuration loading and validation
   ├─ test_imports.py         # Tests for module imports and model integrity
   ├─ test_frame_diff.py      # Placeholder (Stage 1)
   ├─ test_grouping.py        # Placeholder (Stage 1)
   └─ test_cache.py           # Placeholder (Stage 2)
```

---

## Development Roadmap

- **Stage 0 (Current)**: Project scaffold, interfaces, configurations, models, Windows ctypes helpers, and test suite.
- **Stage 1**: Screen capture (MSS) + change detection + OCR (RapidOCR) with console output.
- **Stage 2**: Deep-translator integration + translation caching layer.
- **Stage 3**: Transparent click-through overlay window with capture exclusion.
- **Stage 4**: Global hotkeys, interactive region selector, system tray icon, and performance tuning.
