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

# 1. Cek Python 3
PYTHON_BIN=""
if command -v python3 &>/dev/null; then
    PYTHON_BIN="python3"
elif command -v python &>/dev/null; then
    PYTHON_BIN="python"
else
    echo "❌ Error: Python 3 tidak ditemukan. Silakan pasang python3 terlebih dahulu."
    exit 1
fi

echo "✓ [1/4] Python terdeteksi: $($PYTHON_BIN --version)"

# 2. Direktori Instalasi
INSTALL_DIR="$HOME/.lensetek-agent"
if [ ! -d "$INSTALL_DIR" ]; then
    echo "⬇️  [2/4] Mengkloning repository ke $INSTALL_DIR..."
    if command -v git &>/dev/null; then
        git clone --depth 1 https://github.com/lensetek-int/local-agent-harness.git "$INSTALL_DIR"
    else
        echo "Git tidak ada, mengunduh arsip zip..."
        curl -fsSL https://github.com/lensetek-int/local-agent-harness/archive/refs/heads/main.tar.gz | tar -xz -C "$HOME"
        mv "$HOME/local-agent-harness-main" "$INSTALL_DIR"
    fi
else
    echo "✓ [2/4] Direktori $INSTALL_DIR sudah ada."
fi

# 3. Instal Dependensi
echo "📦 [3/5] Memasang dependensi python (prompt_toolkit, wcwidth)..."
$PYTHON_BIN -m pip install --quiet --upgrade pip
$PYTHON_BIN -m pip install --quiet prompt_toolkit wcwidth

# 4. Unduh runtime llama-server jika belum ada
BIN_DIR="$INSTALL_DIR/bin"
mkdir -p "$BIN_DIR"
LLAMA_EXE="$BIN_DIR/llama-server"

if [ ! -f "$LLAMA_EXE" ]; then
    echo "⬇️  [4/5] Mengunduh runtime CPU llama-server resmi (b12675)..."
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
        echo "✓ Runtime llama-server siap di $BIN_DIR."
    else
        echo "⚠️ Peringatan: Gagal mengunduh binary otomatis. Runtime akan diunduh saat pertama kali menjalankan model."
    fi
else
    echo "✓ [4/5] Runtime llama-server sudah tersedia di $LLAMA_EXE."
fi

# 5. Buat Shortcut Launcher di ~/.local/bin
echo "🚀 [5/5] Mengonfigurasi shortcut launcher CLI..."
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
echo "✓ Instalasi Sukses!"
echo "  Jalankan perintah berikut untuk memulai agen:"
echo "    $LAUNCHER"
echo "  Atau tambahkan ~/.local/bin ke PATH Anda:"
echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
echo "    lensetek"
echo "===================================================================="
echo ""
