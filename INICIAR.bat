@echo off
setlocal EnableExtensions
title Sindrome Chat Overlay
cd /d "%~dp0"

py -3.12 --version >nul 2>&1
if not errorlevel 1 (
    set "PY_CMD=py -3.12"
) else (
    py -3 --version >nul 2>&1
    if errorlevel 1 goto :python_missing
    set "PY_CMD=py -3"
)

if not exist ".venv\Scripts\python.exe" (
    echo Preparando o aplicativo pela primeira vez...
    %PY_CMD% -m venv .venv
    if errorlevel 1 goto :failed
    call ".venv\Scripts\activate.bat"
    python -m pip install --disable-pip-version-check --upgrade pip
    python -m pip install --disable-pip-version-check -r requirements.txt
) else (
    call ".venv\Scripts\activate.bat"
)

if not exist "assets\message.wav" python tools\create_sound.py
if errorlevel 1 goto :failed

python main.py
if errorlevel 1 goto :failed
exit /b 0

:python_missing
echo Python 3 nao foi encontrado. Instale o Python 3.12 de 64 bits:
echo https://www.python.org/downloads/windows/
pause
exit /b 1

:failed
echo Nao foi possivel iniciar. Consulte o README.md.
pause
exit /b 1
