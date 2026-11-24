import os
import sys
import json
import time
import urllib.request
import urllib.error
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

USER_AGENT = "lensetek-agent-harness/1.0 (https://lensetek.com)"

def get_repo_size_summary(repo_id: str) -> str:
    """
    Mengambil ringkasan ukuran model GGUF dari repositori Hugging Face dalam format GB.
    Mendeteksi varian kuantisasi standar (Q4) dan rentang min-max file.
    Contoh output: '1.80 GB' atau '~6.6 GB (Q4) [3.9-22.2 GB]'.
    """
    clean_repo = repo_id.strip()
    url = f"https://huggingface.co/api/models/{clean_repo}/tree/main"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=6) as resp:
            items = json.loads(resp.read().decode("utf-8"))
            model_files = []
            for it in items:
                p = it.get("path", "")
                sz = it.get("size", 0)
                if p.lower().endswith(".gguf") and not p.lower().startswith("mmproj-") and sz > 0:
                    model_files.append((p, sz))
            if not model_files:
                return "N/A"

            # Filter berkas non-shard (prioritaskan single file)
            single_files = [f for f in model_files if "-of-" not in f[0].lower()]
            files_to_use = single_files if single_files else model_files
            files_to_use.sort(key=lambda x: x[1])

            min_sz = files_to_use[0][1] / (1024 * 1024 * 1024)
            max_sz = files_to_use[-1][1] / (1024 * 1024 * 1024)

            # Cari quant Q4 (standar rekomendasi edge LLM)
            q4_file = None
            for pattern in ["q4_k_m", "q4_0", "q4_k_s", "q4_1", "q4"]:
                for f in files_to_use:
                    if pattern in f[0].lower():
                        q4_file = f
                        break
                if q4_file:
                    break

            if len(files_to_use) == 1:
                return f"{min_sz:.2f} GB"
            elif q4_file:
                q4_gb = q4_file[1] / (1024 * 1024 * 1024)
                if abs(min_sz - max_sz) > 0.3:
                    return f"~{q4_gb:.1f} GB (Q4) [{min_sz:.1f}-{max_sz:.1f} GB]"
                else:
                    return f"{q4_gb:.2f} GB"
            else:
                return f"{min_sz:.1f}-{max_sz:.1f} GB"
    except Exception:
        return "N/A"

def search_hf_gguf_models(query: str, limit: int = 10, fetch_sizes: bool = True) -> list[dict]:
    """
    Mencari model GGUF di Hugging Face Hub menggunakan API resmi (seperti llama.cpp).
    Mengembalikan daftar dictionary: [{id, downloads, likes, lastModified, size_display}, ...]
    """
    clean_query = query.strip()
    encoded = urllib.parse.quote(clean_query)
    url = f"https://huggingface.co/api/models?search={encoded}&filter=gguf&sort=downloads&direction=-1&limit={limit}"
    
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            results = []
            for item in data:
                results.append({
                    "id": item.get("id", ""),
                    "downloads": item.get("downloads", 0),
                    "likes": item.get("likes", 0),
                    "lastModified": item.get("lastModified", "")[:10] if item.get("lastModified") else "",
                    "size_display": "N/A"
                })

            if fetch_sizes and results:
                def _attach_size(item):
                    try:
                        item["size_display"] = get_repo_size_summary(item["id"])
                    except Exception:
                        item["size_display"] = "N/A"
                    return item

                with ThreadPoolExecutor(max_workers=min(10, len(results))) as ex:
                    results = list(ex.map(_attach_size, results))

            return results
    except Exception as e:
        print(f"\033[31m[ERROR] Gagal mencari di Hugging Face Hub: {e}\033[0m")
        return []

