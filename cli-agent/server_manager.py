import os
import sys
import time
import atexit
import weakref
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

from config import (
    REPO_ROOT,
    LLAMA_SERVER_EXE,
    find_llama_server_binary,
    download_llama_server_binary,
    DEFAULT_PORT,
    DEFAULT_CTX,
    DEFAULT_THREADS,
    DEFAULT_KV_CACHE
)

class LlamaServerManager:
    def __init__(self, port: int = DEFAULT_PORT, ctx_size: int = DEFAULT_CTX, threads: int = DEFAULT_THREADS):
        self.port = port
        self.ctx_size = ctx_size
        self.threads = threads
        self.process = None
        self.model_name = None
        self.active_loras = []
        self.base_url = f"http://127.0.0.1:{self.port}"
        self_ref = weakref.ref(self)
        atexit.register(lambda: self_ref() and self_ref().stop())

    def is_healthy(self) -> bool:
        """Memeriksa apakah llama-server sedang aktif dan merespons /health."""
        try:
            req = urllib.request.Request(f"{self.base_url}/health")
            with urllib.request.urlopen(req, timeout=1) as resp:
                return resp.status == 200
        except Exception:
            return False

    def start(self, model_name: str, loras: list[dict] | None = None):
        """Menjalankan llama-server dengan profil hemat RAM Ryzen 3 serta dukungan Multi-LoRA."""
        norm_loras = []
        for item in (loras or []):
            lp = Path(str(item.get("path", ""))).resolve()
            if lp.is_file() and lp.exists():
                norm_loras.append({"path": str(lp), "scale": float(item.get("scale", 1.0))})
        server_exe = find_llama_server_binary()
        if not server_exe or not server_exe.exists():
            print("\n[i] Binary llama-server tidak terdeteksi. Memulai unduhan otomatis runtime...")
            ok, msg, downloaded = download_llama_server_binary()
            if ok and downloaded and downloaded.exists():
                server_exe = downloaded
                print(f"[✓] {msg}\n")
            else:
                raise FileNotFoundError(f"Binary llama-server tidak ditemukan di: {LLAMA_SERVER_EXE}. {msg}")

        # Cari model di absolute path, REPO_ROOT, atau folder models/
        raw_path = Path(model_name)
        if raw_path.is_absolute() and raw_path.exists():
            model_path = raw_path
        elif (REPO_ROOT / model_name).exists():
            model_path = REPO_ROOT / model_name
        elif (REPO_ROOT / "models" / model_name).exists():
            model_path = REPO_ROOT / "models" / model_name
        elif raw_path.exists():
            model_path = raw_path.resolve()
        else:
            raise FileNotFoundError(f"Model '{model_name}' tidak ditemukan di REPO_ROOT maupun path kustom.")

        # Jika sudah berjalan dengan model & LoRA yang sama dan sehat, tidak perlu restart
        if self.process and self.process.poll() is None and self.model_name == model_name and self.active_loras == norm_loras:
            if self.is_healthy():
                return

        # Hentikan proses sebelumnya jika ada
        self.stop()

        cmd = [
            str(server_exe),
            "-m", str(model_path),
            "--host", "127.0.0.1",
            "--port", str(self.port),
            "-c", str(self.ctx_size),
            "--jinja",
            "-ctk", DEFAULT_KV_CACHE,
            "-ctv", DEFAULT_KV_CACHE,
            "-t", str(self.threads),
            "-fa", "auto",
            "--temp", "0.4"
        ]
        for l_item in norm_loras:
            scale = l_item.get("scale", 1.0)
            if abs(scale - 1.0) < 1e-6:
                cmd.extend(["--lora", l_item["path"]])
            else:
                cmd.extend(["--lora-scaled", f"{l_item['path']}:{scale:.2f}"])

        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags
        )
        self.model_name = model_name
        self.active_loras = norm_loras

        # Polling /health hingga maksimal 30 detik
        started = False
        for _ in range(60):
            time.sleep(0.5)
            if self.is_healthy():
                started = True
                break
            if self.process.poll() is not None:
                break

        if not started:
            self.stop()
            raise RuntimeError(f"Gagal memulai llama-server untuk model {model_name} pada port {self.port}")

    def stop(self):
        """Menghentikan proses llama-server yang dikelola secara aman."""
        if self.process:
            try:
                if self.process.poll() is None:
                    self.process.terminate()
                    try:
                        self.process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        self.process.kill()
            except Exception:
                pass
            finally:
                self.process = None
                self.model_name = None
