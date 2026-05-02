@echo off
setlocal
cd /d "%~dp0"

REM ----------------------------------------------------------------------
REM AsklaionTyper Server (GPU-Whisper, FastAPI, HTTPS).
REM Laeuft auf https://<lan-ip>:8000 und nimmt Audio per POST /transcribe
REM von einem oder mehreren AsklaionTyper-Clients entgegen.
REM
REM Bootstrap: uv per-User installieren, dann pyproject.toml mit den
REM Extras "gpu" (faster-whisper + CUDA-Wheels) und "server" (fastapi,
REM uvicorn, cryptography, python-multipart) synchronisieren.
REM ----------------------------------------------------------------------

set "UV_DIR=%USERPROFILE%\.local\bin"
set "UV_EXE=%UV_DIR%\uv.exe"

call :find_uv
if defined UV_CMD goto have_uv

echo.
echo Installiere uv (Python-Toolchain, ohne Adminrechte) ...
powershell -ExecutionPolicy Bypass -NoProfile -Command "irm https://astral.sh/uv/install.ps1 | iex"
call :find_uv
if not defined UV_CMD (
    echo.
    echo [FEHLER] uv konnte nicht installiert werden.
    echo Internet pruefen oder uv manuell installieren:
    echo   https://docs.astral.sh/uv/getting-started/installation/
    pause
    exit /b 1
)

:have_uv
echo Synchronisiere Abhaengigkeiten (Server + GPU) ...
"%UV_CMD%" sync --extra gpu --extra server
if errorlevel 1 (
    echo.
    echo [FEHLER] uv sync fehlgeschlagen.
    pause
    exit /b 1
)

REM ----------------------------------------------------------------------
REM CUDA / cuDNN DLLs aus dem venv-PATH zugaenglich machen
REM ----------------------------------------------------------------------
set "VENV_LIB=%CD%\.venv\Lib\site-packages"
if exist "%VENV_LIB%\nvidia\cublas\bin" set "PATH=%VENV_LIB%\nvidia\cublas\bin;%PATH%"
if exist "%VENV_LIB%\nvidia\cudnn\bin"  set "PATH=%VENV_LIB%\nvidia\cudnn\bin;%PATH%"

REM ----------------------------------------------------------------------
REM Pre-flight: ist Port 8000 schon belegt?
REM ----------------------------------------------------------------------
netstat -ano | findstr ":8000 " | findstr LISTENING >nul 2>nul
if not errorlevel 1 (
    echo.
    echo [WARNUNG] Port 8000 ist bereits belegt - vermutlich laeuft der
    echo            Server schon. Nur eine Instanz gleichzeitig moeglich.
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
REM Server starten (Konsole bleibt offen waehrend der Server laeuft)
REM ----------------------------------------------------------------------
echo.
echo Starte AsklaionTyper Server (large-v3, CUDA, https://0.0.0.0:8000) ...
echo Mit Strg+C beenden.
echo.
"%UV_CMD%" run python server_GPU_CUDA_Parallel.py
set "EXITCODE=%ERRORLEVEL%"

if not "%EXITCODE%"=="0" (
    echo.
    echo Server wurde mit Exit-Code %EXITCODE% beendet.
)
pause
endlocal & exit /b %EXITCODE%

REM ----------------------------------------------------------------------
:find_uv
set "UV_CMD="
where uv >nul 2>nul && set "UV_CMD=uv"
if not defined UV_CMD if exist "%UV_EXE%" set "UV_CMD=%UV_EXE%"
goto :eof
