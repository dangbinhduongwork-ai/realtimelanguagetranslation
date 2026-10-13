"""Application launcher and entry point script for PyInstaller packaging."""

from __future__ import annotations

import multiprocessing
from pathlib import Path
import sys

# Ensure src/ is on sys.path when running unbundled
src_dir = Path(__file__).resolve().parent / "src"
if src_dir.is_dir() and str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from screen_translator.__main__ import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(main())
