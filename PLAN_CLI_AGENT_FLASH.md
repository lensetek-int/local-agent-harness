# ⚡ PLAN EKSEKUSI ATOMIK — GEMINI 3.8 FLASH (MEDIUM)
## Membangun `cli-agent/` (Lean CLI Agent Harness + MCP Client ala Pi) dalam 1 Repo `local-llm`

> **Petunjuk Penggunaan untuk Agen (Gemini 3.8 Flash Medium):**
> Dokumen ini adalah *blueprint eksekusi deterministik* untuk membangun folder baru `cli-agent/` di dalam repo `local-llm`.
>
> **Aturan Emas (WAJIB DIPATUHI):**
> 1. **Gunakan `py`** (bukan `python`) untuk semua perintah Python di Windows PowerShell.
> 2. **DILARANG mengubah file edge computing default** di root repo (`app.py`, `start.bat`, `rag_engine.py`, `safety_guard.py`, `requirements.txt`). Semua kode baru harus berada di dalam folder `cli-agent/`.
> 3. **Gunakan Python Standard Library saja** (`json`, `os`, `sys`, `time`, `shutil`, `subprocess`, `pathlib`, `urllib.request`, `urllib.error`, `threading`, `argparse`, `re`) agar tidak memerlukan instalasi paket tambahan yang rawan gagal.
> 4. **DILARANG** melakukan hardcode API key, password, token, atau kredensial apa pun.
> 5. **WAJIB** jalankan **Perintah Verifikasi** di akhir setiap Sprint sebelum lanjut ke Sprint berikutnya.

---

## 📋 Peta 4 Sprint Atomik

| Sprint | Judul Pekerjaan | File Target | Tujuan Utama |
| :---: | :--- | :--- | :--- |
| **Sprint 1** | Konfigurasi & `llama-server` Manager | `cli-agent/config.py`, `cli-agent/mcp_servers.json`, `cli-agent/server_manager.py` | Menjalankan `..\bin\llama-server.exe` dengan profil hemat RAM Ryzen 3 (`-c 8192`, `--jinja`, `-ctk q8_0 -ctv q8_0`, `-t 4`) tanpa mengganggu `app.py`. |
| **Sprint 2** | File & Shell Tools + Safety Gate | `cli-agent/tools_fs.py` | 5 tool ringkas (`list_dir`, `search_files`, `read_file`, `write_or_edit_file`, `run_command`) yang aman untuk project maupun seluruh isi laptop. |
| **Sprint 3** | MCP Stdio Client & Output Trimmer | `cli-agent/mcp_client.py` | Client JSON-RPC 2.0 `stdio` untuk `chrome-devtools-mcp` / MCP lain dengan *lazy loading* (hemat token) dan pemotong output besar. |
| **Sprint 4** | Lean Agent Loop, TUI CLI & Launcher | `cli-agent/agent.py`, `cli-agent/main.py`, `cli-agent/run_agent.bat` | Loop agen dengan fallback parser `<tool_call>`, tampilan CLI ala Pi (status bar `tokens/ctx`), slash commands, dan launcher `.bat`. |

---

## 🔧 SPRINT 1: Konfigurasi & `llama-server` Manager

### 1. Masalah Logika yang Dicegah
- `app.py` menggunakan port `8080` (atau `LLAMA_PORT` di `.env.local`) dan `-c 4096`. `cli-agent` harus memakai port default **`8081`** agar tidak bentrok jika dijalankan bersamaan, serta wajib menyertakan **`--jinja`** agar *function calling* bekerja.
- Lokasi eksekusi user bisa di root repo atau di dalam `cli-agent/`. Semua path ke `bin\llama-server.exe` dan file `.gguf` wajib dihitung relatif terhadap `Path(__file__).resolve().parent.parent` (`REPO_ROOT`).

### 2. Spesifikasi File Eksak

#### A. `cli-agent/mcp_servers.json`
Buat file JSON berisi konfigurasi default MCP server (tanpa kredensial):
```json
{
  "chrome-devtools": {
    "command": "npx",
    "args": ["-y", "chrome-devtools-mcp@latest"],
    "enabled": true,
    "description": "Kontrol browser Chrome, inspect DOM, console, network, dan screenshot"
  },
  "filesystem": {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-filesystem", "."],
    "enabled": false,
    "description": "MCP filesystem standar (opsional, sudah ada tools_fs bawaan)"
  }
}
```

