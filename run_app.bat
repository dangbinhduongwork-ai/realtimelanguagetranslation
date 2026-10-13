@echo off
cd /d "%~dp0"
set PATH=%LOCALAPPDATA%\Programs\Python\Python311;%LOCALAPPDATA%\Programs\Python\Python311\Scripts;%PATH%
set PYTHONPATH=src
echo Starting Screen Translator directly with Python 3.11...
python run_app.py
pause
