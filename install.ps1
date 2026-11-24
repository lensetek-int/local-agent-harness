# ====================================================================
# ⚡ LENSETEK LEAN AGENT HARNESS - One-Liner Installer for Windows
# Usage: irm https://raw.githubusercontent.com/lensetek-int/local-agent-harness/main/install.ps1 | iex
# ====================================================================

$ErrorActionPreference = "Stop"
Write-Host ""
Write-Host "====================================================================" -ForegroundColor Cyan
Write-Host "       ⚡ LENSETEK LEAN AGENT HARNESS (Windows Installer)           " -ForegroundColor Cyan
Write-Host "====================================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Cek Python
$pythonCmd = $null
if (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCmd = "py"
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCmd = "python"
} else {
    Write-Host "[ERROR] Python 3.10+ tidak ditemukan di sistem!" -ForegroundColor Red
    Write-Host "Silakan instal Python terlebih dahulu dari https://www.python.org/downloads/ (Centang 'Add to PATH')"
    exit 1
}

Write-Host "[1/4] Menggunakan Python: $(& $pythonCmd --version)" -ForegroundColor Green

# 2. Cek Folder Instalasi / Git Clone
$installDir = "$HOME\.lensetek-agent"
if (!(Test-Path $installDir)) {
    Write-Host "[2/4] Mengunduh repository ke $installDir..." -ForegroundColor Yellow
    if (Get-Command git -ErrorAction SilentlyContinue) {
        git clone https://github.com/lensetek-int/local-agent-harness.git $installDir
    } else {
        Write-Host "Git tidak terdeteksi, mengunduh file arsip ZIP..." -ForegroundColor Yellow
        $zipPath = "$HOME\lensetek-agent.zip"
        Invoke-WebRequest -Uri "https://github.com/lensetek-int/local-agent-harness/archive/refs/heads/main.zip" -OutFile $zipPath
        Expand-Archive -Path $zipPath -DestinationPath "$HOME" -Force
        Remove-Item $zipPath -Force
        Rename-Item -Path "$HOME\local-agent-harness-main" -NewName ".lensetek-agent" -Force
    }
} else {
    Write-Host "[2/4] Direktori $installDir sudah tersedia." -ForegroundColor Green
}

# 3. Instal Dependensi Python Ringan
Write-Host "[3/5] Memasang dependensi CLI (prompt_toolkit, wcwidth)..." -ForegroundColor Yellow
& $pythonCmd -m pip install --quiet --upgrade pip
& $pythonCmd -m pip install --quiet prompt_toolkit wcwidth

# 4. Siapkan Runtime llama-server di direktori bin
$binDir = "$installDir\bin"
if (!(Test-Path $binDir)) { New-Item -ItemType Directory -Path $binDir -Force | Out-Null }
$llamaExe = "$binDir\llama-server.exe"

Write-Host "[4/5] Memeriksa runtime CPU llama-server..." -ForegroundColor Yellow
if (!(Test-Path $llamaExe)) {
    # Cek apakah repositori lokal memiliki bin/llama-server.exe
    $siblingExe = "$PSScriptRoot\bin\llama-server.exe"
    if (Test-Path $siblingExe) {
        Write-Host "Menyalin binary lokal dari $PSScriptRoot\bin ke $binDir..." -ForegroundColor Green
        Copy-Item "$PSScriptRoot\bin\*" "$binDir\" -Recurse -Force
    } else {
        Write-Host "Mengunduh prebuilt binary llama-server CPU dari ggml-org/llama.cpp (b12675)..." -ForegroundColor Yellow
        $zipUrl = "https://github.com/ggml-org/llama.cpp/releases/download/b12675/llama-b12675-bin-win-cpu-x64.zip"
        $tmpZip = "$HOME\llama-win-cpu.zip"
        try {
            Invoke-WebRequest -Uri $zipUrl -OutFile $tmpZip -UseBasicParsing
            Expand-Archive -Path $tmpZip -DestinationPath $binDir -Force
            Remove-Item $tmpZip -Force
            Write-Host "✓ Runtime llama-server siap di $binDir." -ForegroundColor Green
        } catch {
            Write-Host "[!] Peringatan: Gagal mengunduh otomatis binary ($($_.Exception.Message)). Runtime akan diunduh saat pertama kali menjalankan model." -ForegroundColor Yellow
        }
    }
} else {
    Write-Host "✓ Runtime llama-server sudah tersedia di $llamaExe." -ForegroundColor Green
}

# 5. Buat Shortcut Global 'lensetek' di User PATH
Write-Host "[5/5] Mengonfigurasi shortcut perintah global 'lensetek'..." -ForegroundColor Yellow
$cmdFile = "$binDir\lensetek.cmd"
"@echo off`r`n$pythonCmd `"$installDir\cli-agent\main.py`" %*" | Set-Content -Path $cmdFile -Encoding ASCII

# Tambahkan ke User PATH jika belum ada
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$binDir*") {
    [Environment]::SetEnvironmentVariable("Path", "$userPath;$binDir", "User")
    $env:Path += ";$binDir"
    Write-Host "[+] Menambahkan command 'lensetek' ke User PATH." -ForegroundColor Green
}

Write-Host ""
Write-Host "====================================================================" -ForegroundColor Green
Write-Host "✓ Instalasi Sukses! Anda sekarang bisa menjalankan:" -ForegroundColor Green
Write-Host "   lensetek                    (Jalankan agen dari mana saja)" -ForegroundColor Cyan
Write-Host "   cd $installDir\cli-agent && run_agent.bat" -ForegroundColor Cyan
Write-Host "====================================================================" -ForegroundColor Green
Write-Host ""