#### B. `cli-agent/config.py`
Konstanta dan helper konfigurasi:
- `CLI_DIR = Path(__file__).resolve().parent`
- `REPO_ROOT = CLI_DIR.parent`
- `LLAMA_SERVER_EXE = REPO_ROOT / "bin" / ("llama-server.exe" if sys.platform == "win32" else "llama-server")`
- `DEFAULT_PORT = 8081`
- `DEFAULT_CTX = 8192` (opsi yang didukung: `8192`, `16384`)
- `DEFAULT_THREADS = min(4, os.cpu_count() or 4)` (optimal untuk physical cores Ryzen 3 5300U)
- `DEFAULT_KV_CACHE = "q8_0"`
- Fungsi `list_gguf_models() -> list[str]`: mengembalikan daftar nama file `*.gguf` di `REPO_ROOT` (kecuali file `mmproj-*.gguf`).
- Fungsi `pick_default_model() -> str | None`: prioritaskan `lensetek-edge-loop-3b-q4_k_m.gguf` jika ada, jika tidak ambil model pertama dari `list_gguf_models()`.
- Fungsi `load_mcp_config() -> dict`: membaca `CLI_DIR / "mcp_servers.json"`.

#### C. `cli-agent/server_manager.py`
Class `LlamaServerManager`:
- `__init__(self, port=DEFAULT_PORT, ctx_size=DEFAULT_CTX, threads=DEFAULT_THREADS)`: simpan state `process = None`, `model_name = None`, `base_url = f"http://127.0.0.1:{port}"`.
- `is_healthy(self) -> bool`: `GET {base_url}/health` timeout 1 detik, return `True` jika HTTP 200.
- `start(self, model_name: str)`:
  - Pastikan `LLAMA_SERVER_EXE.exists()`.
  - Jika sudah running dengan `model_name` yang sama dan `is_healthy()`, langsung return.
  - Jika ada proses sebelumnya (`self.process`), panggil `self.stop()` terlebih dahulu (JANGAN `taskkill /IM llama-server.exe` secara global agar tidak mematikan server milik `app.py`, cukup `self.process.terminate()` / `kill()`).
  - Susun command:
    ```python
    cmd = [
        str(LLAMA_SERVER_EXE),
        "-m", str(REPO_ROOT / model_name),
        "--host", "127.0.0.1",
        "--port", str(self.port),
        "-c", str(self.ctx_size),
        "--jinja",
        "-ctk", DEFAULT_KV_CACHE,
        "-ctv", DEFAULT_KV_CACHE,
        "-t", str(self.threads),
        "-fa", "auto",
        "--temp", "0.4",
    ]
    ```
  - Jalankan `subprocess.Popen` dengan `stdout=subprocess.DEVNULL`, `stderr=subprocess.DEVNULL` (dan `CREATE_NO_WINDOW` di Windows).
  - Polling `/health` maksimal 30 detik (interval 0.5 detik) sampai `is_healthy()` bernilai `True`. Jika gagal, raise `RuntimeError`.
- `stop(self)`: terminate proses jika masih hidup dan set `self.process = None`.

### 3. Perintah Verifikasi Sprint 1
```powershell
py -c "import sys; sys.path.insert(0, 'cli-agent'); import config, server_manager; print('Models:', config.list_gguf_models()); print('Default:', config.pick_default_model()); print('MCP:', list(config.load_mcp_config().keys()))"
```
**Kriteria Lulus:** Menampilkan daftar `.gguf`, model default, dan `['chrome-devtools', 'filesystem']` tanpa error.

---

## 🔧 SPRINT 2: File & Shell Tools + Safety Gate (`cli-agent/tools_fs.py`)

### 1. Masalah Logika yang Dicegah
- Model 3B/7B akan gagal atau lambat jika `list_dir` memuntahkan ribuan file `node_modules` atau `.git`. Harus ada skip-list folder sampah dan batas maksimal entri.
- Untuk mengelola "seluruh isi laptop" dengan aman, operasi baca diizinkan langsung, sedangkan `write_or_edit_file` dan `run_command` **WAJIB** meminta konfirmasi user `[y/N]` melalui callback `confirm_fn(prompt_text) -> bool`.
- `read_file` tidak boleh membaca file biner atau file 5000 baris sekaligus. Batasi maksimal **150 baris** per panggilan dan potong baris > 300 karakter.

