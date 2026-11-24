"""
Lensetek WebUI & Workspace Editor Backend
Zero-dependency lightweight HTTP server providing:
- Responsive Mobile-First Web Dashboard
- Workspace File Explorer & Inline Code Editor
- Secure Workspace-Jailed File Operations with Credential Protection
- Proxy to local llama-server (127.0.0.1:8081)
"""

from __future__ import annotations

import json
import os
import threading
import urllib.parse
import urllib.request
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict, Optional

WEBUI_DIR = Path(__file__).resolve().parent
STATIC_DIR = WEBUI_DIR / "static"
DEFAULT_WEBUI_PORT = 3001

# Daftar file dan direktori sensitif yang DILARANG diakses melalui WebUI
SENSITIVE_PATTERNS = {
    ".env", ".env.local", ".env.production", ".env.development",
    ".git", ".gitmodules", "id_rsa", "id_ecdsa", "id_ed25519"
}

def is_safe_path(rel_path_str: str, root: Path) -> tuple[bool, Path | None, str]:
    """Memvalidasi keamanan path agar tetap di dalam workspace dan tidak mengakses credential."""
    clean_rel = rel_path_str.strip().lstrip("/\\")
    if not clean_rel:
        return False, None, "Path tidak boleh kosong."

    # Cek sensitivitas nama
    parts = Path(clean_rel).parts
    for part in parts:
        part_lower = part.lower()
        if part_lower in SENSITIVE_PATTERNS or part_lower.startswith(".env") or part_lower.endswith(".key") or part_lower.endswith(".pem"):
            return False, None, f"Akses ditolak: File/folder '{part}' dilindungi oleh sistem keamanan kredensial."

    try:
        resolved = (root / clean_rel).resolve()
        if not str(resolved).startswith(str(root.resolve())):
            return False, None, "Akses ditolak: Percobaan path traversal di luar folder workspace."
        return True, resolved, ""
    except Exception as e:
        return False, None, f"Error validasi path: {e}"

class WebUIHandler(SimpleHTTPRequestHandler):
    workspace_root: Path = Path.cwd()
    llama_port: int = 8081

    def end_headers(self):
        # Tambahkan header CORS dan security lokal
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # 1. API: Status
        if path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            data = {
                "status": "online",
                "workspace": str(self.workspace_root),
                "llama_port": self.llama_port
            }
            self.wfile.write(json.dumps(data).encode("utf-8"))
            return

        # 2. API: File List
        if path == "/api/files":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            tree = []
            try:
                for item in sorted(self.workspace_root.rglob("*")):
                    # Skip file rahasia dan .git
                    parts = item.relative_to(self.workspace_root).parts
                    if any(p.startswith(".git") or p.startswith(".env") or p.endswith(".pyc") or p == "__pycache__" for p in parts):
                        continue
                    if item.is_file():
                        tree.append({
                            "path": str(item.relative_to(self.workspace_root)).replace("\\", "/"),
                            "name": item.name,
                            "size": item.stat().st_size
                        })
            except Exception as e:
                tree = [{"error": str(e)}]
            self.wfile.write(json.dumps({"files": tree}).encode("utf-8"))
            return

        # 3. API: Read File
        if path == "/api/file":
            rel_p = query.get("path", [""])[0]
            safe, target_file, msg = is_safe_path(rel_p, self.workspace_root)
            if not safe or not target_file:
                self.send_response(403)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"error": msg}).encode("utf-8"))
                return

            if not target_file.exists() or not target_file.is_file():
                self.send_response(404)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "File tidak ditemukan."}).encode("utf-8"))
                return

            try:
                with open(target_file, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "path": rel_p,
                    "content": content,
                    "size": target_file.stat().st_size
                }).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"error": f"Gagal membaca file: {e}"}).encode("utf-8"))
            return

        # 4. Static Files (SPA)
        if path in ("/", "/index.html"):
            index_path = STATIC_DIR / "index.html"
            if index_path.exists():
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                with open(index_path, "rb") as f:
                    self.wfile.write(f.read())
                return

        super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length > 0 else b"{}"

        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception:
            payload = {}

        # 1. API: Write / Edit File
        if path == "/api/file":
            rel_p = payload.get("path", "")
            content = payload.get("content", "")
            safe, target_file, msg = is_safe_path(rel_p, self.workspace_root)
            if not safe or not target_file:
                self.send_response(403)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"error": msg}).encode("utf-8"))
                return

            try:
                target_file.parent.mkdir(parents=True, exist_ok=True)
                with open(target_file, "w", encoding="utf-8") as f:
                    f.write(content)
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": True,
                    "path": rel_p,
                    "bytes_written": len(content.encode("utf-8"))
                }).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"error": f"Gagal menyimpan file: {e}"}).encode("utf-8"))
            return

        # 2. API: Proxy Chat to Local Llama-Server
        if path == "/api/chat":
            llama_url = f"http://127.0.0.1:{self.llama_port}/v1/chat/completions"
            try:
                req = urllib.request.Request(
                    llama_url,
                    data=body,
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=120) as resp:
                    resp_data = resp.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(resp_data)
            except Exception as e:
                self.send_response(502)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"error": f"Gagal menghubungi llama-server: {e}"}).encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()

server_instance: Optional[HTTPServer] = None
server_thread: Optional[threading.Thread] = None

def start_webui_server(workspace: Path, port: int = DEFAULT_WEBUI_PORT, llama_port: int = 8081) -> str:
    """Menjalankan server WebUI di thread background."""
    global server_instance, server_thread

    if server_instance:
        return f"http://127.0.0.1:{port}"

    class CustomHandler(WebUIHandler):
        workspace_root = workspace
        llama_port = llama_port

    server_instance = HTTPServer(("127.0.0.1", port), CustomHandler)
    server_thread = threading.Thread(target=server_instance.serve_forever, daemon=True)
    server_thread.start()
    url = f"http://127.0.0.1:{port}"
    print(f"\n[✓] Lensetek WebUI running at: {url} (Workspace: {workspace})\n")
    return url

def stop_webui_server() -> None:
    """Menghentikan server WebUI."""
    global server_instance
    if server_instance:
        server_instance.shutdown()
        server_instance.server_close()
        server_instance = None

def on_load(context: Dict[str, Any]) -> bool:
    """Lifecycle hook: dijalankan saat plugin diaktifkan."""
    workspace = Path(context.get("workspace", "."))
    start_webui_server(workspace)
    return True

def on_unload(context: Dict[str, Any]) -> None:
    """Lifecycle hook: dijalankan saat plugin dinonaktifkan."""
    stop_webui_server()

if __name__ == "__main__":
    start_webui_server(Path.cwd())
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop_webui_server()
