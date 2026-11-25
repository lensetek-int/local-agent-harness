import os
import sys
import json
import time
import threading
import urllib.request
import urllib.error
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
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

def _probe_download(url: str, user_agent: str = USER_AGENT) -> tuple[int, bool]:
    """Probe URL with Range: bytes=0-0 to detect total size and HTTP Range support."""
    req = urllib.request.Request(url, headers={"User-Agent": user_agent, "Range": "bytes=0-0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        status = getattr(resp, "status", 200)
        content_range = resp.headers.get("Content-Range", "")
        accept_ranges = resp.headers.get("Accept-Ranges", "").lower()
        if status == 206 and "/" in content_range:
            total_str = content_range.split("/")[-1].strip()
            if total_str.isdigit():
                return int(total_str), True
        total_len = int(resp.headers.get("Content-Length", 0) or 0)
        return total_len, (accept_ranges == "bytes" and total_len > 0)


def download_file_parallel(
    url: str,
    out_file: Path,
    lbl_cancelled: str = "Download cancelled by user.",
    lbl_failed: str = "Download failed:",
    lbl_done: str = "Download complete:",
    user_agent: str = USER_AGENT,
    num_workers: int = 6,
    chunk_size: int = 4 * 1024 * 1024,
) -> tuple[bool, str, Path | None]:
    """
    Download a file using multi-part parallel HTTP Range requests with automatic resume.
    Falls back to single-stream download if the server does not support Range requests.
    """
    out_file = Path(out_file)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    part_file = out_file.parent / f"{out_file.name}.part"
    meta_file = out_file.parent / f"{out_file.name}.part.meta.json"

    try:
        total_bytes, supports_ranges = _probe_download(url, user_agent=user_agent)
    except KeyboardInterrupt:
        print(f"\n\033[33m[!] {lbl_cancelled}\033[0m")
        return False, lbl_cancelled, None
    except Exception as e:
        print(f"\n\033[31m[ERROR] {lbl_failed} {e}\033[0m")
        return False, str(e), None

    # Fallback to single-stream for small files or servers without Range support
    if not supports_ranges or total_bytes < 8 * 1024 * 1024:
        req = urllib.request.Request(url, headers={"User-Agent": user_agent})
        try:
            start_time = time.time()
            downloaded = 0
            with urllib.request.urlopen(req, timeout=30) as resp, open(part_file, "wb") as f_out:
                if total_bytes <= 0:
                    total_bytes = int(resp.headers.get("Content-Length", 0) or 0)
                while True:
                    chunk = resp.read(512 * 1024)
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
                        bar = "=" * filled + (">" if filled < bar_len else "") + " " * (bar_len - filled - (1 if filled < bar_len else 0))
                        sys.stdout.write(f"\r\033[36m[{bar}]\033[0m {pct:5.1f}% ({mb_down:6.1f}/{mb_tot:6.1f} MB) at {speed_mb:4.1f} MB/s ")
                    else:
                        sys.stdout.write(f"\rDownloaded {downloaded / (1024 * 1024):.1f} MB at {speed_mb:.1f} MB/s ")
                    sys.stdout.flush()
            print()
            if out_file.exists():
                out_file.unlink()
            part_file.rename(out_file)
            return True, f"{lbl_done} {out_file.name}", out_file
        except KeyboardInterrupt:
            print(f"\n\033[33m[!] {lbl_cancelled}\033[0m")
            return False, lbl_cancelled, None
        except Exception as e:
            print(f"\n\033[31m[ERROR] {lbl_failed} {e}\033[0m")
            return False, str(e), None

    # Multi-part + Resume state initialization
    num_chunks = (total_bytes + chunk_size - 1) // chunk_size
    completed_set: set[int] = set()

    if part_file.exists() and meta_file.exists():
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            if (
                meta.get("total_bytes") == total_bytes
                and meta.get("chunk_size") == chunk_size
                and part_file.stat().st_size == total_bytes
            ):
                completed_set = {int(i) for i in meta.get("completed", []) if 0 <= int(i) < num_chunks}
        except Exception:
            completed_set = set()

    if not part_file.exists() or part_file.stat().st_size != total_bytes:
        completed_set = set()
        with open(part_file, "wb") as f_init:
            f_init.truncate(total_bytes)
        meta_file.write_text(
            json.dumps({"url": url, "total_bytes": total_bytes, "chunk_size": chunk_size, "completed": []}),
            encoding="utf-8",
        )

    def _chunk_bounds(idx: int) -> tuple[int, int]:
        start = idx * chunk_size
        end = min(total_bytes - 1, start + chunk_size - 1)
        return start, end

    resumed_bytes = sum((_chunk_bounds(i)[1] - _chunk_bounds(i)[0] + 1) for i in completed_set)
    pending_indices = [i for i in range(num_chunks) if i not in completed_set]

    if resumed_bytes > 0:
        print(f"\033[33m[i] Resuming download: {resumed_bytes / (1024 * 1024):.1f}/{total_bytes / (1024 * 1024):.1f} MB already saved ({num_workers}x parallel)...\033[0m")
    else:
        print(f"\033[2m    Multi-part enabled: {num_workers} parallel connections ({num_chunks} chunks)\033[0m")

    stop_event = threading.Event()
    write_lock = threading.Lock()
    progress_lock = threading.Lock()
    session_bytes = 0
    start_time = time.time()
    last_print = 0.0

    def _render_progress(force: bool = False):
        nonlocal last_print
        now = time.time()
        if not force and (now - last_print) < 0.25:
            return
        last_print = now
        total_done = min(total_bytes, resumed_bytes + session_bytes)
        elapsed = max(0.1, now - start_time)
        speed_mb = (session_bytes / (1024 * 1024)) / elapsed
        pct = (total_done / total_bytes) * 100
        mb_down = total_done / (1024 * 1024)
        mb_tot = total_bytes / (1024 * 1024)
        bar_len = 24
        filled = int(bar_len * total_done / total_bytes)
        bar = "=" * filled + (">" if filled < bar_len else "") + " " * (bar_len - filled - (1 if filled < bar_len else 0))
        sys.stdout.write(f"\r\033[36m[{bar}]\033[0m {pct:5.1f}% ({mb_down:6.1f}/{mb_tot:6.1f} MB) @ {speed_mb:4.1f} MB/s ")
        sys.stdout.flush()

    f_part = open(part_file, "r+b")

    def _download_chunk(idx: int):
        nonlocal session_bytes
        c_start, c_end = _chunk_bounds(idx)
        expected_len = c_end - c_start + 1

        for attempt in range(3):
            if stop_event.is_set():
                return
            reported = 0
            try:
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": user_agent, "Range": f"bytes={c_start}-{c_end}"},
                )
                buf = bytearray()
                with urllib.request.urlopen(req, timeout=45) as resp:
                    while len(buf) < expected_len:
                        if stop_event.is_set():
                            return
                        block = resp.read(min(262144, expected_len - len(buf)))
                        if not block:
                            break
                        buf.extend(block)
                        with progress_lock:
                            session_bytes += len(block)
                            reported += len(block)
                            _render_progress()

                if len(buf) != expected_len:
                    raise IOError(f"Incomplete chunk {idx}: got {len(buf)}/{expected_len} bytes")

                with write_lock:
                    f_part.seek(c_start)
                    f_part.write(buf)
                    completed_set.add(idx)
                    if len(completed_set) % 4 == 0 or len(completed_set) == num_chunks:
                        meta_file.write_text(
                            json.dumps({
                                "url": url,
                                "total_bytes": total_bytes,
                                "chunk_size": chunk_size,
                                "completed": sorted(completed_set),
                            }),
                            encoding="utf-8",
                        )
                return
            except Exception:
                with progress_lock:
                    session_bytes = max(0, session_bytes - reported)
                if attempt == 2 or stop_event.is_set():
                    raise
                time.sleep(0.5 * (attempt + 1))

    try:
        if pending_indices:
            with ThreadPoolExecutor(max_workers=min(num_workers, len(pending_indices))) as pool:
                futures = [pool.submit(_download_chunk, i) for i in pending_indices]
                for fut in as_completed(futures):
                    fut.result()

        with progress_lock:
            _render_progress(force=True)
        print()
    except KeyboardInterrupt:
        stop_event.set()
        f_part.close()
        try:
            meta_file.write_text(
                json.dumps({
                    "url": url,
                    "total_bytes": total_bytes,
                    "chunk_size": chunk_size,
                    "completed": sorted(completed_set),
                }),
                encoding="utf-8",
            )
        except Exception:
            pass
        print(f"\n\033[33m[!] {lbl_cancelled} (progress saved for resume)\033[0m")
        return False, lbl_cancelled, None
    except Exception as e:
        stop_event.set()
        f_part.close()
        try:
            meta_file.write_text(
                json.dumps({
                    "url": url,
                    "total_bytes": total_bytes,
                    "chunk_size": chunk_size,
                    "completed": sorted(completed_set),
                }),
                encoding="utf-8",
            )
        except Exception:
            pass
        print(f"\n\033[31m[ERROR] {lbl_failed} {e} (progress saved for resume)\033[0m")
        return False, str(e), None
    else:
        f_part.close()

    if meta_file.exists():
        try:
            meta_file.unlink()
        except Exception:
            pass
    if out_file.exists():
        out_file.unlink()
    part_file.rename(out_file)
    return True, f"{lbl_done} {out_file.name}", out_file


def download_hf_gguf_file(repo_id: str, filename: str, target_dir: Path, lang: str = "en") -> tuple[bool, str, Path | None]:
    """
    Mengunduh file GGUF dari Hugging Face dengan multi-part parallel downloader + resume.
    URL: https://huggingface.co/{repo_id}/resolve/main/{filename}
    """
    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    out_file = target_dir / filename

    if out_file.exists() and out_file.stat().st_size > 10 * 1024 * 1024:
        msg = f"File already exists: {out_file.name} ({out_file.stat().st_size / (1024**3):.2f} GB)"
        return True, msg, out_file

    url = f"https://huggingface.co/{repo_id}/resolve/main/{filename}"

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

    return download_file_parallel(
        url=url,
        out_file=out_file,
        lbl_cancelled=lbl_cancelled,
        lbl_failed=lbl_failed,
        lbl_done=lbl_done,
        user_agent=USER_AGENT,
    )
