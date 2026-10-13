"""Application launcher and entry point script for PyInstaller packaging."""

from __future__ import annotations

import multiprocessing
import sys

from screen_translator.__main__ import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(main())
