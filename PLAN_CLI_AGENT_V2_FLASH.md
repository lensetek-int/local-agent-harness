# ⚡ PLAN EKSEKUSI ATOMIK V2 — GEMINI 3.8 FLASH (MEDIUM)
## Upgrade `cli-agent/` menjadi `LENSETEK LEAN AGENT (MCP Orchestrator)`

> **Petunjuk Penggunaan untuk Agen (Gemini 3.8 Flash Medium):**
> Dokumen ini adalah *blueprint eksekusi deterministik* untuk meng-upgrade folder `cli-agent/` yang sudah ada di repo `local-llm`.
>
> **Aturan Emas (WAJIB DIPATUHI):**
> 1. **Gunakan `py`** (bukan `python`) untuk semua perintah Python di Windows PowerShell.
> 2. **DILARANG mengubah file edge computing default** di root repo (`app.py`, `start.bat`, `rag_engine.py`, `safety_guard.py`, `requirements.txt`). Semua perubahan hanya di dalam folder `cli-agent/`.
> 3. **Gunakan Python Standard Library saja** (tanpa `pip install` tambahan seperti PyYAML atau schedule).
> 4. **DILARANG** melakukan hardcode API key, token, atau kredensial di `mcp_servers.json` atau kode Python. Kredensial untuk MCP hanya boleh direferensikan lewat nama environment variable (`env_keys`) dan dibaca dari `.env.local` di root repo atau `os.environ`.
> 5. **WAJIB** jalankan **Perintah Verifikasi** di akhir setiap Sprint sebelum lanjut ke Sprint berikutnya.

---

## 📋 Peta 4 Sprint Atomik

| Sprint | Judul Pekerjaan | File Target | Tujuan Utama |
| :---: | :--- | :--- | :--- |
| **Sprint 1** | Rebranding, Safety Modes & Katalog MCP Ringan | `cli-agent/config.py`, `cli-agent/mcp_servers.json`, `cli-agent/tools_fs.py`, `cli-agent/run_agent.bat` | Tambah safety mode (`strict`, `auto-approve`, `yolo`), katalog preset MCP ringan (`fetch`, `playwright-headless`), dan loader `.env.local`. |
| **Sprint 2** | Universal MCP Installer (`mcp_install`) & Env Injection | `cli-agent/mcp_client.py` | Tambah tool `mcp_install` agar agen/user bisa install segala MCP (`npx`, `uvx`, `py`, JSON) + tes handshake otomatis. |
| **Sprint 3** | Sistem Skills Lokal & Global (`npx skills add`) | `cli-agent/skills_manager.py`, `cli-agent/skills/*` | Membaca `SKILL.md` lokal & global (`~/.agents/skills`, `~/.claude/skills`, `~/.codex/skills`, `~/.gemini/antigravity/skills`), panggil via `/<skill>`, dan buat skill baru. |
| **Sprint 4** | Mode `/goal`, `/loop`, `/schedule` (Win/Linux/Mac) & `--once` | `cli-agent/scheduler.py`, `cli-agent/agent.py`, `cli-agent/main.py` | Rebranding banner `LENSETEK LEAN AGENT (MCP Orchestrator)`, mode otonom `/goal`, `/loop`, scheduler lintas OS + `--once`. |

---

## 🔧 SPRINT 1: Rebranding, Safety Modes & Katalog MCP Ringan