def list_hf_gguf_files(repo_id: str) -> list[dict]:
    """
    Mengambil daftar file *.gguf dari repositori Hugging Face.
    Mengembalikan: [{path, size, size_display}, ...]
    """
    clean_repo = repo_id.strip()
    url = f"https://huggingface.co/api/models/{clean_repo}/tree/main"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            gguf_files = []
            for item in data:
                path = item.get("path", "")
                if path.lower().endswith(".gguf") and not path.lower().startswith("mmproj-"):
                    sz = item.get("size", 0)
                    if sz > (1024 ** 3):
                        sz_disp = f"{sz / (1024 ** 3):.2f} GB"
                    else:
                        sz_disp = f"{sz / (1024 ** 2):.1f} MB"
                    gguf_files.append({
                        "path": path,
                        "size": sz,
                        "size_display": sz_disp
                    })
            return gguf_files
    except Exception as e:
        print(f"\033[31m[ERROR] Gagal membaca file repo '{repo_id}': {e}\033[0m")
        return []

def download_hf_gguf_file(repo_id: str, filename: str, target_dir: Path, lang: str = "en") -> tuple[bool, str, Path | None]:
    """
    Mengunduh file GGUF dari Hugging Face dengan visual progress bar.
    URL: https://huggingface.co/{repo_id}/resolve/main/{filename}
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    out_file = target_dir / filename
    part_file = target_dir / f"{filename}.part"

    if out_file.exists() and out_file.stat().st_size > 10 * 1024 * 1024:
        msg = f"File already exists: {out_file.name} ({out_file.stat().st_size / (1024**3):.2f} GB)"
        return True, msg, out_file

    url = f"https://huggingface.co/{repo_id}/resolve/main/{filename}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    if lang == "id":
        lbl_downloading = "Mengunduh"
        lbl_done = "Selesai diunduh:"
        lbl_cancelled = "Pengunduhan dibatalkan oleh pengguna."
        lbl_failed = "Gagal mengunduh:"
    elif lang == "cn":
        lbl_downloading = "正在下载"
        lbl_done = "下载完成:"
        lbl_cancelled = "用户取消了下载。"
        lbl_failed = "下载失败:"
    else:
        lbl_downloading = "Downloading"
        lbl_done = "Download complete:"
        lbl_cancelled = "Download cancelled by user."
        lbl_failed = "Download failed:"

    print(f"\n\033[36m[*] {lbl_downloading} {filename} from {repo_id}...\033[0m")
    print(f"\033[2m    Source: {url}\033[0m")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            total_bytes = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            chunk_size = 1024 * 1024  # 1MB per chunk
            start_time = time.time()

            with open(part_file, "wb") as f_out:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f_out.write(chunk)
                    downloaded += len(chunk)

                    elapsed = max(0.1, time.time() - start_time)
                    speed_mb = (downloaded / (1024 * 1024)) / elapsed

                    if total_bytes > 0:
                        pct = (downloaded / total_bytes) * 100
                        mb_down = downloaded / (1024 * 1024)
                        mb_tot = total_bytes / (1024 * 1024)
                        bar_len = 24
                        filled = int(bar_len * downloaded / total_bytes)
                        bar = "=" * filled + ">" + " " * (bar_len - filled - 1) if filled < bar_len else "=" * bar_len
                        sys.stdout.write(f"\r\033[36m[{bar[:bar_len]}]\033[0m {pct:5.1f}% ({mb_down:6.1f}/{mb_tot:6.1f} MB) at {speed_mb:4.1f} MB/s ")
                        sys.stdout.flush()
                    else:
                        mb_down = downloaded / (1024 * 1024)
                        sys.stdout.write(f"\rDownloaded {mb_down:.1f} MB at {speed_mb:.1f} MB/s ")
                        sys.stdout.flush()

            print()

        if part_file.exists():
            if out_file.exists():
                out_file.unlink()
            part_file.rename(out_file)

        return True, f"{lbl_done} {out_file.name}", out_file

    except KeyboardInterrupt:
        print(f"\n\033[33m[!] {lbl_cancelled}\033[0m")
        if part_file.exists():
            try:
                part_file.unlink()
            except Exception:
                pass
        return False, lbl_cancelled, None
    except Exception as e:
        print(f"\n\033[31m[ERROR] {lbl_failed} {e}\033[0m")
        if part_file.exists():
            try:
                part_file.unlink()
            except Exception:
                pass
        return False, str(e), None
