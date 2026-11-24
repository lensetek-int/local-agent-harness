# ====================================================================
# ⚡ LENSETEK LEAN AGENT HARNESS - One-Liner Installer for Windows
# Usage: irm https://raw.githubusercontent.com/lensetek/local-llm/main/install.ps1 | iex
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
        git clone https://github.com/lensetek/local-llm.git $installDir
    } else {
        Write-Host "Git tidak terdeteksi, mengunduh file arsip ZIP..." -ForegroundColor Yellow
        $zipPath = "$HOME\lensetek-agent.zip"
        Invoke-WebRequest -Uri "https://github.com/lensetek/local-llm/archive/refs/heads/main.zip" -OutFile $zipPath
        Expand-Archive -Path $zipPath -DestinationPath "$HOME" -Force
        Remove-Item $zipPath -Force
        Rename-Item -Path "$HOME\local-llm-main" -NewName ".lensetek-agent" -Force
    }
} else {
    Write-Host "[2/4] Direktori $installDir sudah tersedia." -ForegroundColor Green
}

# 3. Instal Dependensi Python Ringan
Write-Host "[3/4] Memasang dependensi CLI (prompt_toolkit, wcwidth)..." -ForegroundColor Yellow
& $pythonCmd -m pip install --quiet --upgrade pip
& $pythonCmd -m pip install --quiet prompt_toolkit wcwidth

# 4. Buat Shortcut Global 'lensetek' di PowerShell Profile atau PATH
$binDir = "$HOME\.lensetek-agent\bin"
if (!(Test-Path $binDir)) { New-Item -ItemType Directory -Path $binDir -Force | Out-Null }
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
