@echo off
setlocal EnableExtensions DisableDelayedExpansion
title Bulk Image Cropper - Startup Check
cd /d "%~dp0"
set "CROPPER_LOG=%~dp0cropper_startup_log.txt"
>"%CROPPER_LOG%" echo Bulk Image Cropper startup check - %date% %time%
if errorlevel 1 set "CROPPER_LOG=%TEMP%\cropper_startup_log.txt"
>"%CROPPER_LOG%" echo Bulk Image Cropper startup check - %date% %time%
if not exist "%~dp0bulk_image_cropper.py" goto missing_file
set "CROPPER_PY="
set "CROPPER_ARGS="
if exist "%~dp0.venv\Scripts\python.exe" call :try_python "%~dp0.venv\Scripts\python.exe"
if defined CROPPER_PY goto run_app
if exist "%~dp0venv\Scripts\python.exe" call :try_python "%~dp0venv\Scripts\python.exe"
if defined CROPPER_PY goto run_app
if exist "%~dp0env\Scripts\python.exe" call :try_python "%~dp0env\Scripts\python.exe"
if defined CROPPER_PY goto run_app
if defined CONDA_PREFIX if exist "%CONDA_PREFIX%\python.exe" call :try_python "%CONDA_PREFIX%\python.exe"
if defined CROPPER_PY goto run_app
where python.exe >nul 2>&1
if not errorlevel 1 call :try_python python.exe
if defined CROPPER_PY goto run_app
where py.exe >nul 2>&1
if not errorlevel 1 call :try_python py.exe -3
if defined CROPPER_PY goto run_app
echo.
echo No tested Python installation could import both PyQt5 and Pillow.
echo Run SETUP_WINDOWS.bat once if the required packages are missing.
echo If you use Anaconda, run this BAT from your usual Anaconda Prompt.
goto show_log

:try_python
>>"%CROPPER_LOG%" echo.
>>"%CROPPER_LOG%" echo Checking "%~1" %2
"%~1" %2 -u -c "import sys; print('Python:', sys.executable); print(sys.version); import PyQt5.QtCore; from PIL import Image; print('Qt:', PyQt5.QtCore.QT_VERSION_STR); print('Pillow:', Image.__version__)" >>"%CROPPER_LOG%" 2>&1
if errorlevel 1 exit /b 0
set "CROPPER_PY=%~1"
set "CROPPER_ARGS=%2"
exit /b 0

:run_app
echo Starting Bulk Image Cropper...
echo Keep this window open while using the app.
echo.
echo Python: "%CROPPER_PY%" %CROPPER_ARGS%
echo Log: "%CROPPER_LOG%"
>>"%CROPPER_LOG%" echo Starting application...
"%CROPPER_PY%" %CROPPER_ARGS% -u -X faulthandler "%~dp0bulk_image_cropper.py" <nul >>"%CROPPER_LOG%" 2>&1
set "CROPPER_EXIT=%ERRORLEVEL%"
>>"%CROPPER_LOG%" echo Application exit code: %CROPPER_EXIT%
echo.
echo Application exited with code %CROPPER_EXIT%.
goto show_log

:missing_file
echo.
echo Put START_CROPPER.bat in the SAME folder as bulk_image_cropper.py.
>>"%CROPPER_LOG%" echo bulk_image_cropper.py was not found beside this launcher.

:show_log
echo.
type "%CROPPER_LOG%"
echo.
echo If the app did not open, send cropper_startup_log.txt or a screenshot.
echo Log location: "%CROPPER_LOG%"
echo.
pause
endlocal
