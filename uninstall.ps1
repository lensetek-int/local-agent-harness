# ====================================================================
# * LENSETEK LEAN AGENT HARNESS - Safe Uninstaller for Windows
# Usage: powershell -ExecutionPolicy Bypass -File uninstall.ps1
# ====================================================================

$ErrorActionPreference = "SilentlyContinue"

Write-Host "====================================================================" -ForegroundColor Cyan
Write-Host "       * LENSETEK LEAN AGENT HARNESS (Uninstaller)                 " -ForegroundColor Cyan
Write-Host "====================================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Stop background processes
Write-Host "[1/3] Stopping running agent and llama-server processes..." -ForegroundColor Yellow
Get-Process -Name "llama-server" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

# Find any python processes running lensetek
Get-CimInstance Win32_Process -Filter "Name LIKE 'python%.exe' AND CommandLine LIKE '%lensetek%'" | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}

Start-Sleep -Seconds 1

# 2. Remove installation folder
$installDir = "$HOME\.lensetek-agent"
$binDir = "$installDir\bin"

Write-Host "[2/3] Removing installation files ($installDir)..." -ForegroundColor Yellow
if (Test-Path $installDir) {
    Remove-Item -Path $installDir -Recurse -Force -ErrorAction SilentlyContinue
    if (Test-Path $installDir) {
        Write-Host "[!] Some files were busy. Retrying in 2 seconds..." -ForegroundColor DarkYellow
        Start-Sleep -Seconds 2
        Remove-Item -Path $installDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# 3. Clean User PATH
Write-Host "[3/3] Cleaning PATH environment variable..." -ForegroundColor Yellow
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -like "*$binDir*") {
    $newPath = ($userPath -split ";" | Where-Object { $_ -ne $binDir -and $_ -ne "" }) -join ";"
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    Write-Host "[+] Removed $binDir from User PATH." -ForegroundColor Green
}

Write-Host ""
Write-Host "====================================================================" -ForegroundColor Green
Write-Host "[OK] Uninstallation Complete! Lensetek Agent has been removed." -ForegroundColor Green
Write-Host "====================================================================" -ForegroundColor Green
