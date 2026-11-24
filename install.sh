#!/usr/bin/env bash
# ====================================================================
# ⚡ LENSETEK LEAN AGENT HARNESS - One-Liner Installer for Linux/macOS
# Usage: curl -fsSL https://raw.githubusercontent.com/lensetek/local-llm/main/install.sh | bash
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
        git clone --depth 1 https://github.com/lensetek/local-llm.git "$INSTALL_DIR"
    else
        echo "Git tidak ada, mengunduh arsip zip..."
        curl -fsSL https://github.com/lensetek/local-llm/archive/refs/heads/main.tar.gz | tar -xz -C "$HOME"
        mv "$HOME/local-llm-main" "$INSTALL_DIR"
    fi
else
    echo "✓ [2/4] Direktori $INSTALL_DIR sudah ada."
fi

# 3. Instal Dependensi
echo "📦 [3/4] Memasang dependensi python (prompt_toolkit, wcwidth)..."
$PYTHON_BIN -m pip install --quiet --upgrade pip
$PYTHON_BIN -m pip install --quiet prompt_toolkit wcwidth

# 4. Buat Shortcut Launcher di /usr/local/bin atau ~/.local/bin
BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"
LAUNCHER="$BIN_DIR/lensetek"

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
