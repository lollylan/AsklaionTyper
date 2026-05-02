@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

REM ----------------------------------------------------------------------
REM AsklaionTyper Client (Netzwerk-Variante)
REM Verbindet sich mit einem entfernten Whisper-Server
REM (server_GPU_CUDA_Parallel.py). Lokales Whisper-Modell wird nicht
REM geladen - kein GPU/VRAM-Verbrauch.
REM ----------------------------------------------------------------------

set "VENV_DIR=%CD%\venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"
set "REQ_FILE=%CD%\requirements.txt"
set "STAMP=%VENV_DIR%\.requirements.stamp"

REM ----------------------------------------------------------------------
REM 1. Locate a usable Python interpreter (prefer 3.11, then any python)
REM ----------------------------------------------------------------------
set "PYTHON_CMD="

where py >nul 2>nul
if not errorlevel 1 (
    py -3.11 -c "import sys" >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON_CMD=py -3.11"
    )
)

if not defined PYTHON_CMD (
    where python >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=python"
)

if not defined PYTHON_CMD (
    where py >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=py"
)

if not defined PYTHON_CMD (
    echo.
    echo [FEHLER] Es wurde keine Python-Installation gefunden.
    echo Bitte Python 3.11 installieren: https://www.python.org/downloads/release/python-3119/
    echo Bei der Installation "Add Python to PATH" anhaken.
    echo.
    pause
    exit /b 1
)

REM ----------------------------------------------------------------------
REM 2. Create virtual environment if it does not exist
REM ----------------------------------------------------------------------
if not exist "%VENV_PY%" (
    echo Erstelle virtuelle Umgebung in "%VENV_DIR%" ...
    %PYTHON_CMD% -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo.
        echo [FEHLER] venv konnte nicht erstellt werden.
        pause
        exit /b 1
    )
    if exist "%STAMP%" del "%STAMP%"
)

REM ----------------------------------------------------------------------
REM 3. Install / update dependencies if requirements.txt changed
REM ----------------------------------------------------------------------
set "NEED_INSTALL=0"
if not exist "%STAMP%" (
    set "NEED_INSTALL=1"
) else (
    for %%R in ("%REQ_FILE%") do set "REQ_TIME=%%~tR"
    for %%S in ("%STAMP%")    do set "STAMP_TIME=%%~tS"
    if "!REQ_TIME!" GTR "!STAMP_TIME!" set "NEED_INSTALL=1"
)

if "!NEED_INSTALL!"=="1" (
    echo Installiere/Aktualisiere Pakete aus requirements.txt ...
    "%VENV_PY%" -m pip install --upgrade pip
    "%VENV_PY%" -m pip install -r "%REQ_FILE%"
    if errorlevel 1 (
        echo.
        echo [FEHLER] pip install fehlgeschlagen.
        pause
        exit /b 1
    )
    echo. > "%STAMP%"
)

REM ----------------------------------------------------------------------
REM 4. Launch AsklaionTyper Client (no NVIDIA DLLs needed - remote server
REM    does the GPU work)
REM ----------------------------------------------------------------------
"%VENV_PY%" client.py
set "EXITCODE=%ERRORLEVEL%"

if not "%EXITCODE%"=="0" (
    echo.
    echo AsklaionTyper Client wurde mit Exit-Code %EXITCODE% beendet.
    pause
)

endlocal ^& exit /b %EXITCODE%
