import os
import sys
import json
from pathlib import Path
try:
    from i18n import t
except ImportError:
    try:
        from cli_agent.i18n import t
    except ImportError:
        def t(key, lang="en", **kwargs):
            return key

CLI_DIR = Path(__file__).resolve().parent
REPO_ROOT = CLI_DIR.parent
LLAMA_SERVER_EXE = REPO_ROOT / "bin" / ("llama-server.exe" if sys.platform == "win32" else "llama-server")

def find_llama_server_binary() -> Path | None:
    """Mencari lokasi binary llama-server di berbagai path kandidat."""
    exe_name = "llama-server.exe" if sys.platform == "win32" else "llama-server"

    # 1. Cek di REPO_ROOT / "bin"
    candidate = REPO_ROOT / "bin" / exe_name
    if candidate.exists() and candidate.is_file():
        return candidate

    # 2. Cek di sistem PATH
    import shutil
    which_path = shutil.which(exe_name) or shutil.which("llama-server")
    if which_path:
        wp = Path(which_path)
        if wp.exists():
            return wp

    # 3. Cek lokasi instalasi umum (~/.lensetek-agent/bin)
    lensetek_home = Path.home() / ".lensetek-agent" / "bin" / exe_name
    if lensetek_home.exists() and lensetek_home.is_file():
        return lensetek_home

    # 4. Cek folder lokal sibling (misal local-llm/bin)
    for p in [REPO_ROOT.parent / "local-llm" / "bin" / exe_name, Path.cwd() / "bin" / exe_name]:
        if p.exists() and p.is_file():
            return p

    return None

def download_llama_server_binary(dest_bin_dir: Path | None = None, lang: str = "en") -> tuple[bool, str, Path | None]:
    """
    Mengunduh runtime prebuilt binary llama-server resmi dari GitHub Releases
    ke folder bin/ sesuai sistem operasi pengguna.
    """
    import io
    import tarfile
    import zipfile
    import urllib.request

    if not dest_bin_dir:
        dest_bin_dir = REPO_ROOT / "bin"
    dest_bin_dir.mkdir(parents=True, exist_ok=True)

    exe_name = "llama-server.exe" if sys.platform == "win32" else "llama-server"
    target_exe = dest_bin_dir / exe_name

    tag = "b12675"
    if sys.platform == "win32":
        archive_name = f"llama-{tag}-bin-win-cpu-x64.zip"
    elif sys.platform == "darwin":
        import platform
        arch = "arm64" if platform.machine().lower() in ("arm64", "aarch64") else "x64"
        archive_name = f"llama-{tag}-bin-macos-{arch}.tar.gz"
    else:
        archive_name = f"llama-{tag}-bin-ubuntu-x64.tar.gz"

    download_url = f"https://github.com/ggml-org/llama.cpp/releases/download/{tag}/{archive_name}"

    try:
        print(f"\n[DOWNLOAD] Mengunduh runtime CPU {exe_name} dari ggml-org/llama.cpp ({tag})...")
        req = urllib.request.Request(download_url, headers={"User-Agent": "LensetekAgent/2.0"})
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = resp.read()

        if archive_name.endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                for member in z.infolist():
                    if not member.is_dir():
                        filename = Path(member.filename).name
                        if filename:
                            out_path = dest_bin_dir / filename
                            with z.open(member) as sf, open(out_path, "wb") as df:
                                df.write(sf.read())
        else:
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
                for member in tar.getmembers():
                    if member.isfile():
                        filename = Path(member.name).name
                        if filename:
                            out_path = dest_bin_dir / filename
                            f = tar.extractfile(member)
                            if f:
                                with open(out_path, "wb") as df:
                                    df.write(f.read())
                                if filename == exe_name:
                                    out_path.chmod(0o755)

        if target_exe.exists():
            if sys.platform != "win32":
                target_exe.chmod(0o755)
            return True, f"Runtime llama-server ({tag}) berhasil diunduh ke {dest_bin_dir}", target_exe
        else:
            return False, f"File {exe_name} tidak ditemukan dalam paket arsip yang diunduh.", None
    except Exception as e:
        return False, f"Gagal mengunduh binary llama-server: {e}", None

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


LORAS_DIR = REPO_ROOT / "models" / "loras"


