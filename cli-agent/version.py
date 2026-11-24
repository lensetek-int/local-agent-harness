"""
Lensetek Local LLM Agent Harness - Version & Update Manager
Handles version tracking, changelogs, startup update checks, in-app updating, and restart.
"""
from __future__ import annotations
import os
import sys
import json
import shutil
import subprocess
import threading
from pathlib import Path

APP_VERSION = "0.2.0"
APP_NAME = "Lensetek Local LLM Agent Harness"
RELEASE_DATE = "2026-11-24"

CHANGELOG: dict[str, list[str]] = {
    "0.2.0": [
        "Model Search: Cari dan unduh model GGUF langsung dari Hugging Face Hub (/model search)",
        "Thinking Effort: Atur kedalaman berpikir model (off, low, medium, high) secara interaktif (/effort)",
        "Update Manager: Otomatisasi cek update saat startup, perintah /update, dan restart mandiri",
        "Trilingual Support: Pilihan bahasa dinamis (English, Bahasa Indonesia, 简体中文) via /language",
        "Web Search: Integrasi pencarian web headless terpadu (/search)"
    ],
    "0.1.0": [
        "Rilis perdana Lensetek Local LLM Agent Harness",
        "Mode agen otonom multi-langkah (/goal, /loop, /schedule)",
        "Manajemen siklus hidup server llama.cpp lokal otomatis",
        "Integrasi client Model Context Protocol (MCP) dan skill kustom"
    ]
}

# Cache check result in memory so multiple checks in a single session don't re-fetch unnecessarily
_CACHED_UPDATE_INFO: dict | None = None
_CHECK_LOCK = threading.Lock()

def get_current_version() -> str:
    return APP_VERSION

def get_whats_new(version: str | None = None) -> list[str]:
    v = version or APP_VERSION
    return CHANGELOG.get(v, CHANGELOG.get(APP_VERSION, []))

def check_for_updates(timeout_sec: float = 3.0, force_refresh: bool = False) -> dict:
    """
    Memeriksa pembaruan dari repositori upstream (github/main atau origin/main).
    Mengembalikan status pembaruan, versi terbaru, dan ringkasan What's New.
    """
    global _CACHED_UPDATE_INFO
    if _CACHED_UPDATE_INFO and not force_refresh:
        return _CACHED_UPDATE_INFO

    with _CHECK_LOCK:
        if _CACHED_UPDATE_INFO and not force_refresh:
            return _CACHED_UPDATE_INFO

        info = {
            "checked": False,
            "update_available": False,
            "current_version": APP_VERSION,
            "latest_version": APP_VERSION,
            "behind_count": 0,
            "whats_new": get_whats_new(APP_VERSION),
            "commit_logs": [],
            "method": "git",
            "error": None
        }

        git_bin = shutil.which("git")
        if not git_bin:
            info["error"] = "Git executable not found in PATH."
            info["method"] = "none"
            _CACHED_UPDATE_INFO = info
            return info

        repo_root = Path(__file__).resolve().parent.parent

        try:
            env = os.environ.copy()
            env["GIT_TERMINAL_PROMPT"] = "0"

            # 1. Fetch metadata quietly
            fetch_res = subprocess.run(
                [git_bin, "fetch", "github", "main", "--quiet"],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                env=env
            )
            if fetch_res.returncode != 0:
                subprocess.run(
                    [git_bin, "fetch", "origin", "main", "--quiet"],
                    cwd=str(repo_root),
                    capture_output=True,
                    text=True,
                    timeout=timeout_sec,
                    env=env
                )

            # 2. Determine target upstream remote
            target_remote = "github/main"
            check_rev = subprocess.run(
                [git_bin, "rev-parse", "--verify", target_remote],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                timeout=2.0
            )
            if check_rev.returncode != 0:
                target_remote = "origin/main"

            # 3. Check commit count difference
            count_res = subprocess.run(
                [git_bin, "rev-list", f"HEAD..{target_remote}", "--count"],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                timeout=2.0
            )

            behind_count = 0
            if count_res.returncode == 0 and count_res.stdout.strip().isdigit():
                behind_count = int(count_res.stdout.strip())

            info["behind_count"] = behind_count
            info["checked"] = True

            if behind_count > 0:
                info["update_available"] = True

                # Get commit logs
                log_res = subprocess.run(
                    [git_bin, "log", f"HEAD..{target_remote}", "--oneline", "-n", "8"],
                    cwd=str(repo_root),
                    capture_output=True,
                    text=True,
                    timeout=2.0
                )
                commit_logs = [line.strip() for line in log_res.stdout.splitlines() if line.strip()]
                info["commit_logs"] = commit_logs

                # Try reading remote version.json
                remote_ver = APP_VERSION
                remote_whats_new = []
                show_v = subprocess.run(
                    [git_bin, "show", f"{target_remote}:cli-agent/version.json"],
                    cwd=str(repo_root),
                    capture_output=True,
                    text=True,
                    timeout=2.0
                )
                if show_v.returncode == 0 and show_v.stdout.strip():
                    try:
                        v_data = json.loads(show_v.stdout)
                        remote_ver = v_data.get("version", APP_VERSION)
                        remote_whats_new = v_data.get("changelog", {}).get(remote_ver, [])
                    except Exception:
                        pass

                info["latest_version"] = remote_ver if remote_ver != APP_VERSION else f"{APP_VERSION}+{behind_count}"
                info["whats_new"] = remote_whats_new if remote_whats_new else commit_logs
            else:
                info["update_available"] = False
                info["latest_version"] = APP_VERSION
                info["whats_new"] = get_whats_new(APP_VERSION)

        except subprocess.TimeoutExpired:
            info["error"] = "Update check timed out."
        except Exception as e:
            info["error"] = str(e)

        _CACHED_UPDATE_INFO = info
        return info

