import os
import sys
import json
from pathlib import Path

CLI_DIR = Path(__file__).resolve().parent
REPO_ROOT = CLI_DIR.parent
LLAMA_SERVER_EXE = REPO_ROOT / "bin" / ("llama-server.exe" if sys.platform == "win32" else "llama-server")

DEFAULT_PORT = 8081
DEFAULT_CTX = 8192
DEFAULT_THREADS = min(4, os.cpu_count() or 4)
DEFAULT_KV_CACHE = "q8_0"

USER_SETTINGS_FILE = CLI_DIR / "user_settings.json"
SUPPORTED_LANGUAGES = {
    "en": "English",
    "id": "Bahasa Indonesia",
    "cn": "简体中文 (Chinese)"
}

MCP_PRESETS = {
    "fetch": {
        "command": "uvx",
        "args": ["mcp-server-fetch"],
        "description": "Ambil halaman web statis & ubah ke Markdown bersih (0 browser, super ringan)"
    },
    "playwright-headless": {
        "command": "npx",
        "args": ["-y", "@playwright/mcp@latest", "--headless"],
        "description": "Browser headless Playwright dengan accessibility snapshot (lebih ringan dari Chrome GUI)"
    },
    "chrome-devtools": {
        "command": "npx",
        "args": ["-y", "chrome-devtools-mcp@latest"],
        "description": "Kontrol browser Chrome penuh, inspect DOM, console, dan network"
    },
    "sqlite": {
        "command": "uvx",
        "args": ["mcp-server-sqlite", "--db-path", "database.db"],
        "description": "Query database SQLite lokal"
    },
    "memory": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-memory"],
        "description": "Graph memory persistensi"
    },
    "filesystem": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "."],
        "description": "MCP filesystem standar"
    },
    "github": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
        "env_keys": ["GITHUB_PERSONAL_ACCESS_TOKEN"],
        "description": "GitHub API (membutuhkan GITHUB_PERSONAL_ACCESS_TOKEN di .env.local)"
    }
}

def list_gguf_models() -> list[str]:
    """Mengembalikan daftar nama file / path *.gguf di REPO_ROOT, folder models/, dan custom_models."""
    models = []
    seen = set()

    # 1. Cek di REPO_ROOT
    if REPO_ROOT.exists():
        for f in REPO_ROOT.glob("*.gguf"):
            if not f.name.startswith("mmproj-") and f.name not in seen:
                models.append(f.name)
                seen.add(f.name)

    # 2. Cek di REPO_ROOT / 'models'
    models_dir = REPO_ROOT / "models"
    if models_dir.exists() and models_dir.is_dir():
        for f in models_dir.glob("*.gguf"):
            if not f.name.startswith("mmproj-") and str(f) not in seen and f.name not in seen:
                models.append(str(f))
                seen.add(f.name)

    # 3. Cek custom models yang didaftarkan pengguna di user_settings.json
    try:
        st = load_user_settings()
        for p_str in st.get("custom_models", []):
            p = Path(p_str)
            if p.is_file() and p.suffix.lower() == ".gguf" and str(p) not in seen and p.name not in seen:
                models.append(str(p))
                seen.add(p.name)
            elif p.is_dir():
                for f in p.glob("*.gguf"):
                    if not f.name.startswith("mmproj-") and str(f) not in seen and f.name not in seen:
                        models.append(str(f))
                        seen.add(f.name)
    except Exception:
        pass

    models.sort()
    return models

def add_custom_model_path(path_str: str) -> tuple[bool, str]:
    """Mendaftarkan file *.gguf atau direktori model baru ke user_settings.json."""
    p = Path(path_str).resolve()
    if not p.exists():
        return False, f"Path '{path_str}' tidak ditemukan di sistem."

    st = load_user_settings()
    custom_list = st.get("custom_models", [])
    resolved_str = str(p)
    if resolved_str not in custom_list:
        custom_list.append(resolved_str)
        st["custom_models"] = custom_list
        save_user_settings(st)
        if p.is_file():
            return True, f"Model '{p.name}' berhasil didaftarkan ke daftar model."
        else:
            return True, f"Direktori model '{p}' berhasil didaftarkan ke daftar pencarian model."
    return True, f"Path '{resolved_str}' sudah terdaftar sebelumnya."

def pick_default_model() -> str | None:
    """Prioritaskan lensetek-edge-loop-3b-q4_k_m.gguf jika ada, jika tidak ambil model pertama."""
    models = list_gguf_models()
    if not models:
        return None
    for m in models:
        m_lower = Path(m).name.lower()
        if "lensetek" in m_lower and "loop" in m_lower:
            return m
    return models[0]

def load_mcp_config() -> dict:
    """Membaca konfigurasi MCP servers dari cli-agent/mcp_servers.json."""
    cfg_file = CLI_DIR / "mcp_servers.json"
    if not cfg_file.exists():
        return {}
    try:
        with open(cfg_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[WARN] Gagal membaca mcp_servers.json: {e}")
        return {}

def save_mcp_config(cfg: dict):
    """Menyimpan konfigurasi MCP servers ke cli-agent/mcp_servers.json."""
    cfg_file = CLI_DIR / "mcp_servers.json"
    try:
        with open(cfg_file, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[ERROR] Gagal menyimpan mcp_servers.json: {e}")

def load_dotenv_local() -> dict:
    """Membaca file .env.local di REPO_ROOT secara aman tanpa menimpa os.environ."""
    env_file = REPO_ROOT / ".env.local"
    data = {}
    if not env_file.exists():
        return data
    try:
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    data[k] = v
    except Exception as e:
        print(f"[WARN] Gagal membaca .env.local: {e}")
    return data

def load_user_settings() -> dict:
    """Membaca preferensi pengguna (default language: en)."""
    defaults = {"language": "en"}
    if not USER_SETTINGS_FILE.exists():
        return defaults
    try:
        with open(USER_SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            defaults.update(data)
    except Exception as e:
        print(f"[WARN] Gagal membaca user_settings.json: {e}")
    return defaults

def save_user_settings(settings: dict):
    """Menyimpan preferensi pengguna ke cli-agent/user_settings.json."""
    try:
        with open(USER_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[ERROR] Gagal menyimpan user_settings.json: {e}")

def get_active_language() -> str:
    """Mendapatkan kode bahasa aktif ('en', 'id', 'cn')."""
    st = load_user_settings()
    lang = st.get("language", "en").lower().strip()
    if lang in ("zh", "chinese"):
        return "cn"
    if lang in SUPPORTED_LANGUAGES:
        return lang
    return "en"

def set_active_language(lang_code: str) -> tuple[bool, str]:
    """Mengubah dan menyimpan bahasa aktif ke user_settings.json."""
    code = lang_code.lower().strip()
    if code in ("zh", "chinese"):
        code = "cn"
    if code not in SUPPORTED_LANGUAGES:
        valid_opts = ", ".join(f"'{k}' ({v})" for k, v in SUPPORTED_LANGUAGES.items())
        return False, f"Invalid language code '{lang_code}'. Supported: {valid_opts}"
    st = load_user_settings()
    st["language"] = code
    save_user_settings(st)
    return True, f"Language successfully updated to: {SUPPORTED_LANGUAGES[code]} ({code})"