def list_lora_adapters() -> list[dict]:
    """Mengembalikan daftar adapter LoRA (*.gguf) dari models/loras, custom_loras, dan plugin terpasang."""
    loras = []
    seen = set()

    def _add_lora_file(p: Path, source: str = "local", base_hint: str = ""):
        if not p.is_file() or p.suffix.lower() != ".gguf":
            return
        res_str = str(p.resolve())
        key = res_str.lower() if sys.platform == "win32" else res_str
        if key in seen:
            return
        seen.add(key)
        sz_mb = round(p.stat().st_size / (1024 * 1024), 1)
        loras.append({
            "name": p.name,
            "path": res_str,
            "size_mb": sz_mb,
            "source": source,
            "base_model_hint": base_hint,
        })

    if LORAS_DIR.exists() and LORAS_DIR.is_dir():
        for f in LORAS_DIR.glob("*.gguf"):
            _add_lora_file(f, source="local")

    st = load_user_settings()
    for p_str in st.get("custom_loras", []):
        p = Path(p_str)
        if p.is_file():
            _add_lora_file(p, source="custom")
        elif p.is_dir():
            for f in p.glob("*.gguf"):
                _add_lora_file(f, source="custom")

    # Cek LoRA yang disertakan oleh plugin yang sedang terpasang
    for pid in st.get("installed_plugins", []):
        for base_dir in (REPO_ROOT / "plugins" / pid, Path.home() / ".lensetek-agent" / "plugins" / pid):
            meta_file = base_dir / "plugin.json"
            if meta_file.exists():
                try:
                    meta = json.loads(meta_file.read_text(encoding="utf-8"))
                    for item in meta.get("lora_adapters", []):
                        rel_f = item.get("file", "")
                        if rel_f:
                            _add_lora_file(base_dir / rel_f, source=f"plugin:{pid}", base_hint=item.get("base_model_hint", ""))
                except Exception:
                    pass
                break

    loras.sort(key=lambda x: x["name"].lower())
    return loras


def add_custom_lora_path(path_str: str) -> tuple[bool, str, Path | None]:
    """Mendaftarkan file *.gguf LoRA atau folder LoRA ke user_settings.json."""
    raw = path_str.strip().strip("'\"")
    p = Path(raw).resolve()
    if not p.exists():
        return False, f"LoRA path not found: {path_str}", None
    if p.is_file() and p.suffix.lower() != ".gguf":
        return False, "LoRA adapter must be a .gguf file.", None

    st = load_user_settings()
    custom_list = st.get("custom_loras", [])
    res_str = str(p)
    if res_str not in custom_list:
        custom_list.append(res_str)
        st["custom_loras"] = custom_list
        save_user_settings(st)
        return True, f"Added LoRA: {p.name}", p
    return True, f"LoRA already registered: {p.name}", p


def remove_lora_adapter(path_str: str) -> tuple[bool, str]:
    """Menghapus/melepas pendaftaran LoRA dari custom_loras atau models/loras/."""
    p = Path(path_str.strip()).resolve()
    st = load_user_settings()
    custom_list = st.get("custom_loras", [])
    norm_target = str(p).lower() if sys.platform == "win32" else str(p)
    new_custom = [c for c in custom_list if (str(Path(c).resolve()).lower() if sys.platform == "win32" else str(Path(c).resolve())) != norm_target]
    removed = len(new_custom) != len(custom_list)
    if removed:
        st["custom_loras"] = new_custom

    active_loras = st.get("active_loras", [])
    st["active_loras"] = [a for a in active_loras if (str(Path(a.get("path", "")).resolve()).lower() if sys.platform == "win32" else str(Path(a.get("path", "")).resolve())) != norm_target]
    save_user_settings(st)

    deleted = False
    try:
        p.relative_to(LORAS_DIR.resolve())
        if p.exists() and p.is_file():
            p.unlink()
            deleted = True
    except Exception:
        pass

    if removed or deleted:
        return True, f"Removed LoRA '{p.name}'."
    return False, f"LoRA '{p.name}' not found in custom/local loras."


def get_active_loras() -> list[dict]:
    st = load_user_settings()
    out = []
    for item in st.get("active_loras", []):
        p = item.get("path", "")
        if p and Path(p).exists():
            out.append({"path": str(Path(p).resolve()), "scale": float(item.get("scale", 1.0))})
    return out


def set_active_loras(loras: list[dict]) -> list[dict]:
    clean = []
    for item in loras or []:
        p = str(item.get("path", "")).strip()
        if p and Path(p).exists():
            scale = max(0.0, min(2.0, float(item.get("scale", 1.0))))
            clean.append({"path": str(Path(p).resolve()), "scale": scale})
    st = load_user_settings()
    st["active_loras"] = clean
    save_user_settings(st)
    return clean

