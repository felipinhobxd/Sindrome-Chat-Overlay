@echo off
setlocal EnableExtensions
title Gerar Sindrome Chat Overlay.exe
cd /d "%~dp0"

echo.
echo ============================================================
echo          SINDROME CHAT OVERLAY - GERADOR DO EXE
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
    echo [1/5] Criando ambiente Python isolado...
    %PY_CMD% -m venv .venv
    if errorlevel 1 goto :failed
) else (
    echo [1/5] Ambiente Python ja existe.
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 goto :failed

echo [2/5] Atualizando as ferramentas de instalacao...
python -m pip install --disable-pip-version-check --upgrade pip wheel
if errorlevel 1 goto :failed

echo [3/5] Instalando dependencias do aplicativo e do gerador...
python -m pip install --disable-pip-version-check -r requirements.txt -r requirements-build.txt
if errorlevel 1 goto :failed

echo [4/5] Gerando o icone e o som de mensagem...
python tools\create_icon.py
if errorlevel 1 goto :failed
python tools\create_sound.py
if errorlevel 1 goto :failed

echo [5/5] Montando o arquivo .exe. Isto pode demorar alguns minutos...
python -m PyInstaller --noconfirm --clean SindromeChatOverlay.spec
if errorlevel 1 goto :failed

copy /Y "README.md" "dist\LEIA-ME.md" >nul
copy /Y "THIRD_PARTY_NOTICES.md" "dist\THIRD_PARTY_NOTICES.md" >nul
copy /Y "LICENSE" "dist\LICENSE.txt" >nul

echo.
echo ============================================================
echo  PRONTO!
echo  Arquivo: %CD%\dist\SindromeChatOverlay.exe
echo ============================================================
echo.
explorer "%CD%\dist"
pause
exit /b 0

:python_missing
echo [ERRO] Python nao foi encontrado.
echo Instale o Python 3.12 de 64 bits e marque "Add Python to PATH":
echo https://www.python.org/downloads/windows/
echo Depois execute este arquivo novamente.
pause
exit /b 1

:failed
echo.
echo [ERRO] Nao foi possivel gerar o .exe.
echo Confira a mensagem acima e o arquivo README.md.
pause
exit /b 1
