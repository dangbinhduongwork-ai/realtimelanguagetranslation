@echo off
cd /d "%~dp0"
set PATH=%LOCALAPPDATA%\Programs\Python\Python311;%LOCALAPPDATA%\Programs\Python\Python311\Scripts;%PATH%
set PYTHONPATH=src
echo Running capture exclusion diagnostic with MSS backend...
python -m screen_translator --check-exclusion --backend mss
pause
