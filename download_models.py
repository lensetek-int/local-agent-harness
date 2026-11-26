#!/usr/bin/env python3
"""
Model & Asset Downloader for Local LLM & Edge Studio
Memungkinkan pengguna mengunduh model LLM GGUF, Speech-to-Text Whisper,
dan TTS Voice Models langsung dari Hugging Face secara otomatis.
"""

import os
import sys
import argparse
import urllib.request
import urllib.error

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MODEL_CATALOG = {
    "lensetek-edge-loop-3b": {
        "name": "Lensetek Edge-Loop 3B (Q4_K_M GGUF)",
        "repo_id": "lensetek/lensetek-edge-loop-3b-GGUF",
        "filename": "lensetek-edge-loop-3b-q4_k_m.gguf",
        "dest": os.path.join(BASE_DIR, "lensetek-edge-loop-3b-q4_k_m.gguf"),
        "size_mb": 1930,
        "desc": "🔥 Flagship Edge Agent: Looped Reasoning, Error Recovery & Anti-Hallucination (RAM < 2.5 GB)."
    },
    "lensetek-iot-coder-3b": {
        "name": "Lensetek IoT Coder 3B (Q4_K_M GGUF)",
        "repo_id": "lensetek/lensetek-iot-coder-3b-GGUF",
        "filename": "lensetek-iot-coder-3b-q4_k_m.gguf",
        "dest": os.path.join(BASE_DIR, "lensetek-iot-coder-3b-q4_k_m.gguf"),
        "size_mb": 1841,
        "desc": "⚡ Specialized IoT Coder 3B: Arduino/ESP32/MicroPython, pyserial/MQTT, Mobile-First Dashboards & Circuit Diagrams (Wokwi/WireViz/KiCad/Mermaid)."
    },
    "qwen2.5-0.5b": {
        "name": "Qwen 2.5 0.5B Instruct (Q4_K_M)",
        "repo_id": "Qwen/Qwen2.5-0.5B-Instruct-GGUF",
        "filename": "qwen2.5-0.5b-instruct-q4_k_m.gguf",
        "dest": os.path.join(BASE_DIR, "qwen2.5-0.5b-instruct-q4_k_m.gguf"),
        "size_mb": 491,
        "desc": "Ultra-lightweight chat, cepat di semua jenis laptop/CPU."
    },
    "qwen2.5-3b": {
        "name": "Qwen 2.5 3B Instruct (Q4_K_M)",
        "repo_id": "Qwen/Qwen2.5-3B-Instruct-GGUF",
        "filename": "qwen2.5-3b-instruct-q4_k_m.gguf",
        "dest": os.path.join(BASE_DIR, "qwen2.5-3b-instruct-q4_k_m.gguf"),
        "size_mb": 2040,
        "desc": "⭐ Sangat direkomendasikan untuk AI Agent, Function Calling & Structured JSON."
    },
    "qwen2.5-7b": {
        "name": "Qwen 2.5 7B Instruct (Q4_K_M)",
        "repo_id": "bartowski/Qwen2.5-7B-Instruct-GGUF",
        "filename": "Qwen2.5-7B-Instruct-Q4_K_M.gguf",
        "dest": os.path.join(BASE_DIR, "Qwen2.5-7B-Instruct-Q4_K_M.gguf"),
        "size_mb": 4680,
        "desc": "👑 Standar emas AI Agent: multi-step planning, coding & tool chains kompleks."
    },
    "smolvlm-500m": {
        "name": "SmolVLM 500M Instruct + Vision Projector",
        "files": [
            {
                "repo_id": "HuggingFaceTB/SmolVLM-500M-Instruct-GGUF",
                "filename": "SmolVLM-500M-Instruct-Q8_0.gguf",
                "dest": os.path.join(BASE_DIR, "SmolVLM-500M-Instruct-Q8_0.gguf")
            },
            {
                "repo_id": "HuggingFaceTB/SmolVLM-500M-Instruct-GGUF",
                "filename": "mmproj-SmolVLM-500M-Instruct-Q8_0.gguf",
                "dest": os.path.join(BASE_DIR, "mmproj-SmolVLM-500M-Instruct-Q8_0.gguf")
            }
        ],
        "size_mb": 545,
        "desc": "Model multimodal vision untuk analisis gambar & visual."
    },
    "whisper-base": {
        "name": "Whisper Base (Speech-to-Text)",
        "repo_id": "ggerganov/whisper.cpp",
        "filename": "ggml-base.bin",
        "dest": os.path.join(BASE_DIR, "voice_models", "ggml-base.bin"),
        "size_mb": 147,
        "desc": "Model transkripsi suara STT cepat dan ringan (RAM ~300 MB)."
    },
    "whisper-small": {
        "name": "Whisper Small (Speech-to-Text Akurat)",
        "repo_id": "ggerganov/whisper.cpp",
        "filename": "ggml-small.bin",
        "dest": os.path.join(BASE_DIR, "voice_models", "ggml-small.bin"),
        "size_mb": 487,
        "desc": "Model STT akurat dengan kosakata Bahasa Indonesia lengkap."
    },
    "kokoro-82m": {
        "name": "Kokoro-82M Offline Voice Engine",
        "files": [
            {
                "repo_id": "hexgrad/Kokoro-82M",
                "filename": "kokoro-v1.0.onnx",
                "dest": os.path.join(BASE_DIR, "voice_models", "kokoro", "kokoro-v1.0.onnx")
            },
            {
                "repo_id": "hexgrad/Kokoro-82M",
                "filename": "voices-v1.0.bin",
                "dest": os.path.join(BASE_DIR, "voice_models", "kokoro", "voices-v1.0.bin")
            }
        ],
        "size_mb": 337,
        "desc": "Model Text-to-Speech offline 82M bergaya natural ala studio."
    }
}