### 2. Spesifikasi File Eksak (`cli-agent/tools_fs.py`)
Buat class `LocalWorkspaceTools`:
- `__init__(self, workspace_root: str, confirm_fn=None)`
  - `self.workspace_root = Path(workspace_root).resolve()`
  - `self.confirm_fn = confirm_fn` (default meminta `input(f"{msg} [y/N]: ").strip().lower() == "y"`).
- Helper `_resolve_path(self, raw_path: str) -> Path`:
  - Jika `raw_path` absolut (misal `C:\Users\ACER\Documents`), gunakan langsung `.resolve()`.
  - Jika relatif, gabungkan dengan `self.workspace_root`.
- **5 Core Tools** (skema OpenAI JSON ringkas disediakan via method `get_openai_tools() -> list[dict]`):
  1. `list_dir(path=".")`:
     - Skip folder: `{".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".next"}`.
     - Tampilkan `[DIR] nama/` dan `[FILE] nama (ukuran)`, maksimal 80 item. Jika lebih, beri catatan `"... (terpotong, gunakan search_files)"`.
  2. `search_files(query: str, root_path: str = ".")`:
     - Cari nama file yang cocok ATAU teks di dalam file teks (`.py`, `.js`, `.ts`, `.md`, `.json`, `.txt`, `.html`, `.css`, `.bat`, `.yml`).
     - Jika `shutil.which("rg")` tersedia, gunakan `rg -n --max-count 5 --max-filesize 512K <query> <root>` (timeout 10 detik, batasi output 40 baris). Jika tidak ada `rg`, fallback ke `os.walk` Python (maksimal 30 kecocokan, skip folder sampah).
  3. `read_file(path: str, start_line: int = 1, end_line: int = 120)`:
     - Validasi file ada dan bukan biner (cek null bytes di 1024 byte pertama).
     - Batasi `end_line - start_line <= 150`.
     - Format output dengan nomor baris: `12: isi baris` (maks 300 char/baris).
  4. `write_or_edit_file(path: str, mode: str, content: str, target: str = "")`:
     - `mode` hanya boleh `"write"` (buat/timpa file) atau `"edit"` (ganti string eksak `target` dengan `content`).
     - Untuk `mode == "edit"`, jika `target` tidak ditemukan di file, kembalikan pesan error yang jelas agar model bisa memperbaikinya.
     - **Wajib panggil `confirm_fn`** sebelum menulis ke disk. Jika ditolak user, return `"Dibatalkan oleh pengguna."`.
  5. `run_command(command: str, cwd: str = ".")`:
     - Blokir pola destruktif fatal (`format `, `rm -rf /`, `del /s /q c:\`, `rd /s /q c:\`).
     - **Wajib panggil `confirm_fn`** sebelum menjalankan command.
     - Jalankan via `subprocess.run(["powershell", "-NoProfile", "-Command", command], cwd=resolved_cwd, capture_output=True, text=True, timeout=30)`.
     - Potong gabungan stdout+stderr maksimal **3000 karakter**.
- Method `execute(self, name: str, args: dict) -> str`: dispatcher aman dengan `try/except` sehingga error tool selalu mengembalikan string error informatif (tidak membuat program crash).

### 3. Perintah Verifikasi Sprint 2
```powershell
py -c "import sys; sys.path.insert(0, 'cli-agent'); from tools_fs import LocalWorkspaceTools; t = LocalWorkspaceTools('.', confirm_fn=lambda m: False); print('Tools:', [x['function']['name'] for x in t.get_openai_tools()]); print(t.execute('list_dir', {'path': '.'})[:300])"
```
**Kriteria Lulus:** Menampilkan 5 nama tool (`list_dir`, `search_files`, `read_file`, `write_or_edit_file`, `run_command`) dan daftar isi direktori repo tanpa crash.

---

## 🔧 SPRINT 3: MCP Stdio Client & Output Trimmer (`cli-agent/mcp_client.py`)

### 1. Masalah Logika yang Dicegah
- Di Windows, `npx` sebenarnya adalah `npx.cmd`. Memanggil `subprocess.Popen(["npx", ...])` tanpa `shutil.which("npx")` akan melempar `FileNotFoundError: [WinError 2]`. **Wajib** resolve executable dengan `shutil.which(cmd)`.
- MCP seperti `chrome-devtools-mcp` memiliki >20 tool dan bisa mengembalikan DOM snapshot atau base64 screenshot puluhan ribu karakter. Jika masuk utuh ke context `8192`, `llama-server` akan meledak.
- Solusi **Lazy Tool Loading**: Hanya ekspos **2 meta-tool** ke LLM (`mcp_list_tools` dan `mcp_call`) + lakukan *output trimming* (hapus data base64 panjang & potong teks maksimal 3500 karakter).

### 2. Spesifikasi File Eksak (`cli-agent/mcp_client.py`)
Buat class `MCPStdioClient` dan `MCPManager`:
- `MCPStdioClient(name: str, command: str, args: list[str], env: dict | None = None)`:
  - `start()`:
    - Resolve binary: `exe = shutil.which(self.command) or self.command`.
    - Jalankan `subprocess.Popen([exe, *self.args], stdin=PIPE, stdout=PIPE, stderr=PIPE, text=True, encoding="utf-8", errors="replace", bufsize=1)`.
    - Kirim JSON-RPC `initialize` (`protocolVersion: "2024-11-05"`, `capabilities: {}`, `clientInfo: {"name": "local-llm-cli", "version": "1.0.0"}`).
    - Baca respons baris per baris (dengan timeout 20 detik menggunakan thread/queue agar tidak deadlock jika server lambat start atau `npx` sedang mengunduh package).
    - Kirim notifikasi `notifications/initialized`.
  - `list_tools() -> list[dict]`: kirim `tools/list`, cache hasilnya di `self.tools_cache`.
  - `call_tool(tool_name: str, arguments: dict) -> str`: kirim `tools/call` (timeout 45 detik), gabungkan `result.content` (jika `type == "image"`, ganti menjadi `"[Image data omitted to save context]"`), dan potong teks maksimal **3500 karakter**.
  - `close()`: tutup `stdin`, terminate proses dengan aman.
- `MCPManager(config_dict: dict, confirm_fn=None)`:
  - `get_openai_tools() -> list[dict]`: mengembalikan 2 skema tool ringkas:
    1. `mcp_list_tools(server_name: str)` — daftar server yang tersedia ditulis di deskripsi tool (misal: `chrome-devtools`).
    2. `mcp_call(server_name: str, tool_name: str, arguments: dict)` — memanggil tool MCP spesifik. Memanggil `confirm_fn` sebelum eksekusi aksi MCP (opsional/aktif default untuk keamanan).
  - `execute(name: str, args: dict) -> str`: lazy-start server saat pertama kali dipanggil, lalu jalankan `list_tools` (format ringkas: `- nama_tool: deskripsi singkat (required: [param1, param2])`) atau `call_tool`.
  - `close_all()`: matikan semua MCP server yang aktif saat CLI keluar.

### 3. Perintah Verifikasi Sprint 3
```powershell
py -c "import sys; sys.path.insert(0, 'cli-agent'); import config; from mcp_client import MCPManager; m = MCPManager(config.load_mcp_config()); print('Meta tools:', [x['function']['name'] for x in m.get_openai_tools()]); m.close_all()"
```
**Kriteria Lulus:** Menampilkan `['mcp_list_tools', 'mcp_call']` tanpa error. *(Catatan: Uji koneksi live `npx chrome-devtools-mcp` dilakukan opsional saat runtime manual agar verifikasi unit tidak tergantung jaringan npm).*

---

## 🔧 SPRINT 4: Lean Agent Loop, TUI CLI ala Pi & Launcher

### 1. Masalah Logika yang Dicegah
- Beberapa model GGUF kecil (terutama saat prompt panjang atau streaming) terkadang mengembalikan `tool_calls` dalam format OpenAI JSON standar, **atau** menuliskan tag teks `<tool_call>{"name": "...", "arguments": {...}}</tool_call>` di dalam `content`. `agent.py` **WAJIB** mendukung kedua cara parsing tersebut agar model `lensetek-edge-loop-3b` dan `Qwen2.5-Coder-7B` sama-sama berjalan mulus.
- Jika percakapan memanjang mendekati batas `-c 8192`, `agent.py` harus otomatis memangkas (*sliding window*) pesan lama sambil mempertahankan `system` prompt dan pesan user terakhir.
- Tambahkan indikator loading (`Memproses prompt...`) di terminal agar pengguna tahu CPU sedang bekerja saat *prompt eval* berlangsung (tidak mengira program *hang*).

### 2. Spesifikasi File Eksak

#### A. `cli-agent/agent.py`
Buat class `LeanAgent`:
- System prompt super ringkas (< 250 kata) dalam Bahasa Indonesia/Inggris yang jelas:
  - Menjelaskan peran sebagai asisten coding & pengelola file/browser lokal.
  - Menginstruksikan: gunakan `list_dir` / `search_files` / `read_file` terlebih dahulu sebelum mengedit; untuk tugas browser/MCP, panggil `mcp_list_tools` dulu untuk melihat nama tool yang tersedia sebelum `mcp_call`.
- Method `run_turn(self, user_text: str, on_status=None, on_tool=None) -> str`:
  - Tambahkan pesan user ke `self.messages`.
  - Loop maksimal `max_steps = 8` per turn:
    1. Panggil `_trim_history_if_needed()` jika estimasi/usage token > 80% dari `ctx_size`.
    2. Kirim request HTTP `POST {base_url}/v1/chat/completions` (`stream=False`, `timeout=300`) berisi `messages` dan `tools` (gabungan 5 tool FS + 2 tool MCP = 7 tool).
    3. Ambil `usage` (`prompt_tokens`, `total_tokens`) untuk ditampilkan di status bar UI.
    4. Cek `message.get("tool_calls")`. Jika kosong, jalankan regex fallback `_parse_xml_tool_calls(content)` untuk menangkap pola `<tool_call>...</tool_call>`.
    5. Jika tidak ada tool call, simpan jawaban asisten ke `self.messages` dan kembalikan `content` final.
    6. Jika ada tool call: eksekusi masing-masing tool lewat `fs_tools.execute` atau `mcp_manager.execute`, tambahkan hasilnya sebagai `role: "tool"` ke `self.messages`, lalu lanjut iterasi berikutnya.

#### B. `cli-agent/main.py`
Terminal UI interaktif ala Pi:
- Mendukung argumen CLI: `--workspace` (default `.`), `--model`, `--ctx` (default `8192`), `--port` (default `8081`), `--no-server` (jika user sudah menyalakan `llama-server` sendiri).
- Mendukung ANSI color terminal Windows (`os.system("")` agar warna ANSI aktif di Windows CMD/PowerShell).
- Menampilkan **Header** saat startup (Model aktif, Workspace aktif, Context `8192`, daftar MCP enabled).
- Menampilkan **Status Bar** sebelum prompt input, mirip gaya Pi:
  `[workspace_path] | tokens: {last_tokens}/{ctx_size} ({pct:.1f}%) | model: {model_name}`
- Mendukung **Slash Commands**:
  - `/help` — tampilkan daftar perintah.
  - `/workspace <path>` — ganti folder kerja aktif (bisa ke project lain atau `C:\Users\ACER`).
  - `/model` — pilih ulang file `.gguf` dan restart `llama-server`.
  - `/ctx <8192|16384>` — ubah ukuran context dan restart `llama-server`.
  - `/mcp` — tampilkan status server MCP & toggle on/off.
  - `/clear` — bersihkan riwayat chat.
  - `/exit` — hentikan `llama-server` & semua MCP server, lalu keluar bersih.

#### C. `cli-agent/run_agent.bat`
Launcher Windows 1-klik:
```bat
@echo off
title Local-LLM CLI Agent
cd /d "%~dp0"
py main.py %*
pause
```

### 3. Perintah Verifikasi Sprint 4 (End-to-End Check)
1. Cek kompilasi sintaks seluruh file di `cli-agent/`:
```powershell
py -m py_compile cli-agent/config.py cli-agent/server_manager.py cli-agent/tools_fs.py cli-agent/mcp_client.py cli-agent/agent.py cli-agent/main.py
```
2. Uji help CLI tanpa menyalakan server:
```powershell
py cli-agent/main.py --help
```
3. Pastikan file edge computing di root **tidak berubah**:
```powershell
git status --short
```
**Kriteria Lulus:** `py_compile` keluar dengan exit code 0, `--help` menampilkan opsi CLI dengan benar, dan `git status` menunjukkan hanya folder `cli-agent/` (serta file plan ini) yang baru ditambahkan.
