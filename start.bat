@echo off
setlocal
cd /d "%~dp0"

REM ----------------------------------------------------------------------
REM AsklaionTyper - All-in-One (lokale Whisper-Inferenz auf eigener GPU).
REM
REM Bootstrap-Strategie: kein vorinstalliertes Python noetig. uv (in Rust)
REM wird per-User nach %USERPROFILE%\.local\bin installiert (kein Admin),
REM laedt selbststaendig Python 3.11 herunter und legt das venv unter .venv\
REM an. uv.lock garantiert deterministische, reproduzierbare Installs.
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
echo Synchronisiere Abhaengigkeiten (All-in-One + GPU) ...
"%UV_CMD%" sync --extra gpu
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
REM AsklaionTyper starten
REM ----------------------------------------------------------------------
"%UV_CMD%" run python run.py
set "EXITCODE=%ERRORLEVEL%"
if not "%EXITCODE%"=="0" (
    echo.
    echo AsklaionTyper wurde mit Exit-Code %EXITCODE% beendet.
    pause
)
endlocal & exit /b %EXITCODE%

REM ----------------------------------------------------------------------
:find_uv
set "UV_CMD="
where uv >nul 2>nul && set "UV_CMD=uv"
if not defined UV_CMD if exist "%UV_EXE%" set "UV_CMD=%UV_EXE%"
goto :eof