def add_custom_model_path(path_str: str, lang: str = "en") -> tuple[bool, str, Path | None]:
    """Mendaftarkan file *.gguf atau direktori model baru ke user_settings.json."""
    raw = path_str.strip().strip("'\"")
    p = Path(raw).resolve()
    if not p.exists():
        return False, t("model_add_not_found", lang, path=path_str), None

    st = load_user_settings()
    custom_list = st.get("custom_models", [])
    resolved_str = str(p)
    if resolved_str not in custom_list:
        custom_list.append(resolved_str)
        st["custom_models"] = custom_list
        save_user_settings(st)
        if p.is_file():
            return True, t("model_add_success_file", lang, name=p.name), p
        else:
            return True, t("model_add_success_dir", lang, path=str(p)), p
    return True, t("model_add_exists", lang, path=resolved_str), p

def resolve_model_file(target: str) -> Path | None:
    """Mencari objek Path dari model berdasarkan nama file, path lengkap, atau substring nama."""
    target_clean = target.strip().strip("'\"")
    if not target_clean:
        return None

    # 1. Direct path check
    p = Path(target_clean)
    if p.is_file() and p.exists():
        return p

    # 2. Check in models/
    models_dir = REPO_ROOT / "models"
    if (models_dir / target_clean).is_file():
        return models_dir / target_clean

    # 3. Check in REPO_ROOT
    if (REPO_ROOT / target_clean).is_file():
        return REPO_ROOT / target_clean

    # 4. Search through available models
    available = list_gguf_models()
    for m in available:
        mp = Path(m)
        if mp.name.lower() == target_clean.lower() or m.lower() == target_clean.lower():
            if mp.is_absolute() and mp.is_file():
                return mp
            elif (models_dir / mp.name).is_file():
                return models_dir / mp.name
            elif (REPO_ROOT / mp.name).is_file():
                return REPO_ROOT / mp.name

    return None

def delete_model(target: str) -> tuple[bool, str, Path | None]:
    """
    Menghapus model GGUF dari disk atau mencabut pendaftaran custom model.
    Mengembalikan (success, message, resolved_path).
    """
    resolved_path = resolve_model_file(target)

    # Hapus juga dari custom_models jika terdaftar di user_settings.json
    st = load_user_settings()
    custom_list = st.get("custom_models", [])
    modified_custom = False

    clean_target = target.strip().strip("'\"").lower()
    new_custom_list = []
    for item in custom_list:
        ip = Path(item)
        if ip.name.lower() == clean_target or item.lower() == clean_target:
            modified_custom = True
        else:
            new_custom_list.append(item)

    if modified_custom:
        st["custom_models"] = new_custom_list
        save_user_settings(st)

    if not resolved_path or not resolved_path.exists():
        if modified_custom:
            return True, f"Path model kustom '{target}' dicabut dari daftar pendaftaran.", None
        return False, f"Model '{target}' tidak ditemukan di disk.", None

    file_size_gb = 0.0
    try:
        file_size_gb = resolved_path.stat().st_size / (1024 ** 3)
    except Exception:
        pass

    try:
        resolved_path.unlink()
        size_msg = f" ({file_size_gb:.2f} GB)" if file_size_gb > 0 else ""
        return True, f"Model '{resolved_path.name}'{size_msg} berhasil dihapus dari disk.", resolved_path
    except Exception as e:
        return False, f"Gagal menghapus file model '{resolved_path.name}': {e}", resolved_path

