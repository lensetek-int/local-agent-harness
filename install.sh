#!/usr/bin/env bash
# ====================================================================
# ⚡ LENSETEK LEAN AGENT HARNESS - One-Liner Installer for Linux/macOS
# Usage: curl -fsSL https://raw.githubusercontent.com/lensetek-int/local-agent-harness/main/install.sh | bash
# ====================================================================

set -e

echo ""
echo "===================================================================="
echo "       ⚡ LENSETEK LEAN AGENT HARNESS (Linux & macOS Installer)      "
echo "===================================================================="
echo ""

# 1. Check Python 3 (Auto-install if missing)
PYTHON_BIN=""
if command -v python3 &>/dev/null; then
    PYTHON_BIN="python3"
elif command -v python &>/dev/null; then
    PYTHON_BIN="python"
else
    echo "⬇️  [1/5] Python 3 not found. Attempting automatic installation..."
    if command -v brew &>/dev/null; then
        brew install python@3.12
    elif command -v apt-get &>/dev/null; then
        sudo apt-get update -qq && sudo apt-get install -y python3 python3-pip
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y python3 python3-pip
    elif command -v pacman &>/dev/null; then
        sudo pacman -Sy --noconfirm python python-pip
    else
        echo "❌ Error: Python 3 not found and no supported package manager detected. Please install Python 3.10+ first."
        exit 1
    fi

    if command -v python3 &>/dev/null; then
        PYTHON_BIN="python3"
    elif command -v python &>/dev/null; then
        PYTHON_BIN="python"
    else
        echo "❌ Error: Python 3 installation failed."
        exit 1
    fi
fi

echo "✓ [1/5] Python detected: $($PYTHON_BIN --version)"

# 2. Installation Directory
INSTALL_DIR="$HOME/.lensetek-agent"
if [ ! -d "$INSTALL_DIR" ]; then
    echo "⬇️  [2/5] Cloning repository to $INSTALL_DIR..."
    if command -v git &>/dev/null; then
        git clone --depth 1 https://github.com/lensetek-int/local-agent-harness.git "$INSTALL_DIR"
    else
        echo "Git not found, downloading archive..."
        curl -fsSL https://github.com/lensetek-int/local-agent-harness/archive/refs/heads/main.tar.gz | tar -xz -C "$HOME"
        mv "$HOME/local-agent-harness-main" "$INSTALL_DIR"
    fi
else
    echo "⬇️  [2/5] Updating existing installation in $INSTALL_DIR..."
    if [ -d "$INSTALL_DIR/.git" ] && command -v git &>/dev/null; then
        git -C "$INSTALL_DIR" pull --quiet || true
    fi
    echo "✓ [2/5] Directory $INSTALL_DIR is up to date."
fi

# 3. Install Dependencies
echo "📦 [3/5] Installing Python dependencies (prompt_toolkit, wcwidth)..."
$PYTHON_BIN -m pip install --quiet --no-cache-dir --upgrade pip
$PYTHON_BIN -m pip install --quiet --no-cache-dir prompt_toolkit wcwidth

# 4. Download llama-server runtime if missing
BIN_DIR="$INSTALL_DIR/bin"
mkdir -p "$BIN_DIR"
LLAMA_EXE="$BIN_DIR/llama-server"

if [ ! -f "$LLAMA_EXE" ]; then
    echo "⬇️  [4/5] Downloading official llama-server CPU runtime (b12675)..."
    TAG="b12675"
    OS_TYPE="$(uname -s)"
    ARCH_TYPE="$(uname -m)"

    if [ "$OS_TYPE" = "Darwin" ]; then
        if [ "$ARCH_TYPE" = "arm64" ]; then
            TAR_NAME="llama-${TAG}-bin-macos-arm64.tar.gz"
        else
            TAR_NAME="llama-${TAG}-bin-macos-x64.tar.gz"
        fi
    else
        TAR_NAME="llama-${TAG}-bin-ubuntu-x64.tar.gz"
    fi

    DOWNLOAD_URL="https://github.com/ggml-org/llama.cpp/releases/download/${TAG}/${TAR_NAME}"
    TMP_TAR="/tmp/llama-server.tar.gz"
    if curl -fsSL "$DOWNLOAD_URL" -o "$TMP_TAR"; then
        tar -xzf "$TMP_TAR" -C "$BIN_DIR"
        rm -f "$TMP_TAR"
        chmod +x "$BIN_DIR"/* || true
        echo "✓ llama-server runtime ready at $BIN_DIR."
    else
        echo "⚠️ Warning: Failed to auto-download binary. It will be downloaded on first model run."
    fi
else
    echo "✓ [4/5] llama-server runtime is already available at $LLAMA_EXE."
fi

# 5. Create Launcher Shortcut in ~/.local/bin
echo "🚀 [5/5] Configuring global CLI launcher..."
LOCAL_BIN="$HOME/.local/bin"
mkdir -p "$LOCAL_BIN"
LAUNCHER="$LOCAL_BIN/lensetek"

cat <<EOF > "$LAUNCHER"
#!/usr/bin/env bash
exec $PYTHON_BIN "$INSTALL_DIR/cli-agent/main.py" "\$@"
EOF
chmod +x "$LAUNCHER"

echo ""
echo "===================================================================="
echo "✓ Installation Successful!"
echo "  Run one of the following commands to get started:"
echo "    $LAUNCHER"
echo "  Or ensure ~/.local/bin is in your PATH:"
echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
echo "    lensetek"
echo "===================================================================="
echo ""
