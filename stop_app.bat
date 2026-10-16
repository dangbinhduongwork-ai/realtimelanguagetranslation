@echo off
echo Stopping any running Screen Translator instances...
taskkill /F /IM python.exe /FI "WINDOWTITLE eq ScreenTranslator*" 2>nul
taskkill /F /IM python.exe 2>nul
echo Done.
pause