### 1. Masalah Logika yang Dicegah
- Mode `--auto-approve` harus tetap aman: hanya melewatkan konfirmasi `[y/N]` jika path target berada di dalam `workspace_root` (gunakan `Path.is_relative_to()`), sedangkan aksi di luar workspace tetap wajib `[y/N]`.
- Mode `--yolo` melewatkan semua konfirmasi `[y/N]`, namun tetap memblokir perintah destruktif fatal (`format `, `rm -rf /`, `del /s /q c:\`, `rd /s /q c:\`).
- Jika MCP butuh token (misal GitHub MCP), nilai token tidak boleh ditulis ke `mcp_servers.json`; cukup baca dari `.env.local` atau `os.environ`.

### 2. Spesifikasi Perubahan Eksak

#### A. Update `cli-agent/run_agent.bat`
Ubah title menjadi:
```bat
@echo off
title LENSETEK LEAN AGENT (MCP Orchestrator)
cd /d "%~dp0"
py main.py %*
pause
```

#### B. Update `cli-agent/mcp_servers.json`
Tambahkan preset ringan `fetch` dan `playwright-headless` di samping `chrome-devtools` dan `filesystem`:
```json
{
  "fetch": {
    "command": "uvx",
    "args": ["mcp-server-fetch"],
    "enabled": true,
    "description": "Ambil halaman web statis & ubah ke Markdown bersih (0 browser, super ringan)"
  },
  "playwright-headless": {
    "command": "npx",
    "args": ["-y", "@playwright/mcp@latest", "--headless"],
    "enabled": false,
    "description": "Browser headless Playwright dengan accessibility snapshot (lebih ringan dari Chrome GUI)"
  },
  "chrome-devtools": {
    "command": "npx",
    "args": ["-y", "chrome-devtools-mcp@latest"],
    "enabled": false,
    "description": "Kontrol browser Chrome penuh, inspect DOM, console, dan network"
  },
  "filesystem": {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-filesystem", "."],
    "enabled": false,
    "description": "MCP filesystem standar (opsional, sudah ada tools_fs bawaan)"
  }
}
```

#### C. Update `cli-agent/config.py`
Tambahkan:
1. `MCP_PRESETS` dict berisi preset siap pasang: `fetch`, `playwright-headless`, `chrome-devtools`, `sqlite`, `memory`, `filesystem`, `github` (untuk `github`, isi `"env_keys": ["GITHUB_PERSONAL_ACCESS_TOKEN"]`).
2. `save_mcp_config(cfg: dict)`: simpan `cfg` ke `CLI_DIR / "mcp_servers.json"` dengan `indent=2`.
3. `load_dotenv_local() -> dict`: baca `REPO_ROOT / ".env.local"` (jika ada), parse baris `KEY=VALUE` (abaikan komentar `#` dan kosong), dan kembalikan dict tanpa menimpa `os.environ` yang sudah ada.

#### D. Update `cli-agent/tools_fs.py`
Tambahkan parameter `safety_mode: str = "strict"` pada `LocalWorkspaceTools.__init__` dan method `set_safety_mode(mode: str)` (pilihan valid: `"strict"`, `"auto-approve"`, `"yolo"`, `"read-only"`):
- Buat helper `_needs_confirmation(self, target_path: Path | None = None) -> bool`:
  - Jika `safety_mode == "yolo"`: return `False`.
  - Jika `safety_mode == "read-only"`: return `False` (dan tolak aksi tulis/shell secara langsung!).
  - Jika `safety_mode == "auto-approve"`: jika `target_path` berada di dalam `self.workspace_root` (`target_path.is_relative_to(self.workspace_root)`), return `False`; selain itu return `True`.
  - Jika `safety_mode == "strict"`: return `True`.
- Terapkan `_needs_confirmation` di `write_or_edit_file` dan `run_command`. Jika `safety_mode == "read-only"`, langsung kembalikan `"Ditolak: Agent berjalan dalam mode read-only (headless default)."`.

### 3. Perintah Verifikasi Sprint 1
```powershell
py -c "import sys; sys.path.insert(0, 'cli-agent'); import config; from tools_fs import LocalWorkspaceTools; t = LocalWorkspaceTools('.', safety_mode='auto-approve'); print('Presets:', list(config.MCP_PRESETS.keys())); print('In-WS confirm:', t._needs_confirmation(t.workspace_root / 'test.txt')); print('Out-WS confirm:', t._needs_confirmation(t.workspace_root.parent / 'outside.txt'))"
```
**Kriteria Lulus:** `Presets` mencetak daftar preset, `In-WS confirm: False`, dan `Out-WS confirm: True`.

---

## 🔧 SPRINT 2: Universal MCP Installer (`mcp_install`) & Env Injection

### 1. Masalah Logika yang Dicegah
- `MCPManager` harus bisa menginstal MCP baru baik dari nama preset (`fetch`), command custom (`npx`, `uvx`, `py`), maupun blok JSON, lalu langsung memverifikasi bahwa file `mcp_servers.json` tersimpan dan server bisa handshake.
- Jika ada `env_keys` di config server, nilai diambil saat runtime dari `os.environ` atau `config.load_dotenv_local()`, tidak pernah ditulis ke `mcp_servers.json`.

### 2. Spesifikasi Perubahan Eksak (`cli-agent/mcp_client.py`)
1. Ubah `clientInfo` di `MCPStdioClient.start()` menjadi `{"name": "lensetek-lean-agent", "version": "2.0.0"}`.
2. Pada `MCPManager.__init__(self, config_dict=None, confirm_fn=None, safety_mode="strict")`:
   - Tambahkan `set_safety_mode(self, mode: str)` (jika `"yolo"`, lewati `confirm_fn`; jika `"read-only"`, tolak `mcp_call` yang mengubah state / `mcp_install`).
   - Saat memulai client di `_get_or_start_client`: gabungkan `os.environ.copy()` dengan `config.load_dotenv_local()` untuk setiap key di `cfg.get("env_keys", [])`. Jika ada `env_keys` yang nilainya kosong, tampilkan peringatan informatif agar user mengisinya di `.env.local`.
3. Tambahkan method pada `MCPManager`:
   - `install_server(self, name: str, command: str = "", args: list[str] | None = None, env_keys: list[str] | None = None, description: str = "") -> str`:
     - Jika `name` ada di `config.MCP_PRESETS` dan `command` kosong, ambil template dari `MCP_PRESETS[name]`.
     - Minta konfirmasi user (kecuali `safety_mode == "yolo"`).
     - Simpan ke `self.config[name]` (dengan `enabled: True`) dan panggil `config.save_mcp_config(self.config)`.
     - Langsung uji koneksi (`_get_or_start_client(name)` + `list_tools()`) dan kembalikan laporan jumlah tool yang berhasil dimuat (atau pesan error yang jelas jika binary seperti `uvx`/`npx` belum terpasang).
   - `test_server(self, name: str) -> str`: tes start + `list_tools()` dan laporkan hasilnya.
   - `remove_server(self, name: str) -> str`: tutup client jika aktif, hapus dari `self.config`, simpan via `config.save_mcp_config`.
   - `toggle_server(self, name: str, enabled: bool) -> str`: ubah `enabled` dan simpan.
4. Tambahkan 1 tool baru di `MCPManager.get_openai_tools()`:
   - **`mcp_install`**: parameter `name` (nama alias/preset), `command` (opsional jika preset), `args` (list string, opsional), `description` (opsional).
   - Di `MCPManager.execute()`, tangani `name == "mcp_install"`.

### 3. Perintah Verifikasi Sprint 2
```powershell
py -c "import sys; sys.path.insert(0, 'cli-agent'); import config; from mcp_client import MCPManager; m = MCPManager(config.load_mcp_config()); print('Tools:', [x['function']['name'] for x in m.get_openai_tools()]); m.close_all()"
```
**Kriteria Lulus:** Menampilkan `['mcp_list_tools', 'mcp_call', 'mcp_install']` tanpa error.

---

## 🔧 SPRINT 3: Sistem Skills Lokal & Global (`npx skills add`)

### 1. Masalah Logika yang Dicegah
- User memiliki banyak skill global yang dipasang via `npx skills add` di `~\.agents\skills`, `~\.claude\skills`, `~\.codex\skills`, dan `~\.gemini\antigravity\skills`.
- **DILARANG** memasukkan semua isi atau daftar 100+ skill ke `SYSTEM_PROMPT` karena akan meledakkan context `8192`. Gunakan pola **on-demand**: hanya dimuat saat user memanggil `/<nama-skill>` atau agen memanggil `search_skills`.
- Di Windows, `npx skills add` sering membuat *junction/symlink* di `~/.agents/skills/`. Gunakan `Path.is_dir()` dan cek `(folder / "SKILL.md").exists()`.
- Jika `SKILL.md` sangat panjang, potong maksimal **4000 karakter** saat disuntikkan ke prompt.

### 2. Spesifikasi File Eksak

#### A. Buat `cli-agent/skills_manager.py`
Class `SkillManager`:
- `__init__(self, local_skills_dir: Path, workspace_root: Path | None = None)`:
  - Tentukan urutan direktori scan (prioritas dari yang tertinggi — nama yang sama di lokal meng-override global):
    1. `local_skills_dir` (`cli-agent/skills`)
    2. `workspace_root / ".agents" / "skills"` dan `workspace_root / ".skills"` (jika `workspace_root` ada)
    3. `Path.home() / ".agents" / "skills"` (standar global `npx skills add -g`)
    4. `Path.home() / ".claude" / "skills"`
    5. `Path.home() / ".codex" / "skills"`
    6. `Path.home() / ".gemini" / "antigravity" / "skills"`
- Helper `_parse_frontmatter(text: str) -> tuple[dict, str]`:
  - Parse frontmatter YAML `--- ... ---` secara manual menggunakan string split/regex (tanpa library eksternal) untuk mengambil `name` dan `description`, lalu mengembalikan `(meta_dict, body_markdown)`.
- Method `scan_skills() -> dict[str, dict]`:
  - Kembalikan dictionary `{skill_name: {"name": ..., "description": ..., "path": Path, "source": "local"|"workspace"|"global"}}`.
  - Abaikan folder yang diawali titik (`.system`, `.git`).
- Method `get_skill_prompt(self, skill_name: str) -> str | None`:
  - Cari skill dari hasil `scan_skills()` (cocokkan exact atau case-insensitive).
  - Baca isi `SKILL.md`, ambil body (atau full text), potong maksimal `4000` karakter jika terlalu panjang.
- Method `search_skills(self, query: str = "") -> list[dict]`:
  - Filter daftar skill berdasarkan `query` pada `name` atau `description`.
- Method `create_skill(self, name: str, description: str, instructions: str) -> str`:
  - Normalisasi `name` menjadi lowercase slug (`[a-z0-9_-]`).
  - Buat folder `cli-agent/skills/<name>/SKILL.md` berisi frontmatter YAML `name` & `description` + body `instructions`.
- Method `get_openai_tools() -> list[dict]`:
  - Ekspose 2 tool ringkas untuk agen:
    1. `search_skills(query: str = "")` — mencari skill lokal/global yang tersedia.
    2. `create_skill(name: str, description: str, instructions: str)` — membuat skill baru di `cli-agent/skills/` (wajib konfirmasi kecuali `yolo`).

#### B. Buat 2 Skill Bawaan di `cli-agent/skills/`
1. `cli-agent/skills/code-review/SKILL.md`: instruksi review bug, keamanan kredensial, dan kebersihan kode.
2. `cli-agent/skills/web-research/SKILL.md`: instruksi riset web ringkas memakai MCP `fetch` atau `playwright-headless`.

### 3. Perintah Verifikasi Sprint 3
```powershell
py -c "import sys; sys.path.insert(0, 'cli-agent'); import config; from skills_manager import SkillManager; sm = SkillManager(config.CLI_DIR / 'skills', config.REPO_ROOT); skills = sm.scan_skills(); print('Total skills ditemukan:', len(skills)); print('Contoh 5 skill:', list(skills.keys())[:5]); print('code-review ada:', 'code-review' in skills)"
```
**Kriteria Lulus:** Mendeteksi skill lokal (`code-review`, `web-research`) sekaligus skill global dari `~/.agents/skills` (total > 2) tanpa error.

---

## 🔧 SPRINT 4: `/goal`, `/loop`, `/schedule` (Cross-Platform) & `--once` Mode

### 1. Masalah Logika yang Dicegah
- Di `/goal`: jika percakapan panjang dan `_trim_history_if_needed()` berjalan, instruksi tujuan awal (`[ACTIVE GOAL]`) tidak boleh ikut terhapus agar model 3B/7B tetap fokus.
- Di `/loop`: setiap iterasi harus memakai context baru (reset history, hanya bawa ringkasan hasil iterasi sebelumnya maksimal 500 karakter) agar context `8192` tidak penuh.
- Di `--once` (headless scheduler): jika `llama-server` sudah berjalan di port `8081` (`server_mgr.is_healthy()`), **reuse server tersebut** dan **JANGAN matikan** saat `--once` selesai! Jika belum berjalan, nyalakan lalu matikan saat selesai. Default safety mode pada `--once` adalah `read-only` (kecuali argumen `--auto-approve` atau `--yolo` diberikan).

### 2. Spesifikasi File Eksak

#### A. Buat `cli-agent/scheduler.py`
Class `TaskScheduler`:
- **In-App Scheduler:**
  - `add_in_app(self, name: str, interval_seconds: int, prompt: str, callback)`: jalankan daemon thread timer berulang setiap `interval_seconds` selama CLI berjalan, catat log ke `cli-agent/logs/schedule.log`.
  - `list_in_app()`, `remove_in_app(name)`.
- **OS-Level Cross-Platform Scheduler:**
  - `parse_interval_or_time(spec: str) -> dict`: dukung format ringkas seperti `5m`, `1h`, `daily 08:00`.
  - `register_os_task(self, name: str, spec: str, prompt: str, workspace: str, safety_flag: str = "") -> str`:
    - Buat command target: `py "<main.py>" --once "<prompt>" --workspace "<workspace>" {safety_flag}`.
    - **Windows (`sys.platform == "win32"`):** Jalankan `schtasks /Create /F /TN "LensetekAgent_<name>" ...` (`/SC MINUTE /MO <N>` atau `/SC DAILY /ST <HH:MM>`).
    - **Linux / macOS (`sys.platform != "win32"`):** Baca `crontab -l` (abaikan error jika kosong), tambahkan baris cron + komentar `# lensetek-agent:<name>`, tulis kembali via `crontab -`.
  - `list_os_tasks() -> str`:
    - Windows: `schtasks /Query /FO LIST` filter `LensetekAgent_`.
    - Linux/Mac: `crontab -l` filter `lensetek-agent:`.
  - `remove_os_task(name: str) -> str`:
    - Windows: `schtasks /Delete /F /TN "LensetekAgent_<name>"`.
    - Linux/Mac: hapus baris dengan `# lensetek-agent:<name>` dari `crontab`.

#### B. Update `cli-agent/agent.py`
1. Integrasikan `SkillManager` (tambahkan tools `search_skills` dan `create_skill` ke `_get_all_tools()` dan `_execute_tool()`).
2. Tambahkan `active_goal: str | None = None`:
   - Di `_trim_history_if_needed()`: pertahankan index 0 (`system`), dan jika `self.active_goal` aktif, pastikan pesan index 1 (`[ACTIVE GOAL]: ...`) **tidak pernah terhapus**; hapus mulai dari index 2 ke atas.
3. Tambahkan `run_goal(self, goal_text: str, max_steps: int = 20, on_status=None, on_tool=None) -> str`:
   - Set `self.active_goal = goal_text`, sisipkan pesan pinned `[ACTIVE GOAL] Selesaikan target ini langkah demi langkah dan verifikasi hasilnya sebelum menjawab selesai: {goal_text}`.
   - Jalankan `run_turn(..., max_steps=max_steps)` (tambahkan parameter opsional `max_steps: int = 8` di `run_turn`).
   - Bersihkan `self.active_goal = None` setelah selesai.
4. Tambahkan `run_loop(self, count_or_interval: str, prompt_text: str, on_status=None, on_tool=None, on_iteration=None)`:
   - Parse `count_or_interval`: jika berakhiran `x` (misal `3x`), ulangi tepat N kali. Jika berakhiran `s`/`m`/`h` (misal `30s`, `5m`), ulangi berjadwal hingga `KeyboardInterrupt`.
   - Di setiap iterasi: panggil `self.reset_session()`, bawa ringkasan singkat hasil iterasi sebelumnya (maks 400 char), lalu jalankan `run_turn(prompt_text)`.

#### C. Update `cli-agent/main.py`
1. Ubah banner menjadi: **`⚡ LENSETEK LEAN AGENT (MCP Orchestrator)`**.
2. Tambah argumen CLI:
   - `--auto-approve`: mode auto-approve di dalam workspace aktif.
   - `--yolo`: mode tanpa konfirmasi sama sekali.
   - `--once PROMPT`: jalankan 1 prompt secara headless lalu keluar (default `read-only` kecuali `--auto-approve` atau `--yolo` ikut dipasang).
3. Logika `--once`:
   - Cek apakah `server_mgr.is_healthy()` sudah `True` sebelum `start()`. Jika sudah menyala, set `started_by_us = False` (jangan di-`stop()` di blok `finally`).
4. Tambah / update Slash Commands di loop interaktif:
   - `/auto-approve`: aktifkan mode auto-approve (dalam workspace).
   - `/yolo`: aktifkan mode yolo (tanpa konfirmasi).
   - `/strict`: kembali ke mode konfirmasi penuh.
   - `/skills [filter]`: tampilkan daftar skill lokal & global yang ditemukan `SkillManager`.
   - `/skill create <nama> | <deskripsi>`: minta agen membuatkan `SKILL.md` baru.
   - `/<nama-skill> [tugas]`: jika `<nama-skill>` cocok dengan skill yang ada di `SkillManager`, suntikkan isi `SKILL.md` tersebut ke `run_turn`.
   - `/mcp` / `/mcp install <nama> [command args...]` / `/mcp test <nama>` / `/mcp remove <nama>` / `/mcp enable <nama>` / `/mcp disable <nama>`.
   - `/goal <target>`: jalankan `agent.run_goal(...)`.
   - `/loop <3x|30s|5m> <tugas>`: jalankan `agent.run_loop(...)`.
   - `/schedule add <in-app|os> <nama> <5m|1h|daily 08:00> <prompt>` / `/schedule list` / `/schedule remove <nama>`.

### 3. Perintah Verifikasi Sprint 4 (End-to-End Check)
1. Kompilasi seluruh file Python di `cli-agent/`:
```powershell
py -m py_compile cli-agent/config.py cli-agent/server_manager.py cli-agent/tools_fs.py cli-agent/mcp_client.py cli-agent/skills_manager.py cli-agent/scheduler.py cli-agent/agent.py cli-agent/main.py
```
2. Uji CLI `--help` menampilkan argumen baru (`--auto-approve`, `--yolo`, `--once`):
```powershell
py cli-agent/main.py --help
```
3. Uji `SkillManager` dan `TaskScheduler` parse interval:
```powershell
py -c "import sys; sys.path.insert(0, 'cli-agent'); from scheduler import TaskScheduler; ts = TaskScheduler(); print(ts.parse_interval_or_time('5m')); print(ts.parse_interval_or_time('daily 08:30'))"
```
4. Pastikan file edge computing di root **tidak berubah**:
```powershell
git status --short
```
**Kriteria Lulus:** `py_compile` exit code 0, `--help` menampilkan flag `--auto-approve`, `--yolo`, dan `--once`, `TaskScheduler` mem-parse `5m` dan `daily 08:30` tanpa error, serta tidak ada perubahan pada file root (`app.py`, `start.bat`, `rag_engine.py`, `safety_guard.py`).
