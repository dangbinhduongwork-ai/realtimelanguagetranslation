@echo off
cd /d "%~dp0"
set PATH=%LOCALAPPDATA%\Programs\Python\Python311;%LOCALAPPDATA%\Programs\Python\Python311\Scripts;%PATH%
taskkill /F /IM ScreenTranslator.exe 2>nul
echo ====================================================
echo Rebuilding Screen Translator with fixes...
echo ====================================================
powershell -ExecutionPolicy Bypass -File scripts\build.ps1 -Clean -Zip
pause
