@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

REM ----------------------------------------------------------------------
REM AsklaionTyper Server (GPU-Whisper, FastAPI, HTTPS).
REM Laeuft auf https://<lan-ip>:8000 und nimmt Audio per POST /transcribe
REM von einem oder mehreren AsklaionTyper-Clients entgegen.
REM ----------------------------------------------------------------------

set "VENV_DIR=%CD%\venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"
set "REQ_FILE=%CD%\requirements.txt"
set "STAMP=%VENV_DIR%\.requirements.stamp"
set "SERVER_STAMP=%VENV_DIR%\.server_requirements.stamp"

REM ----------------------------------------------------------------------
REM 1. Locate a usable Python interpreter (prefer 3.11)
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
    echo.
    pause
    exit /b 1
)

REM ----------------------------------------------------------------------
REM 2. Create virtual environment if missing
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
    if exist "%STAMP%"        del "%STAMP%"
    if exist "%SERVER_STAMP%" del "%SERVER_STAMP%"
)

REM ----------------------------------------------------------------------
REM 3. Install / update base dependencies (requirements.txt)
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
REM 4. Install server-only dependencies (fastapi, uvicorn, cryptography,
REM    python-multipart) one-time
REM ----------------------------------------------------------------------
if not exist "%SERVER_STAMP%" (
    echo Installiere Server-Pakete ^(fastapi, uvicorn, cryptography, python-multipart^) ...
    "%VENV_PY%" -m pip install fastapi uvicorn cryptography python-multipart
    if errorlevel 1 (
        echo.
        echo [FEHLER] Server-Pakete konnten nicht installiert werden.
        pause
        exit /b 1
    )
    echo. > "%SERVER_STAMP%"
)

REM ----------------------------------------------------------------------
REM 5. Add bundled NVIDIA CUDA / cuDNN DLLs to PATH
REM ----------------------------------------------------------------------
if exist "%VENV_DIR%\Lib\site-packages\nvidia\cublas\bin" (
    set "PATH=%VENV_DIR%\Lib\site-packages\nvidia\cublas\bin;!PATH!"
)
if exist "%VENV_DIR%\Lib\site-packages\nvidia\cudnn\bin" (
    set "PATH=%VENV_DIR%\Lib\site-packages\nvidia\cudnn\bin;!PATH!"
)

REM ----------------------------------------------------------------------
REM 6. Pre-flight: ist Port 8000 schon belegt?
REM ----------------------------------------------------------------------
netstat -ano | findstr ":8000 " | findstr LISTENING >nul 2>nul
if not errorlevel 1 (
    echo.
    echo [WARNUNG] Port 8000 ist bereits belegt - vermutlich laeuft der
    echo            Server schon. Du kannst nur eine Instanz gleichzeitig
    echo            starten. Beende den anderen Prozess erst:
    echo.
    netstat -ano ^| findstr ":8000 " ^| findstr LISTENING
    echo.
    echo   Im Task-Manager den dortigen PID beenden, dann diese .bat
    echo   erneut starten.
    echo.
    pause
    exit /b 1
)

REM ----------------------------------------------------------------------
REM 7. Launch server (Konsole bleibt offen waehrend der Server laeuft)
REM ----------------------------------------------------------------------
echo.
echo Starte AsklaionTyper Server (large-v3, CUDA, https://0.0.0.0:8000) ...
echo Mit Strg+C beenden.
echo.
"%VENV_PY%" server_GPU_CUDA_Parallel.py
set "EXITCODE=%ERRORLEVEL%"

if not "%EXITCODE%"=="0" (
    echo.
    echo Server wurde mit Exit-Code %EXITCODE% beendet.
)
pause
endlocal ^& exit /b %EXITCODE%
