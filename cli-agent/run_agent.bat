@echo off
title LENSETEK LEAN AGENT HARNESS
cd /d "%~dp0"
py -c "import prompt_toolkit" 2>nul
if errorlevel 1 (
    echo [SETUP] Menginstal modul UI autocomplete prompt_toolkit...
    py -m pip install prompt_toolkit wcwidth
)
py main.py %*
pause