def download_file_hf(repo_id, filename, dest_path, progress_callback=None):
    """Mengunduh file dari Hugging Face Hub dengan visual progress bar."""
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    if os.path.exists(dest_path) and os.path.getsize(dest_path) > 1024:
        print(f"  [✓] File sudah ada: {os.path.basename(dest_path)} ({os.path.getsize(dest_path) / (1024*1024):.1f} MB)")
        if progress_callback:
            sz = os.path.getsize(dest_path)
            progress_callback(sz, sz)
        return True

    print(f"  Mengunduh: {filename} dari {repo_id}...")
    
    # 1. Coba direct HTTP stream dari Hugging Face CDN (agar progress bar akurat)
    url = f"https://huggingface.co/{repo_id}/resolve/main/{filename}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            total_size = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            block_size = 1024 * 512  # 512 KB per chunk
            temp_dest = dest_path + ".download"

            with open(temp_dest, "wb") as f:
                while True:
                    chunk = resp.read(block_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total_size)
                    if total_size > 0:
                        pct = (downloaded / total_size) * 100
                        mb_done = downloaded / (1024 * 1024)
                        mb_total = total_size / (1024 * 1024)
                        bar = "=" * int(pct / 4) + "-" * (25 - int(pct / 4))
                        sys.stdout.write(f"\r  [{bar}] {pct:5.1f}% ({mb_done:.1f}/{mb_total:.1f} MB)")
                        sys.stdout.flush()
                    else:
                        mb_done = downloaded / (1024 * 1024)
                        sys.stdout.write(f"\r  Mengunduh... {mb_done:.1f} MB")
                        sys.stdout.flush()
            print()
            if os.path.exists(dest_path):
                os.remove(dest_path)
            os.rename(temp_dest, dest_path)
            print(f"  [✓] Berhasil diunduh: {os.path.basename(dest_path)}")
            if progress_callback:
                progress_callback(total_size or downloaded, total_size or downloaded)
            return True
    except Exception as e:
        print(f"  [!] HTTP stream error: {e}, mencoba fallback hf_hub_download...")
        try:
            from huggingface_hub import hf_hub_download
            cached_path = hf_hub_download(
                repo_id=repo_id,
                filename=filename,
                repo_type="model"
            )
            import shutil
            shutil.copy2(cached_path, dest_path)
            print(f"  [✓] Selesai via hf_hub_download: {os.path.basename(dest_path)}")
            if progress_callback:
                sz = os.path.getsize(dest_path)
                progress_callback(sz, sz)
            return True
        except Exception as err2:
            print(f"  [!] Gagal mengunduh: {err2}")
            temp_dest = dest_path + ".download"
            if os.path.exists(temp_dest):
                os.remove(temp_dest)
            return False

def download_item(key, progress_callback=None):
    if key not in MODEL_CATALOG:
        print(f"[!] Kunci model '{key}' tidak ditemukan di katalog.")
        return False
    item = MODEL_CATALOG[key]
    print(f"\n--- Mengunduh {item['name']} ---")
    if "files" in item:
        success = True
        for f in item["files"]:
            ok = download_file_hf(f["repo_id"], f["filename"], f["dest"], progress_callback)
            if not ok: success = False
        return success
    else:
        return download_file_hf(item["repo_id"], item["filename"], item["dest"], progress_callback)

