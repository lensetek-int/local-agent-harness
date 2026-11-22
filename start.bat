@echo off
title Local LLM Studio
echo ========================================================
echo        LOCAL LLM STUDIO & OPENAI AI AGENT API
echo ========================================================
echo.

if not exist "bin\llama-server.exe" (
    echo [ERROR] bin\llama-server.exe tidak ditemukan!
    echo Silakan pastikan binary llama.cpp tersedia di folder bin\
    pause
    exit /b 1
)

set HAS_GGUF=0
for %%f in (*.gguf) do (
    set HAS_GGUF=1
)

if "%HAS_GGUF%"=="0" (
    echo [PERHATIAN] Belum ada model GGUF yang terpasang di folder ini!
    echo Membuka panduan unduh model otomatis...
    echo.
    py download_models.py
)

echo.
echo Menjalankan Web App Studio di http://127.0.0.1:3000 ...
echo Halaman browser akan terbuka otomatis.
echo Tekan Ctrl+C di jendela ini untuk mematikan server.
echo.

start "" "http://127.0.0.1:3000"

py app.py
pause
