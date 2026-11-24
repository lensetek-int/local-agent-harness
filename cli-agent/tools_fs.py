import os
import sys
import shutil
import subprocess
from pathlib import Path

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".next", ".turbo"}
TEXT_EXTS = {".py", ".js", ".ts", ".jsx", ".tsx", ".md", ".json", ".txt", ".html", ".css", ".bat", ".cmd", ".ps1", ".yml", ".yaml", ".env", ".toml", ".ini", ".sql"}

def default_confirm(prompt: str) -> bool:
    try:
        ans = input(f"\n⚠️  {prompt} [y/N]: ").strip().lower()
        return ans in ("y", "yes")
    except EOFError:
        return False

class LocalWorkspaceTools:
    def __init__(self, workspace_root: str = ".", confirm_fn=None, safety_mode: str = "strict"):
        self.workspace_root = Path(workspace_root).resolve()
        self.confirm_fn = confirm_fn if confirm_fn is not None else default_confirm
        self.safety_mode = safety_mode.strip().lower()

    def set_safety_mode(self, mode: str):
        mode = mode.strip().lower()
        if mode in ("strict", "auto-approve", "yolo", "read-only"):
            self.safety_mode = mode

    def _resolve_path(self, raw_path: str) -> Path:
        p = Path(raw_path.strip().strip('"').strip("'"))
        if p.is_absolute():
            return p.resolve()
        return (self.workspace_root / p).resolve()

    def _is_inside_workspace(self, path: Path) -> bool:
        try:
            path.resolve().relative_to(self.workspace_root.resolve())
            return True
        except (ValueError, Exception):
            return False

    def _needs_confirmation(self, target_path: Path = None) -> bool:
        if self.safety_mode == "yolo":
            return False
        if self.safety_mode == "read-only":
            return False
        if self.safety_mode == "auto-approve":
            if target_path and self._is_inside_workspace(target_path):
                return False
            return True
        return True

    def set_workspace(self, new_root: str):
        self.workspace_root = Path(new_root).resolve()

    def list_dir(self, path: str = ".") -> str:
        target = self._resolve_path(path)
        if not target.exists():
            return f"Error: Direktori '{path}' ({target}) tidak ditemukan."
        if not target.is_dir():
            return f"Error: '{path}' bukan sebuah direktori."

        items = []
        try:
            entries = sorted(list(target.iterdir()), key=lambda e: (not e.is_dir(), e.name.lower()))
            count = 0
            for entry in entries:
                if entry.name in SKIP_DIRS:
                    continue
                count += 1
                if count > 80:
                    items.append("... [Terpotong: lebih dari 80 item, gunakan search_files untuk mencari secara spesifik]")
                    break
                if entry.is_dir():
                    items.append(f"[DIR]  {entry.name}/")
                else:
                    try:
                        sz = entry.stat().st_size
                        if sz >= 1024 * 1024:
                            sz_str = f"{sz / (1024 * 1024):.1f} MB"
                        elif sz >= 1024:
                            sz_str = f"{sz / 1024:.1f} KB"
                        else:
                            sz_str = f"{sz} B"
                        items.append(f"[FILE] {entry.name} ({sz_str})")
                    except Exception:
                        items.append(f"[FILE] {entry.name}")
        except Exception as e:
            return f"Error membaca direktori: {e}"

        return "\n".join(items) if items else "(Direktori kosong)"

    def search_files(self, query: str, root_path: str = ".") -> str:
        root = self._resolve_path(root_path)
        if not root.exists():
            return f"Error: Direktori '{root_path}' tidak ditemukan."

        # Coba gunakan ripgrep (rg) jika tersedia
        rg_bin = shutil.which("rg")
        if rg_bin:
            try:
                cmd = [
                    rg_bin,
                    "-n",
                    "--max-count", "5",
                    "--max-filesize", "512K",
                    "--glob", "!{.git,node_modules,__pycache__}/*",
                    query,
                    str(root)
                ]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                lines = res.stdout.strip().splitlines()
                if lines and lines[0]:
                    out_lines = lines[:40]
                    if len(lines) > 40:
                        out_lines.append(f"... (total {len(lines)} baris cocok, dibatasi 40 baris teratas)")
                    return "\n".join(out_lines)
            except Exception:
                pass

        # Fallback ke python walk
        matches = []
        query_lower = query.lower()
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for f in filenames:
                full_p = Path(dirpath) / f
                try:
                    rel_p = str(full_p.relative_to(root))
                except Exception:
                    rel_p = str(full_p)
                # Cocokkan nama file
                if query_lower in f.lower():
                    matches.append(f"[MATCH NAMA FILE] {rel_p}")
                    if len(matches) >= 30:
                        break
                # Cocokkan isi file teks jika ekstensi teks
                if full_p.suffix.lower() in TEXT_EXTS:
                    try:
                        if full_p.stat().st_size <= 512 * 1024:
                            with open(full_p, "r", encoding="utf-8", errors="ignore") as fh:
                                for idx, line in enumerate(fh, start=1):
                                    if query_lower in line.lower():
                                        snippet = line.strip()[:100]
                                        matches.append(f"{rel_p}:{idx}: {snippet}")
                                        if len(matches) >= 30:
                                            break
                    except Exception:
                        pass
                if len(matches) >= 30:
                    break
            if len(matches) >= 30:
                matches.append("... [Pencarian dibatasi 30 kecocokan teratas]")
                break

        return "\n".join(matches) if matches else f"Tidak ditemukan kecocokan untuk: '{query}'"

    def read_file(self, path: str, start_line: int = 1, end_line: int = 120) -> str:
        target = self._resolve_path(path)
        if not target.exists():
            return f"Error: File '{path}' ({target}) tidak ditemukan."
        if not target.is_file():
            return f"Error: '{path}' bukan sebuah file."

        try:
            with open(target, "rb") as bf:
                chunk = bf.read(1024)
                if b"\x00" in chunk:
                    return f"Error: File '{path}' terdeteksi sebagai binary, tidak dapat dibaca sebagai teks."
        except Exception as e:
            return f"Error membaca header file: {e}"

        start_line = max(1, int(start_line))
        end_line = max(start_line, int(end_line))
        if end_line - start_line > 150:
            end_line = start_line + 150

        out = []
        try:
            with open(target, "r", encoding="utf-8", errors="replace") as f:
                for idx, line in enumerate(f, start=1):
                    if idx < start_line:
                        continue
                    if idx > end_line:
                        break
                    clean_line = line.rstrip("\r\n")
                    if len(clean_line) > 300:
                        clean_line = clean_line[:300] + "... [baris terpotong]"
                    out.append(f"{idx}: {clean_line}")
        except Exception as e:
            return f"Error membaca file: {e}"

        if not out:
            return f"File '{path}' tidak memiliki baris antara {start_line} dan {end_line}."
        return "\n".join(out)

    def write_or_edit_file(self, path: str, mode: str, content: str, target: str = "") -> str:
        if self.safety_mode == "read-only":
            return "Ditolak: Agent berjalan dalam mode read-only (headless default)."

        target_path = self._resolve_path(path)
        mode = mode.strip().lower()

        if mode not in ("write", "edit"):
            return "Error: mode harus 'write' (tulis ulang/buat file baru) atau 'edit' (ganti teks spesifik)."

        if mode == "write":
            # Strip accidental outer markdown code fences generated by small 3B models
            stripped = content.strip()
            if stripped.startswith("```") and stripped.endswith("```"):
                lines = stripped.splitlines()
                if len(lines) >= 2:
                    content = "\n".join(lines[1:-1]) + "\n"
            if self._needs_confirmation(target_path):
                action_desc = f"Membuat / menimpa file '{target_path}'"
                if not self.confirm_fn(f"Apakah Anda mengizinkan: {action_desc}?"):
                    return "Dibatalkan oleh pengguna."
            try:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                with open(target_path, "w", encoding="utf-8") as f:
                    f.write(content)
                return f"Sukses menulis {len(content)} karakter ke '{path}'."
            except Exception as e:
                return f"Error menulis file: {e}"

        elif mode == "edit":
            if not target_path.exists():
                return f"Error: File '{path}' tidak ditemukan untuk diedit."
            if not target:
                return "Error: 'target' string wajib diisi untuk mode 'edit'."

            try:
                with open(target_path, "r", encoding="utf-8", errors="replace") as f:
                    orig_content = f.read()

                if target not in orig_content:
                    return f"Error: Target teks tidak ditemukan di dalam '{path}'. Pastikan spasi, baris baru, dan karakter sama persis."

                if self._needs_confirmation(target_path):
                    action_desc = f"Mengubah file '{target_path}' (mengganti {len(target)} karakter dengan {len(content)} karakter)"
                    if not self.confirm_fn(f"Apakah Anda mengizinkan: {action_desc}?"):
                        return "Dibatalkan oleh pengguna."

                new_content = orig_content.replace(target, content, 1)
                with open(target_path, "w", encoding="utf-8") as f:
                    f.write(new_content)
                return f"Sukses memperbarui file '{path}'."
            except Exception as e:
                return f"Error mengedit file: {e}"

    def run_command(self, command: str, cwd: str = ".") -> str:
        if self.safety_mode == "read-only":
            return "Ditolak: Agent berjalan dalam mode read-only (headless default)."

        # Cek perintah terlarang destruktif fatal
        lowered = command.lower()
        blocked_keywords = ["format ", "rm -rf /", "del /s /q c:\\", "rd /s /q c:\\", "format c:"]
        for bk in blocked_keywords:
            if bk in lowered:
                return f"Error Keamanan: Perintah '{command}' diblokir karena berpotensi merusak sistem."

        resolved_cwd = self._resolve_path(cwd)
        if not resolved_cwd.exists() or not resolved_cwd.is_dir():
            resolved_cwd = self.workspace_root

        if self._needs_confirmation(resolved_cwd):
            action_desc = f"Eksekusi perintah terminal: `{command}` di direktori `{resolved_cwd}`"
            if not self.confirm_fn(f"Apakah Anda mengizinkan: {action_desc}?"):
                return "Dibatalkan oleh pengguna."

        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", command],
                cwd=resolved_cwd,
                capture_output=True,
                text=True,
                timeout=30
            )
            out = (res.stdout or "") + ("\n[STDERR]\n" + res.stderr if res.stderr else "")
            if not out.strip():
                return f"Perintah selesai dengan exit code {res.returncode} (tanpa output)."
            if len(out) > 3000:
                out = out[:3000] + "\n... [Output terpotong: melebihi 3000 karakter]"
            return out
        except subprocess.TimeoutExpired:
            return f"Error: Perintah `{command}` kehabisan waktu (timeout > 30 detik)."
        except Exception as e:
            return f"Error eksekusi perintah: {e}"

    def get_openai_tools(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "list_dir",
                    "description": "Melihat daftar folder dan file di dalam direktori project atau laptop.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Path relatif atau absolut (contoh: '.' atau 'C:/Users/ACER')"}
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_files",
                    "description": "Mencari file berdasarkan nama atau isi teks dengan cepat.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Kata kunci pencarian"},
                            "root_path": {"type": "string", "description": "Direktori awal pencarian (default: '.')"}
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Membaca potongan baris file teks dengan nomor baris (maksimal 150 baris per call).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Path file relatif atau absolut"},
                            "start_line": {"type": "integer", "description": "Nomor baris awal (default: 1)"},
                            "end_line": {"type": "integer", "description": "Nomor baris akhir (default: 120)"}
                        },
                        "required": ["path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "write_or_edit_file",
                    "description": "Menulis file baru / menimpa (mode='write') atau mengubah teks spesifik di file yang sudah ada (mode='edit').",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Path file relatif atau absolut"},
                            "mode": {"type": "string", "enum": ["write", "edit"], "description": "'write' untuk timpa/buat, 'edit' untuk ganti target"},
                            "content": {"type": "string", "description": "Konten baru atau teks pengganti"},
                            "target": {"type": "string", "description": "Teks eksak yang akan diganti jika mode='edit'"}
                        },
                        "required": ["path", "mode", "content"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "run_command",
                    "description": "Menjalankan perintah PowerShell / terminal lokal.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {"type": "string", "description": "Perintah shell yang akan dijalankan"},
                            "cwd": {"type": "string", "description": "Direktori kerja eksekusi (default: '.')"}
                        },
                        "required": ["command"]
                    }
                }
            }
        ]

    def execute(self, name: str, args: dict) -> str:
        try:
            if name == "list_dir":
                return self.list_dir(args.get("path", "."))
            elif name == "search_files":
                return self.search_files(args.get("query", ""), args.get("root_path", "."))
            elif name == "read_file":
                return self.read_file(args.get("path", ""), args.get("start_line", 1), args.get("end_line", 120))
            elif name == "write_or_edit_file":
                return self.write_or_edit_file(args.get("path", ""), args.get("mode", "write"), args.get("content", ""), args.get("target", ""))
            elif name == "run_command":
                return self.run_command(args.get("command", ""), args.get("cwd", "."))
            else:
                return f"Error: Tool '{name}' tidak dikenal."
        except Exception as e:
            return f"Error eksekusi tool '{name}': {str(e)}"

    def list_mentionable_files(self, max_files: int = 1000) -> list[dict]:
        """Return safe workspace relative file paths & sizes (BFS order) for '@' autocomplete."""
        from collections import deque

        sensitive_exts = {".pem", ".key", ".p12", ".pfx", ".crt", ".jks", ".keystore"}
        sensitive_kws = (".env", "secret", "credential", "password", "private_key", "id_rsa", "id_ed25519", "service_account", ".htpasswd", ".netrc", ".npmrc", ".pypirc")
        results = []
        root = self.workspace_root.resolve()
        if not root.exists():
            return results

        queue = deque([root])
        while queue and len(results) < max_files:
            cur_dir = queue.popleft()
            try:
                entries = sorted(list(cur_dir.iterdir()), key=lambda e: (e.is_dir(), e.name.lower()))
            except Exception:
                continue

            for entry in entries:
                low = entry.name.lower()
                if entry.is_dir():
                    if entry.name in SKIP_DIRS or low.startswith(".env"):
                        continue
                    queue.append(entry)
                else:
                    if low.startswith(".env") or any(k in low for k in sensitive_kws):
                        continue
                    if entry.suffix.lower() in sensitive_exts:
                        continue
                    try:
                        rel = str(entry.relative_to(root)).replace("\\", "/")
                        sz = entry.stat().st_size
                        if sz >= 1024 * 1024:
                            sz_str = f"{sz / (1024 * 1024):.1f} MB"
                        elif sz >= 1024:
                            sz_str = f"{sz / 1024:.1f} KB"
                        else:
                            sz_str = f"{sz} B"
                        results.append({"path": rel, "size": sz_str, "bytes": sz})
                        if len(results) >= max_files:
                            return results
                    except Exception:
                        continue
        return results