def check_status():
    print("\n=======================================================")
    print("      STATUS MODEL & ASSET LOCAL LLM STUDIO")
    print("=======================================================")
    for k, item in MODEL_CATALOG.items():
        if "files" in item:
            all_exist = all(os.path.exists(f["dest"]) for f in item["files"])
            status = "✅ TERPASANG" if all_exist else "❌ BELUM TERPASANG"
        else:
            status = "✅ TERPASANG" if os.path.exists(item["dest"]) else "❌ BELUM TERPASANG"
        print(f"[{status}] {item['name']} ({item['size_mb']} MB)")
    print("=======================================================\n")

def interactive_menu():
    while True:
        print("\n" + "=" * 62)
        print("     LOCAL LLM & AI AGENT - MODEL DOWNLOADER")
        print("=" * 62)
        print("Pilih model yang ingin Anda unduh:")
        print(" [1] Lensetek Edge-Loop 3B (2.0 GB) - 🔥 Flagship Looped Agent (Error-Recovery, RAM < 2.5GB)")
        print(" [2] Qwen 2.5 0.5B (491 MB)  - Cepat, Ultra-Light")
        print(" [3] Qwen 2.5 3B   (2.0 GB)  - Standar AI Agent (Function Calling)")
        print(" [4] Qwen 2.5 7B   (4.7 GB)  - 👑 Advanced AI Agent (Complex Chains)")
        print(" [5] SmolVLM 500M  (545 MB)  - Vision & Image Understanding")
        print(" [6] Whisper Base  (147 MB)  - Speech-to-Text Cepat")
        print(" [7] Whisper Small (487 MB)  - Speech-to-Text Akurat")
        print(" [8] Kokoro-82M    (337 MB)  - Suara Natural Studio Offline")
        print(" [9] Unduh Komponen Default  (Qwen 0.5B + Whisper Base)")
        print(" [s] Cek Status Model")
        print(" [0] Keluar")
        print("=" * 62)
        choice = input("Pilihan Anda [0-9, s]: ").strip().lower()

        if choice == "0":
            print("Keluar.")
            break
        elif choice == "1":
            download_item("lensetek-edge-loop-3b")
        elif choice == "2":
            download_item("qwen2.5-0.5b")
        elif choice == "3":
            download_item("qwen2.5-3b")
        elif choice == "4":
            download_item("qwen2.5-7b")
        elif choice == "5":
            download_item("smolvlm-500m")
        elif choice == "6":
            download_item("whisper-base")
        elif choice == "7":
            download_item("whisper-small")
        elif choice == "8":
            download_item("kokoro-82m")
        elif choice == "9":
            download_item("qwen2.5-0.5b")
            download_item("whisper-base")
        elif choice == "s":
            check_status()
        else:
            print("Pilihan tidak valid, silakan coba lagi.")

def main():
    parser = argparse.ArgumentParser(description="Downloader Model Local LLM")
    parser.add_argument("--default", action="store_true", help="Unduh model default (Qwen 0.5B & Whisper Base)")
    parser.add_argument("--agent", action="store_true", help="Unduh model rekomendasi AI Agent (Qwen 2.5 3B)")
    parser.add_argument("--loop", action="store_true", help="Unduh model Lensetek Edge-Loop 3B Flagship")
    parser.add_argument("--model", type=str, help="Nama model spesifik (lensetek-edge-loop-3b, qwen2.5-0.5b, dll.)")
    parser.add_argument("--status", action="store_true", help="Cek status kelengkapan model")

    args = parser.parse_args()

    if args.status:
        check_status()
        return

    if args.default:
        print("[INFO] Mengunduh paket model default...")
        download_item("qwen2.5-0.5b")
        download_item("whisper-base")
        return

    if args.loop:
        print("[INFO] Mengunduh model Lensetek Edge-Loop 3B Flagship...")
        download_item("lensetek-edge-loop-3b")
        return

    if args.agent:
        print("[INFO] Mengunduh model rekomendasi AI Agent (Qwen 2.5 3B)...")
        download_item("qwen2.5-3b")
        return

    if args.model:
        download_item(args.model)
        return

    interactive_menu()

if __name__ == "__main__":
    main()