def perform_update() -> tuple[bool, str]:
    """
    Menerapkan pembaruan dari remote git ke repositori lokal.
    Aman terhadap modifikasi lokal (stash & pop bila diperlukan).
    """
    git_bin = shutil.which("git")
    if not git_bin:
        return False, "Git tidak ditemukan di sistem."

    repo_root = Path(__file__).resolve().parent.parent

    try:
        status_res = subprocess.run(
            [git_bin, "status", "--porcelain"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=5.0
        )
        is_dirty = bool(status_res.stdout.strip())

        stashed = False
        if is_dirty:
            stash_res = subprocess.run(
                [git_bin, "stash", "push", "-m", "lensetek-auto-update-stash"],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                timeout=10.0
            )
            stashed = stash_res.returncode == 0

        # Pull updates
        pull_res = subprocess.run(
            [git_bin, "pull", "--ff-only", "github", "main"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=25.0
        )
        if pull_res.returncode != 0:
            pull_res = subprocess.run(
                [git_bin, "pull", "--ff-only", "origin", "main"],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                timeout=25.0
            )

        if stashed:
            subprocess.run(
                [git_bin, "stash", "pop"],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                timeout=10.0
            )

        if pull_res.returncode == 0:
            global _CACHED_UPDATE_INFO
            _CACHED_UPDATE_INFO = None
            return True, "Aplikasi berhasil diperbarui ke versi terbaru."
        else:
            return False, f"Git pull gagal: {pull_res.stderr.strip() or pull_res.stdout.strip()}"

    except Exception as e:
        return False, f"Terjadi kesalahan saat memperbarui: {e}"

def restart_application():
    """
    Merestart aplikasi CLI agent secara bersih menggunakan Python interpreter saat ini.
    """
    try:
        import time
        time.sleep(0.5)
        sys.stdout.flush()
        sys.stderr.flush()
        
        python_exe = sys.executable
        args = [python_exe] + sys.argv
        
        subprocess.Popen(args)
        sys.exit(0)
    except Exception as e:
        print(f"\n[!] Gagal restart otomatis: {e}. Silakan jalankan ulang aplikasi secara manual.")
        sys.exit(0)
