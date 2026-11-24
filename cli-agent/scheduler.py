import os
import sys
import time
import shutil
import threading
import subprocess
from pathlib import Path
from datetime import datetime

class TaskScheduler:
    def __init__(self, log_dir: Path = None):
        self.log_dir = Path(log_dir).resolve() if log_dir else Path(__file__).resolve().parent / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / "schedule.log"
        self.in_app_tasks = {}

    def log(self, message: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{timestamp}] {message}\n"
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(entry)
        except Exception:
            pass

    @staticmethod
    def parse_interval_or_time(spec: str) -> dict:
        """Mem-parse string spesifikasi waktu seperti '5m', '1h', '30s', atau 'daily 08:30'."""
        s = spec.strip().lower()
        if s.startswith("daily"):
            parts = s.split()
            time_str = parts[1] if len(parts) > 1 else "08:00"
            if ":" in time_str:
                h, m = time_str.split(":", 1)
                return {
                    "type": "daily",
                    "time": f"{int(h):02d}:{int(m):02d}",
                    "hour": int(h),
                    "minute": int(m),
                    "raw": spec
                }
            return {"type": "daily", "time": "08:00", "hour": 8, "minute": 0, "raw": spec}

        # Format interval (contoh: 30s, 5m, 1h)
        total_seconds = 0
        if s.endswith("s"):
            total_seconds = int(s[:-1])
        elif s.endswith("m"):
            total_seconds = int(s[:-1]) * 60
        elif s.endswith("h"):
            total_seconds = int(s[:-1]) * 3600
        elif s.isdigit():
            total_seconds = int(s) * 60
        else:
            total_seconds = 300  # Default 5 menit

        return {
            "type": "interval",
            "seconds": max(10, total_seconds),
            "minutes": max(1, total_seconds // 60),
            "raw": spec
        }

    # --- IN-APP SCHEDULER (Berjalan saat CLI aktif) ---

    def add_in_app(self, name: str, spec_str: str, prompt: str, callback):
        parsed = self.parse_interval_or_time(spec_str)
        interval_secs = parsed.get("seconds", 300)

        if name in self.in_app_tasks:
            self.remove_in_app(name)

        stop_event = threading.Event()

        def _worker():
            self.log(f"In-App Task '{name}' dimulai (interval: {interval_secs}s).")
            while not stop_event.is_set():
                # Tunggu interval atau sampai di-stop
                if stop_event.wait(interval_secs):
                    break
                try:
                    self.log(f"In-App Task '{name}' mengeksekusi prompt: {prompt}")
                    callback(prompt)
                except Exception as e:
                    self.log(f"In-App Task '{name}' error: {e}")

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        self.in_app_tasks[name] = {
            "name": name,
            "spec": spec_str,
            "prompt": prompt,
            "stop_event": stop_event,
            "thread": t
        }
        return f"Sukses menjadwalkan in-app task '{name}' setiap {interval_secs} detik."

    def list_in_app(self) -> list[dict]:
        return [
            {"name": v["name"], "spec": v["spec"], "prompt": v["prompt"]}
            for v in self.in_app_tasks.values()
        ]

    def remove_in_app(self, name: str) -> bool:
        if name in self.in_app_tasks:
            task = self.in_app_tasks[name]
            task["stop_event"].set()
            del self.in_app_tasks[name]
            self.log(f"In-App Task '{name}' dihentikan.")
            return True
        return False

    # --- OS-LEVEL SCHEDULER (Cross-Platform: Windows schtasks / Linux-Mac crontab) ---

    def register_os_task(self, name: str, spec: str, prompt: str, workspace: str, safety_flag: str = "") -> str:
        parsed = self.parse_interval_or_time(spec)
        main_py = Path(__file__).resolve().parent / "main.py"
        py_exe = sys.executable

        # Command runner
        # py main.py --once "<prompt>" --workspace "<ws>" {safety_flag}
        args_part = f'"{main_py}" --once "{prompt}" --workspace "{workspace}"'
        if safety_flag:
            args_part += f" {safety_flag}"

        if sys.platform == "win32":
            task_name = f"LensetekAgent_{name}"
            if parsed["type"] == "interval":
                minutes = max(1, parsed.get("minutes", 5))
                sc_args = ["/SC", "MINUTE", "/MO", str(minutes)]
            else:
                time_str = parsed.get("time", "08:00")
                sc_args = ["/SC", "DAILY", "/ST", time_str]

            cmd = [
                "schtasks", "/Create", "/F",
                "/TN", task_name,
                "/TR", f'"{py_exe}" {args_part}',
                *sc_args
            ]
            try:
                res = subprocess.run(cmd, capture_output=True, text=True)
                if res.returncode == 0:
                    return f"Sukses mendaftarkan Windows Task '{task_name}' ({spec}).\nCommand: schtasks /Run /TN {task_name}"
                return f"Gagal membuat Windows Task: {res.stderr or res.stdout}"
            except Exception as e:
                return f"Error eksekusi schtasks: {e}"

        else:
            # Linux / macOS (crontab)
            cron_tag = f"# lensetek-agent:{name}"
            if parsed["type"] == "interval":
                minutes = max(1, parsed.get("minutes", 5))
                cron_time = f"*/{minutes} * * * *"
            else:
                h = parsed.get("hour", 8)
                m = parsed.get("minute", 0)
                cron_time = f"{m} {h} * * *"

            cron_line = f'{cron_time} "{py_exe}" {args_part} >> "{self.log_file}" 2>&1 {cron_tag}\n'

            try:
                # Baca crontab saat ini
                current_cron = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
                lines = current_cron.stdout.splitlines() if current_cron.returncode == 0 else []
                # Hapus entri lama dengan tag yang sama
                lines = [l for l in lines if cron_tag not in l]
                lines.append(cron_line.strip())
                new_cron = "\n".join(lines) + "\n"

                res = subprocess.run(["crontab", "-"], input=new_cron, text=True, capture_output=True)
                if res.returncode == 0:
                    return f"Sukses mendaftarkan Cron Job '{name}' ({spec})."
                return f"Gagal memperbarui crontab: {res.stderr}"
            except Exception as e:
                return f"Error crontab: {e}"

    def list_os_tasks(self) -> str:
        if sys.platform == "win32":
            try:
                res = subprocess.run(["schtasks", "/Query", "/FO", "LIST"], capture_output=True, text=True)
                lines = res.stdout.splitlines()
                matching = []
                capture = False
                cur_block = []
                for line in lines:
                    if "LensetekAgent_" in line:
                        capture = True
                    if capture:
                        cur_block.append(line)
                        if not line.strip():
                            matching.extend(cur_block)
                            cur_block = []
                            capture = False
                if cur_block:
                    matching.extend(cur_block)
                return "\n".join(matching) if matching else "Tidak ada Windows Task 'LensetekAgent_' aktif."
            except Exception as e:
                return f"Error query schtasks: {e}"
        else:
            try:
                res = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
                if res.returncode != 0:
                    return "Crontab kosong atau tidak ditemukan."
                matching = [l for l in res.stdout.splitlines() if "lensetek-agent:" in l]
                return "\n".join(matching) if matching else "Tidak ada cron task lensetek-agent aktif."
            except Exception as e:
                return f"Error query crontab: {e}"

    def remove_os_task(self, name: str) -> str:
        if sys.platform == "win32":
            task_name = f"LensetekAgent_{name}"
            try:
                res = subprocess.run(["schtasks", "/Delete", "/F", "/TN", task_name], capture_output=True, text=True)
                if res.returncode == 0:
                    return f"Sukses menghapus Windows Task '{task_name}'."
                return f"Gagal menghapus Windows Task: {res.stderr or res.stdout}"
            except Exception as e:
                return f"Error delete schtasks: {e}"
        else:
            cron_tag = f"# lensetek-agent:{name}"
            try:
                current_cron = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
                if current_cron.returncode != 0:
                    return "Crontab kosong."
                lines = [l for l in current_cron.stdout.splitlines() if cron_tag not in l]
                new_cron = "\n".join(lines) + "\n"
                subprocess.run(["crontab", "-"], input=new_cron, text=True, capture_output=True)
                return f"Sukses menghapus Cron Job '{name}'."
            except Exception as e:
                return f"Error hapus crontab: {e}"
