@echo off
cd /d "%~dp0"
call venv\Scripts\activate.bat
set "PATH=%CD%\venv\Lib\site-packages\nvidia\cublas\bin;%CD%\venv\Lib\site-packages\nvidia\cudnn\bin;%PATH%"
python run.py
pause
