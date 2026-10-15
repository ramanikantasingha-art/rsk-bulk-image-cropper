@echo off
setlocal EnableExtensions DisableDelayedExpansion
title Bulk Image Cropper - One-time Setup
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto install
where py.exe >nul 2>&1
if not errorlevel 1 goto use_py
where python.exe >nul 2>&1
if not errorlevel 1 goto use_python
echo Python was not found. Install Python 3.11 or 3.12 for Windows, then retry.
goto failed
:use_py
py -3 -m venv .venv
if errorlevel 1 goto failed
goto install
:use_python
python -m venv .venv
if errorlevel 1 goto failed
:install
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -c "from PyQt5.QtWidgets import QApplication; from PIL import Image; print('Dependencies ready.')"
if errorlevel 1 goto failed
echo.
echo Setup complete. Double-click START_CROPPER.bat to use the app.
pause
exit /b 0
:failed
echo.
echo Setup did not complete. Send a screenshot of the error above.
pause
exit /b 1
