"""
Lensetek Local LLM Agent Harness - Version & Update Manager
Handles version tracking, changelogs, startup update checks, in-app updating, and restart.
"""
from __future__ import annotations
import io
import os
import sys
import json
import shutil
import zipfile
import tempfile
import subprocess
import threading
import urllib.request
from pathlib import Path

APP_VERSION = "0.3.1"
APP_NAME = "Lensetek Local LLM Agent Harness"
RELEASE_DATE = "2026-11-25"
GITHUB_RAW_VERSION_URL = "https://raw.githubusercontent.com/lensetek-int/local-agent-harness/main/cli-agent/version.json"
GITHUB_API_COMMIT_URL = "https://api.github.com/repos/lensetek-int/local-agent-harness/commits/main"
GITHUB_ARCHIVE_ZIP_URL = "https://github.com/lensetek-int/local-agent-harness/archive/refs/heads/main.zip"

CHANGELOG: dict[str, list[str]] = {
    "0.3.1": [
        "WebUI Cancel & Full Slash Commands: Real-time Cancel button (/api/cancel) plus /goal, /loop, /session, /mcp, /schedule, /ctx, /workspace, and /update in WebUI",
        "Multi-Part & Resume GGUF Downloader: 6x parallel HTTP Range downloads with automatic resume from .part state",
        "Self-Healing Installer & Safe Uninstall: Auto-stop locked llama-server/WebUI processes in install.ps1/install.sh and added lensetek --uninstall",
        "Non-Git Update Fallback: HTTP/ZIP fallback for lensetek --update when .git or git CLI is absent",
        "WebUI Socket & Port Stability: Prevented hung CloseWait HTTP/1.1 sockets and auto-reclaimed port 3001"
    ],
    "0.3.0": [
        "On-Demand Plugin System: Extensible modular architecture via /plugins with pagination & search",
        "Official WebUI Plugin: Local responsive dashboard & workspace file editor (mobile-first)",
        "Playwright Dynamic Research: Headless Chromium web scraper optimized for 3B SLM context windows",
        "Plugin Contributor Blueprint & Maker Skill: Template scaffolding & /plugins create command",
        "External Model Registration: Register models from any directory/drive via /model add <path>",
        "Safe Model Deletion: Delete local GGUF models and reclaim disk space via /model remove <id>",
        "Installer Runtime Auto-Download: Automated official llama-server CPU binary fetch on install"
    ],
    "0.2.0": [
        "Hugging Face Hub model search & direct download (/model search)",
        "Reasoning & thinking effort depth adjustment (/effort off|low|medium|high)",
        "Automated startup update check, /update command, and auto-restart",
        "Full multilingual interface (English, Bahasa Indonesia, 简体中文) via /language",
        "Headless web search integration with multi-engine fallback (/search)"
    ],
    "0.1.0": [
        "Initial release of Lensetek Local LLM Agent Harness",
        "Autonomous multi-turn agent with /goal, /loop, and /schedule modes",
        "Built-in llama.cpp server lifecycle management",
        "Local workspace file tools with safety sandbox modes"
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

def _parse_ver_tuple(v: str) -> tuple[int, ...]:
    parts = []
    for seg in str(v).strip().lstrip("v").split("."):
        digits = "".join(ch for ch in seg if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def _check_updates_via_http(repo_root: Path, info: dict, timeout_sec: float) -> dict:
    """Fallback update check via GitHub raw version.json + commits API for ZIP-based installs."""
    info["method"] = "archive"
    headers = {"User-Agent": "LensetekAgent/2.0"}
    remote_ver = APP_VERSION
    remote_whats_new = []

    req_v = urllib.request.Request(GITHUB_RAW_VERSION_URL, headers=headers)
    with urllib.request.urlopen(req_v, timeout=timeout_sec) as resp:
        v_data = json.loads(resp.read().decode("utf-8"))
        remote_ver = str(v_data.get("version", APP_VERSION))
        remote_whats_new = v_data.get("changelog", {}).get(remote_ver, [])

    remote_sha = ""
    commit_msg = ""
    try:
        req_c = urllib.request.Request(GITHUB_API_COMMIT_URL, headers=headers)
        with urllib.request.urlopen(req_c, timeout=timeout_sec) as resp_c:
            c_data = json.loads(resp_c.read().decode("utf-8"))
            remote_sha = str(c_data.get("sha", ""))[:7]
            commit_msg = str(c_data.get("commit", {}).get("message", "")).splitlines()[0]
    except Exception:
        pass

    commit_file = repo_root / ".lensetek-commit"
    local_sha = commit_file.read_text(encoding="utf-8").strip() if commit_file.exists() else ""

    ver_newer = _parse_ver_tuple(remote_ver) > _parse_ver_tuple(APP_VERSION)
    sha_newer = bool(remote_sha and local_sha and remote_sha != local_sha)

    info["checked"] = True
    info["update_available"] = ver_newer or sha_newer
    info["latest_version"] = remote_ver if ver_newer else (f"{APP_VERSION}+{remote_sha}" if sha_newer else APP_VERSION)
    if remote_whats_new and ver_newer:
        info["whats_new"] = remote_whats_new
    elif commit_msg and sha_newer:
        info["whats_new"] = [f"[{remote_sha}] {commit_msg}"]
        info["commit_logs"] = info["whats_new"]
    else:
        info["whats_new"] = get_whats_new(APP_VERSION)
    return info


def _perform_zip_update(repo_root: Path, timeout_sec: float = 45.0) -> tuple[bool, str]:
    """Download main.zip from GitHub and overlay updated code while preserving user settings/data."""
    headers = {"User-Agent": "LensetekAgent/2.0"}
    req = urllib.request.Request(GITHUB_ARCHIVE_ZIP_URL, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
        zip_bytes = resp.read()

    # Preserve user_settings.json if present
    settings_path = repo_root / "cli-agent" / "user_settings.json"
    saved_settings = settings_path.read_bytes() if settings_path.exists() else None

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            zf.extractall(tmp_path)

        extracted_roots = [p for p in tmp_path.iterdir() if p.is_dir()]
        if not extracted_roots:
            return False, "Arsip update kosong atau tidak valid."
        src_root = extracted_roots[0]

        for folder_name in ("cli-agent", "plugins"):
            src_sub = src_root / folder_name
            dst_sub = repo_root / folder_name
            if src_sub.exists():
                shutil.copytree(src_sub, dst_sub, dirs_exist_ok=True)

        for top_file in ("install.ps1", "install.sh", "README.md"):
            src_f = src_root / top_file
            if src_f.exists():
                shutil.copy2(src_f, repo_root / top_file)

    if saved_settings is not None:
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_bytes(saved_settings)

    try:
        req_c = urllib.request.Request(GITHUB_API_COMMIT_URL, headers=headers)
        with urllib.request.urlopen(req_c, timeout=5.0) as resp_c:
            c_data = json.loads(resp_c.read().decode("utf-8"))
            sha = str(c_data.get("sha", ""))[:7]
            if sha:
                (repo_root / ".lensetek-commit").write_text(sha, encoding="utf-8")
    except Exception:
        pass

    global _CACHED_UPDATE_INFO
    _CACHED_UPDATE_INFO = None
    return True, "Aplikasi berhasil diperbarui ke versi terbaru (ZIP)."


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

        repo_root = Path(__file__).resolve().parent.parent
        git_bin = shutil.which("git")
        if not git_bin or not (repo_root / ".git").exists():
            try:
                _check_updates_via_http(repo_root, info, timeout_sec)
            except Exception as exc:
                info["error"] = f"Update check failed: {exc}"
            _CACHED_UPDATE_INFO = info
            return info

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
    Menerapkan pembaruan dari remote git ke repositori lokal,
    atau fallback otomatis ke unduhan ZIP GitHub jika tidak memakai git.
    """
    repo_root = Path(__file__).resolve().parent.parent
    git_bin = shutil.which("git")
    if not git_bin or not (repo_root / ".git").exists():
        try:
            return _perform_zip_update(repo_root)
        except Exception as e:
            return False, f"Terjadi kesalahan saat memperbarui via ZIP: {e}"

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
