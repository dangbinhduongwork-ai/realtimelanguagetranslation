@echo off
cd /d "%~dp0"
set PATH=%LOCALAPPDATA%\Programs\Python\Python311;%LOCALAPPDATA%\Programs\Python\Python311\Scripts;%PATH%
set PYTHONPATH=src
echo Running all pytest unit and integration tests...
python -m pytest -v
pause
