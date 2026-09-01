@echo off
setlocal EnableExtensions
title Build Sindrome Chat Overlay.exe
cd /d "%~dp0"

echo.
echo ============================================================
echo          SINDROME CHAT OVERLAY - EXE BUILDER
echo ============================================================
echo.

py -3.12 --version >nul 2>&1
if not errorlevel 1 (
    set "PY_CMD=py -3.12"
) else (
    py -3 --version >nul 2>&1
    if errorlevel 1 goto :python_missing
    set "PY_CMD=py -3"
)

if not exist ".venv\Scripts\python.exe" (
    echo [1/5] Creating an isolated Python environment...
    %PY_CMD% -m venv .venv
    if errorlevel 1 goto :failed
) else (
    echo [1/5] The Python environment already exists.
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 goto :failed

echo [2/5] Updating installation tools...
python -m pip install --disable-pip-version-check --upgrade pip wheel
if errorlevel 1 goto :failed

echo [3/5] Installing application and build dependencies...
python -m pip install --disable-pip-version-check -r requirements.txt -r requirements-build.txt
if errorlevel 1 goto :failed

echo [4/5] Generating the application icon and message sound...
python tools\create_icon.py
if errorlevel 1 goto :failed
python tools\create_sound.py
if errorlevel 1 goto :failed

echo [5/5] Building the executable. This may take a few minutes...
python -m PyInstaller --noconfirm --clean SindromeChatOverlay.spec
if errorlevel 1 goto :failed

copy /Y "README.md" "dist\README.md" >nul
copy /Y "THIRD_PARTY_NOTICES.md" "dist\THIRD_PARTY_NOTICES.md" >nul
copy /Y "LICENSE" "dist\LICENSE.txt" >nul

echo.
echo ============================================================
echo  COMPLETE
echo  File: %CD%\dist\SindromeChatOverlay.exe
echo ============================================================
echo.
explorer "%CD%\dist"
pause
exit /b 0

:python_missing
echo [ERROR] Python was not found.
echo Install 64-bit Python 3.12 and enable "Add Python to PATH":
echo https://www.python.org/downloads/windows/
echo Then run this file again.
pause
exit /b 1

:failed
echo.
echo [ERROR] The executable could not be built.
echo Review the message above and README.md.
pause
exit /b 1
