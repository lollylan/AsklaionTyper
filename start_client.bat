@echo off
setlocal
cd /d "%~dp0"

REM ----------------------------------------------------------------------
REM AsklaionTyper Client (Netzwerk-Variante).
REM Verbindet sich mit einem entfernten Whisper-Server und braucht daher
REM weder lokales Whisper-Modell noch GPU/CUDA. Installation deutlich
REM schlanker als die All-in-One-Variante (~250 MB statt ~2.5 GB).
REM
REM Bootstrap: uv per-User installieren, dann nur Basis-Abhaengigkeiten
REM aus pyproject.toml synchronisieren (kein --extra gpu).
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
echo Synchronisiere Abhaengigkeiten (Netzwerk-Client, ohne GPU) ...
"%UV_CMD%" sync
if errorlevel 1 (
    echo.
    echo [FEHLER] uv sync fehlgeschlagen.
    pause
    exit /b 1
)

REM ----------------------------------------------------------------------
REM AsklaionTyper Client starten (kein NVIDIA-Setup noetig - der Server
REM erledigt die GPU-Arbeit)
REM ----------------------------------------------------------------------
"%UV_CMD%" run python client.py
set "EXITCODE=%ERRORLEVEL%"
if not "%EXITCODE%"=="0" (
    echo.
    echo AsklaionTyper Client wurde mit Exit-Code %EXITCODE% beendet.
    pause
)
endlocal & exit /b %EXITCODE%

REM ----------------------------------------------------------------------
:find_uv
set "UV_CMD="
where uv >nul 2>nul && set "UV_CMD=uv"
if not defined UV_CMD if exist "%UV_EXE%" set "UV_CMD=%UV_EXE%"
goto :eof