def load_model_catalog() -> dict:
    """Membaca daftar model yang dapat diunduh dari list.json."""
    candidates = [CLI_DIR / "list.json", REPO_ROOT / "list.json"]
    for c in candidates:
        if c.exists():
            try:
                with open(c, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[WARN] Gagal membaca {c.name}: {e}")
    return {"default_model": "lensetek-edge-loop-3b-q4_k_m.gguf", "models": []}

def download_model_from_catalog(target_id: str = None, dest_dir: Path = None, lang: str = "en") -> tuple[bool, str, str]:
    """
    Mengunduh model dari list.json langsung dari Hugging Face ke folder tujuan.
    Mengembalikan (success, message, filepath_or_empty).
    """
    import time
    import urllib.request

    catalog = load_model_catalog()
    models = catalog.get("models", [])
    if not models:
        return False, "Catalog list.json is empty or not found.", ""

    # Pilih target model
    selected = None
    if target_id:
        tid_lower = target_id.lower().strip()
        for m in models:
            if m.get("id", "").lower() == tid_lower or m.get("filename", "").lower() == tid_lower or tid_lower in m.get("name", "").lower():
                selected = m
                break
        if not selected:
            return False, f"Model ID '{target_id}' not found in list.json.", ""
    else:
        # Default: ambil recommended atau default_model
        def_name = catalog.get("default_model", "lensetek-edge-loop-3b-q4_k_m.gguf")
        for m in models:
            if m.get("filename") == def_name or m.get("recommended"):
                selected = m
                break
        if not selected:
            selected = models[0]

    filename = selected.get("filename")
    url = selected.get("url")
    display_name = selected.get("name", filename)

    if not dest_dir:
        # Simpan di REPO_ROOT / models jika ada, jika tidak langsung di REPO_ROOT
        models_dir = REPO_ROOT / "models"
        if models_dir.exists() and models_dir.is_dir():
            dest_dir = models_dir
        else:
            dest_dir = REPO_ROOT

    dest_dir.mkdir(parents=True, exist_ok=True)
    target_path = dest_dir / filename

    if target_path.exists() and target_path.stat().st_size > 1024 * 1024:
        return True, f"Model '{display_name}' already exists at: {target_path}", str(target_path)

    d_start_lbl = t("download_started", lang)
    print(f"\n\033[1;36m[DOWNLOAD]\033[0m {d_start_lbl}: {display_name} ({selected.get('size_display', '')})")
    print(f"\033[2mSource: {url}\033[0m")
    print(f"\033[2mDestination: {target_path}\033[0m\n")

    from hf_hub import download_file_parallel
    ok, msg, out_path = download_file_parallel(
        url=url,
        out_file=target_path,
        lbl_cancelled=t("download_cancelled", lang),
        lbl_failed=t("download_failed", lang),
        lbl_done=t("download_complete", lang),
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) LensetekHarness/2.0",
    )
    if ok and out_path:
        print(f"\n\033[32m{t('download_complete', lang)}\033[0m {out_path}\n")
        return True, f"{t('download_complete', lang)} {display_name}", str(out_path)
    return False, msg, ""

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

SUPPORTED_EFFORT_LEVELS = {
    "off": "Thinking disabled (fast direct responses without internal monologue)",
    "low": "Concise reasoning (brief focused chain of thought)",
    "medium": "Balanced reasoning (standard exploratory thinking)",
    "high": "Deep iterative reasoning (rigorous deep thinking & verification)"
}

def get_active_effort() -> str:
    """Mendapatkan tingkat thinking effort aktif ('off', 'low', 'medium', 'high'). Default: 'medium'."""
    st = load_user_settings()
    eff = st.get("effort", "medium").lower().strip()
    if eff in SUPPORTED_EFFORT_LEVELS:
        return eff
    return "medium"

def set_active_effort(effort_level: str) -> tuple[bool, str]:
    """Mengubah dan menyimpan tingkat thinking effort ke user_settings.json."""
    level = effort_level.lower().strip()
    num_map = {"1": "off", "2": "low", "3": "medium", "4": "high", "med": "medium"}
    if level in num_map:
        level = num_map[level]
    if level not in SUPPORTED_EFFORT_LEVELS:
        opts = ", ".join(SUPPORTED_EFFORT_LEVELS.keys())
        return False, f"Invalid effort level '{effort_level}'. Supported: {opts} (or 1-4)"
    st = load_user_settings()
    st["effort"] = level
    save_user_settings(st)
    return True, f"Reasoning effort set to: '{level}' ({SUPPORTED_EFFORT_LEVELS[level]})"

def check_model_thinking_support(model_name: str | None) -> tuple[bool, str]:
    """
    Mengecek apakah model yang sedang aktif memiliki kemampuan native reasoning / thinking tags (<think>...</think>).
    """
    if not model_name:
        return False, "No active model loaded"
    m_lower = Path(model_name).name.lower()
    if "iot-coder" in m_lower:
        return False, "Specialized IoT coding & diagram model (direct structured output)"
    reasoning_keywords = ["lensetek", "loop", "r1", "reasoning", "think", "qwq", "deepseek"]
    for kw in reasoning_keywords:
        if kw in m_lower:
            return True, f"Native reasoning & iterative loop supported ({kw})"
    return False, "Standard autoregressive model (no specialized reasoning token pattern)"

