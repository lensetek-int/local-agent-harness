# ====================================================================
# * LENSETEK LEAN AGENT HARNESS - One-Liner Installer for Windows
# Usage: irm https://raw.githubusercontent.com/lensetek-int/local-agent-harness/main/install.ps1 | iex
# ====================================================================

$ErrorActionPreference = "Stop"
Write-Host ""
Write-Host "====================================================================" -ForegroundColor Cyan
Write-Host "       * LENSETEK LEAN AGENT HARNESS (Windows Installer)           " -ForegroundColor Cyan
Write-Host "====================================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Check Python (Auto-install via winget or official installer if missing)
$pythonCmd = $null
if (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCmd = "py"
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCmd = "python"
} else {
    Write-Host "[1/5] Python 3.10+ not found. Attempting automatic Python installation..." -ForegroundColor Yellow
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
    } else {
        Write-Host "Downloading official Python 3.12.8 installer for Windows..." -ForegroundColor Yellow
        $pyInstaller = "$HOME\python-3.12.8-amd64.exe"
        Invoke-WebRequest -Uri "https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe" -OutFile $pyInstaller -UseBasicParsing
        Start-Process -FilePath $pyInstaller -ArgumentList "/quiet InstallAllUsers=0 PrependPath=1 Include_test=0" -Wait
        Remove-Item $pyInstaller -Force -ErrorAction SilentlyContinue
    }

    # Refresh PATH in current session
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $pythonCmd = "py"
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        $pythonCmd = "python"
    } else {
        Write-Host "[ERROR] Automatic Python setup finished, but 'python' is not yet in this shell's PATH." -ForegroundColor Red
        Write-Host "Please close and reopen PowerShell, then re-run this installer." -ForegroundColor Yellow
        exit 1
    }
}

Write-Host "[1/5] Using Python: $(& $pythonCmd --version)" -ForegroundColor Green

# 2. Check Installation Directory / Git Clone
$installDir = "$HOME\.lensetek-agent"
# Stop any running llama-server process so binary/DLL files are not locked
Get-Process -Name "llama-server" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

if (!(Test-Path "$installDir\cli-agent\main.py")) {
    Write-Host "[2/5] Downloading repository files to $installDir..." -ForegroundColor Yellow
    $zipPath = "$HOME\lensetek-agent.zip"
    Invoke-WebRequest -Uri "https://github.com/lensetek-int/local-agent-harness/archive/refs/heads/main.zip" -OutFile $zipPath
    Expand-Archive -Path $zipPath -DestinationPath "$HOME" -Force
    Remove-Item $zipPath -Force
    if (!(Test-Path $installDir)) { New-Item -ItemType Directory -Path $installDir -Force | Out-Null }
    Copy-Item -Path "$HOME\local-agent-harness-main\*" -Destination $installDir -Recurse -Force
    Remove-Item -Path "$HOME\local-agent-harness-main" -Recurse -Force
} else {
    Write-Host "[2/5] Updating existing installation in $installDir..." -ForegroundColor Yellow
    if ((Test-Path "$installDir\.git") -and (Get-Command git -ErrorAction SilentlyContinue)) {
        git -C $installDir reset --hard HEAD --quiet 2>$null
        git -C $installDir pull --quiet 2>$null
    }
    Write-Host "[OK] Directory $installDir is up to date." -ForegroundColor Green
}

# 3. Install Lightweight Python Dependencies
Write-Host "[3/5] Installing CLI dependencies (prompt_toolkit, wcwidth)..." -ForegroundColor Yellow
& $pythonCmd -m pip install --quiet --no-cache-dir --upgrade pip
& $pythonCmd -m pip install --quiet --no-cache-dir prompt_toolkit wcwidth

# 4. Prepare llama-server Runtime in bin directory
$binDir = "$installDir\bin"
if (!(Test-Path $binDir)) { New-Item -ItemType Directory -Path $binDir -Force | Out-Null }
$llamaExe = "$binDir\llama-server.exe"

Write-Host "[4/5] Checking llama-server CPU runtime..." -ForegroundColor Yellow
if (!(Test-Path $llamaExe)) {
    $siblingExe = "$PSScriptRoot\bin\llama-server.exe"
    if (Test-Path $siblingExe) {
        Write-Host "Copying local binary from $PSScriptRoot\bin to $binDir..." -ForegroundColor Green
        Copy-Item "$PSScriptRoot\bin\*" "$binDir\" -Recurse -Force
    } else {
        Write-Host "Downloading prebuilt llama-server CPU binary from ggml-org/llama.cpp (b12675)..." -ForegroundColor Yellow
        $zipUrl = "https://github.com/ggml-org/llama.cpp/releases/download/b12675/llama-b12675-bin-win-cpu-x64.zip"
        $tmpZip = "$HOME\llama-win-cpu.zip"
        try {
            Invoke-WebRequest -Uri $zipUrl -OutFile $tmpZip -UseBasicParsing
            Expand-Archive -Path $tmpZip -DestinationPath $binDir -Force
            Remove-Item $tmpZip -Force
            Write-Host "[OK] llama-server runtime ready at $binDir." -ForegroundColor Green
        } catch {
            Write-Host "[!] Warning: Failed to auto-download binary ($($_.Exception.Message)). It will be downloaded on first model run." -ForegroundColor Yellow
        }
    }
} else {
    Write-Host "[OK] llama-server runtime is already available at $llamaExe." -ForegroundColor Green
}

# 5. Create Global 'lensetek' Shortcut in User PATH
Write-Host "[5/5] Configuring global 'lensetek' CLI command..." -ForegroundColor Yellow
$cmdFile = "$binDir\lensetek.cmd"
"@echo off`r`n$pythonCmd `"$installDir\cli-agent\main.py`" %*" | Set-Content -Path $cmdFile -Encoding ASCII

# Add to User PATH if not already present
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$binDir*") {
    [Environment]::SetEnvironmentVariable("Path", "$userPath;$binDir", "User")
    $env:Path += ";$binDir"
    Write-Host "[+] Added 'lensetek' command to User PATH." -ForegroundColor Green
}

Write-Host ""
Write-Host "====================================================================" -ForegroundColor Green
Write-Host "[OK] Installation Successful! You can now run:" -ForegroundColor Green
Write-Host "   lensetek                    (Launch agent from anywhere)" -ForegroundColor Cyan
Write-Host "   lensetek --gui              (Open Lensetek Agent Web Workspace)" -ForegroundColor Cyan
Write-Host "   lensetek --help             (Show all CLI options)" -ForegroundColor Cyan
Write-Host "====================================================================" -ForegroundColor Green
Write-Host ""
