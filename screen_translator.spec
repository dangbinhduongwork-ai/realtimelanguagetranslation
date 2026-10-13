# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build specification for Screen Translator."""

from __future__ import annotations

import os
from pathlib import Path
import sys

# Ensure src/ is accessible during analysis
sys.path.insert(0, os.path.abspath("src"))

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

block_cipher = None

# 1. Collect RapidOCR ONNX models and configurations
rapidocr_datas = collect_data_files("rapidocr_onnxruntime")

# 2. Collect ONNX Runtime native dynamic link libraries
onnxruntime_binaries = collect_dynamic_libs("onnxruntime")

# 3. Application data: bundle default config.yaml
datas = [
    ("config.yaml", "."),
] + rapidocr_datas

binaries = onnxruntime_binaries

# 4. Hidden imports required for Windows background hooks
hiddenimports = [
    "pynput.keyboard._win32",
    "pynput.mouse._win32",
]

# 5. Exclude heavy unused GUI, web, 3D, and scientific packages to minimize bundle size
excludes = [
    "tkinter",
    "matplotlib",
    "scipy",
    "pandas",
    "IPython",
    "PySide6.QtWebEngine",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DRender",
    "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic",
    "PySide6.Qt3DAnimation",
    "PySide6.Qt3DExtras",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuickWidgets",
    "PySide6.QtQuick3D",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtSql",
    "PySide6.QtTest",
    "PySide6.QtCharts",
    "PySide6.QtSpatialAudio",
    "PySide6.QtSensors",
    "PySide6.QtSerialPort",
    "PySide6.QtPositioning",
    "PySide6.QtLocation",
    "PySide6.QtRemoteObjects",
    "PySide6.QtScxml",
    "PySide6.QtStateMachine",
]

# Support debug build with console window when requested via environment
enable_console = os.environ.get("BUILD_CONSOLE", "0").lower() in ("1", "true", "yes")

# Determine icon path
icon_file = "assets/app.ico" if os.path.isfile("assets/app.ico") else None

a = Analysis(
    ["run_app.py"],
    pathex=["src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ScreenTranslator",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=enable_console,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_file,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="ScreenTranslator",
)
