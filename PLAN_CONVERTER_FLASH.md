# ⚡ PLAN EKSEKUSI ATOMIK — GEMINI 3.8 FLASH (MEDIUM)
## Arsitektur 1 Repo Induk & Multi-Variant Self-Conversion (`lensetek-edge-loop-3b`)

> **Petunjuk Penggunaan untuk Agen (Gemini 3.8 Flash Medium):**
> Dokumen ini adalah *blueprint eksekusi deterministik* yang sudah diaudit agar bebas dari error sintaks, kerusakan struktur JSON `.ipynb`, *NameError*, maupun kebocoran kredensial.
>
> **Aturan Emas (WAJIB DIPATUHI):**
> 1. **Gunakan `py`** (bukan `python`) untuk menjalankan semua perintah Python di Windows PowerShell.
> 2. **DILARANG mengedit file `.ipynb` secara manual dengan `edit_file`** karena sangat rawan merusak format JSON/escaping newline. Selalu baca & tulis `.ipynb` menggunakan script Python dengan modul standar `json` (`indent=2`, `ensure_ascii=False`).
> 3. **DILARANG** menulis hardcode token (`hf_...`), API key, atau kredensial apa pun di dalam kode atau notebook. Wajib baca dari `google.colab.userdata` / `os.environ` / `getpass`.
> 4. **DILARANG** menjalankan `git push` atau `HfApi.upload_*` ke remote selama pengerjaan Sprint, kecuali pengguna menginstruksikan secara eksplisit setelah semua Sprint lulus verifikasi.
> 5. **WAJIB** jalankan **Perintah Verifikasi** di akhir setiap Sprint.

---

## 📋 Peta 3 Sprint Atomik

| Sprint | Judul Pekerjaan | File Target | Tujuan Utama |
| :---: | :--- | :--- | :--- |
| **Sprint 1** | Upgrade Pipeline Ekspor Training Colab | `training/lensetek_train_colab.ipynb` | Menambah backup LoRA adapter ke Drive & push 16-bit Safetensors ke `lensetek/lensetek-edge-loop-3b` secara aman. |
| **Sprint 2** | Buat Notebook Converter Mandiri (1-Klik Colab) | `converter/lensetek_converter_colab.ipynb`, `converter/README.md` | Memberi pengguna alat konversi mandiri di cloud gratis ke **GGUF Custom**, **WebGPU ONNX (`q4f16`)**, dan **MLX**. |
| **Sprint 3** | Tambah Panduan *Self-Conversion* di Model Card | `model_card/README_base.md`, `README.md` | Menambahkan navigasi konversi mandiri (`ggml-org/gguf-my-repo` + Colab Converter) secara transparan. |

---

## 🔧 SPRINT 1: Upgrade `training/lensetek_train_colab.ipynb` (Backup LoRA + Push 16-Bit Safetensors)

### 1. Masalah Logika yang Dicegah
- Sebelumnya, notebook hanya menyimpan file `.gguf` ke Google Drive (`SAVE_DIR`). Akibatnya, bobot 16-bit Safetensors dan LoRA adapter hilang saat sesi Colab berakhir.
- Jika pengguna melewati sel Mount Google Drive, variabel `SAVE_DIR` bisa memicu `NameError`.
- Jika `HF_TOKEN` belum diatur di Colab Secrets, `userdata.get("HF_TOKEN")` bisa memicu `SecretNotFoundError`.

### 2. Spesifikasi Perubahan Eksak
Sisipkan **2 pasang sel baru (Markdown + Code)** tepat **sebelum** sel `### Langkah 6: Ekspor Model Langsung ke GGUF 4-Bit (Q4_K_M)` (yaitu setelah sel uji coba `FastLanguageModel.for_inference(model)`):
1. **Langkah 5.6 — Backup LoRA Adapter ke Google Drive / Lokal** (ukuran ringan ~100 MB, wajib dilakukan sebelum merge agar adapter selalu aman).
2. **Langkah 5.7 — Merge & Push Bobot 16-Bit Safetensors ke `lensetek/lensetek-edge-loop-3b`** (dengan helper aman `get_hf_token()`, opsional skip push jika token kosong, dan fallback simpan lokal).

### 3. Source Code Builder Eksak (Jalankan via `py` untuk Memodifikasi Notebook dengan Aman)

Jalankan skrip Python berikut (atau simpan sementara, jalankan, lalu hapus jika memakai file sementara — **jangan tinggalkan file skrip builder sementara di repo**):

```python
import json
from pathlib import Path

nb_path = Path("training/lensetek_train_colab.ipynb")
nb = json.loads(nb_path.read_text(encoding="utf-8"))

# Cek idempotensi: jangan duplikasi jika sudah pernah disisipkan
already_patched = any(
    "Langkah 5.6" in "".join(c.get("source", []))
    for c in nb.get("cells", [])
)
if already_patched:
    print("[SKIP] Sel Langkah 5.6 & 5.7 sudah ada di notebook.")
else:
    new_cells = [
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "---\n",
                "### Langkah 5.6: Backup LoRA Adapter (~100 MB) ke Google Drive / Lokal\n",
                "Menyimpan adapter LoRA sebelum proses merge/kuantisasi agar bobot hasil fine-tuning tetap aman dan dapat diekspor ulang kapan saja."
            ]
        },
        {
            "cell_type": "code",
            "metadata": {},
            "execution_count": None,
            "outputs": [],
            "source": [
                "import os\n",
                "\n",
                "# Guard agar tidak NameError jika pengguna melewati langkah Mount Google Drive\n",
                "SAVE_DIR = globals().get(\"SAVE_DIR\", \"/content/lensetek_outputs\")\n",
                "os.makedirs(SAVE_DIR, exist_ok=True)\n",
                "\n",
                "lora_dir = os.path.join(SAVE_DIR, \"lensetek_edge_loop_3b_lora\")\n",
                "print(f\"Menyimpan backup LoRA adapter ke: {lora_dir}...\")\n",
                "model.save_pretrained(lora_dir)\n",
                "tokenizer.save_pretrained(lora_dir)\n",
                "print(\"[OK] Backup LoRA adapter berhasil disimpan!\")\n"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "---\n",
                "### Langkah 5.7: Ekspor & Push Bobot Base 16-Bit Safetensors ke Hugging Face\n",
                "Mengunggah bobot penuh 16-bit (`merged_16bit`) ke repositori induk `lensetek/lensetek-edge-loop-3b` agar pengguna dapat mengonversi sendiri ke berbagai varian (GGUF custom, WebGPU ONNX, MLX, vLLM).\n",
                "\n",
                "> **Keamanan Kredensial:** Simpan token Hugging Face Anda di menu **Colab Secrets (ikon kunci 🔑)** dengan nama `HF_TOKEN` (akses *Write*). Jangan pernah menempelkan token langsung di dalam kode sel."
            ]
        },
        {
            "cell_type": "code",
            "metadata": {},
            "execution_count": None,
            "outputs": [],
            "source": [
                "import os\n",
                "from getpass import getpass\n",
                "\n",
                "BASE_HF_REPO = \"lensetek/lensetek-edge-loop-3b\"\n",
                "PUSH_16BIT_TO_HF = True  # Ubah ke False jika hanya ingin simpan lokal\n",
                "\n",
                "def get_hf_token():\n",
                "    # 1. Coba ambil dari Colab Secrets\n",
                "    try:\n",
                "        from google.colab import userdata\n",
                "        tok = userdata.get(\"HF_TOKEN\")\n",
                "        if tok and tok.strip():\n",
                "            return tok.strip()\n",
                "    except Exception:\n",
                "        pass\n",
                "    # 2. Fallback ke environment variable\n",
                "    tok = os.environ.get(\"HF_TOKEN\", \"\").strip()\n",
                "    if tok:\n",
                "        return tok\n",
                "    # 3. Fallback input interaktif aman (tidak tercetak di layar)\n",
                "    if PUSH_16BIT_TO_HF:\n",
                "        return getpass(\"Masukkan HF_TOKEN (Write) atau tekan Enter untuk lewati push: \").strip()\n",
                "    return \"\"\n",
                "\n",
                "hf_token = get_hf_token()\n",
                "\n",
                "if PUSH_16BIT_TO_HF and hf_token:\n",
                "    print(f\"Menggabungkan & mengunggah 16-bit Safetensors ke {BASE_HF_REPO}...\")\n",
                "    try:\n",
                "        model.push_to_hub_merged(\n",
                "            BASE_HF_REPO,\n",
                "            tokenizer,\n",
                "            save_method=\"merged_16bit\",\n",
                "            token=hf_token,\n",
                "        )\n",
                "        print(f\"[OK] Bobot 16-bit Safetensors berhasil diunggah ke https://huggingface.co/{BASE_HF_REPO}\")\n",
                "    except Exception as e:\n",
                "        print(f\"[WARNING] Push ke Hugging Face gagal: {e}\")\n",
                "        local_16bit = os.path.join(SAVE_DIR, \"lensetek_edge_loop_3b_safetensors\")\n",
                "        print(f\"Menyimpan fallback 16-bit Safetensors secara lokal ke: {local_16bit}...\")\n",
                "        model.save_pretrained_merged(local_16bit, tokenizer, save_method=\"merged_16bit\")\n",
                "else:\n",
                "    local_16bit = os.path.join(SAVE_DIR, \"lensetek_edge_loop_3b_safetensors\")\n",
                "    print(f\"[INFO] HF_TOKEN kosong atau PUSH_16BIT_TO_HF=False. Menyimpan lokal ke: {local_16bit}...\")\n",
                "    model.save_pretrained_merged(local_16bit, tokenizer, save_method=\"merged_16bit\")\n"
            ]
        }
    ]

    # Cari indeks tepat sebelum Langkah 6 (Ekspor GGUF)
    insert_idx = None
    for idx, cell in enumerate(nb["cells"]):
        text = "".join(cell.get("source", []))
        if "Langkah 6:" in text:
            insert_idx = idx
            break

    if insert_idx is None:
        raise RuntimeError("Anchor 'Langkah 6:' tidak ditemukan di notebook!")

    nb["cells"][insert_idx:insert_idx] = new_cells
    nb_path.write_text(json.dumps(nb, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[SUCCESS] Berhasil menyisipkan {len(new_cells)} sel sebelum indeks {insert_idx}.")
```

### 4. Perintah Verifikasi Sprint 1 (WAJIB DIJALANKAN)
```powershell
py -c "import json, ast; nb=json.load(open('training/lensetek_train_colab.ipynb', encoding='utf-8')); code_cells=[c for c in nb['cells'] if c['cell_type']=='code']; [ast.parse(''.join(c['source'])) for c in code_cells if not any(l.strip().startswith(('!','%')) for l in c['source'])]; print('TOTAL_CELLS:', len(nb['cells']), 'HAS_5_6:', any('Langkah 5.6' in ''.join(c['source']) for c in nb['cells']), 'HAS_5_7:', any('Langkah 5.7' in ''.join(c['source']) for c in nb['cells']))"
```
**Ekspektasi Lulus:** `HAS_5_6: True`, `HAS_5_7: True`, tanpa `JSONDecodeError` maupun `SyntaxError`.

---

## 🔧 SPRINT 2: Buat Notebook Converter Mandiri (`converter/lensetek_converter_colab.ipynb` & `converter/README.md`)

### 1. Masalah Logika yang Dicegah
- **Fail-Fast Pre-Flight Check**: Sebelum mengunduh dependensi berat (PyTorch / Optimum / llama.cpp), notebook **wajib** mengecek via `HfApi().list_repo_files(MODEL_ID)` apakah file `.safetensors` sudah tersedia di repo target. Jika belum ada, hentikan proses dengan pesan yang jelas dan arahkan ke repo GGUF siap pakai — jangan sampai user menunggu 10 menit lalu crash!
- **WebGPU ONNX (`q4f16`)**: Harus menghasilkan format ONNX yang kompatibel dengan `@huggingface/transformers` (Transformers.js v3) di browser WebGPU, bukan sekadar `fp32` 12 GB yang langsung crash OOM di browser.
- **GGUF Custom**: Gunakan binary/build `llama.cpp` di lingkungan Linux Colab (jauh lebih stabil daripada laptop Windows pengguna), dengan pilihan dropdown (`Q2_K`, `Q3_K_M`, `Q4_K_M`, `Q5_K_M`, `Q6_K`, `Q8_0`, `F16`).
- **Apple Silicon MLX**: Jelaskan secara jujur bahwa `mlx_lm` membutuhkan chip Apple Silicon (macOS M1/M2/M3/M4), sehingga jika user memilih opsi `mlx`, notebook mencetak perintah 1-baris resmi untuk dijalankan langsung di Terminal Mac (tidak mencoba menginstal `mlx` di Linux Colab yang pasti gagal!).

### 2. Target File
- **Buat baru:** `converter/lensetek_converter_colab.ipynb`
- **Buat baru:** `converter/README.md`

### 3. Source Code Builder Eksak untuk `converter/lensetek_converter_colab.ipynb`

Jalankan skrip Python berikut untuk membangkitkan `converter/lensetek_converter_colab.ipynb` dengan struktur JSON valid 100%:

```python
import json
from pathlib import Path

out_dir = Path("converter")
out_dir.mkdir(parents=True, exist_ok=True)

notebook = {
    "nbformat": 4,
    "nbformat_minor": 0,
    "metadata": {
        "colab": {
            "provenance": [],
            "gpuType": "T4"
        },
        "kernelspec": {
            "name": "python3",
            "display_name": "Python 3"
        },
        "language_info": {
            "name": "python"
        },
        "accelerator": "GPU"
    },
    "cells": [
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "# 🔄 Lensetek-Edge-Loop-3B: Multi-Variant Self-Converter\n",
                "\n",
                "Notebook ini memungkinkan Anda mengonversi bobot dasar 16-bit (**[`lensetek/lensetek-edge-loop-3b`](https://huggingface.co/lensetek/lensetek-edge-loop-3b)**) ke varian target sesuai perangkat Anda secara gratis di Google Colab:\n",
                "- **`gguf`** — Untuk Ollama, `llama.cpp`, LM Studio, Raspberry Pi, Mini PC (pilihan: `Q2_K`, `Q3_K_M`, `Q4_K_M`, `Q5_K_M`, `Q6_K`, `Q8_0`, `F16`).\n",
                "- **`webgpu_onnx`** — Untuk dijalankan langsung di browser klien via **Transformers.js v3 (WebGPU `q4f16`)**.\n",
                "- **`mlx_guide`** — Menghasilkan perintah 1-baris siap pakai untuk Mac Apple Silicon (M1/M2/M3/M4).\n",
                "\n",
                "> **Tips:** Gunakan runtime **T4 GPU** atau **CPU High-RAM** di Colab (*Runtime → Change runtime type*)."
            ]
        },
        {
            "cell_type": "code",
            "metadata": {},
            "execution_count": None,
            "outputs": [],
            "source": [
                "#@title 1. Konfigurasi Target Konversi\n",
                "MODEL_ID = \"lensetek/lensetek-edge-loop-3b\" #@param {type:\"string\"}\n",
                "TARGET_FORMAT = \"gguf\" #@param [\"gguf\", \"webgpu_onnx\", \"mlx_guide\"]\n",
                "GGUF_QUANT = \"Q4_K_M\" #@param [\"Q2_K\", \"Q3_K_M\", \"Q4_K_M\", \"Q5_K_M\", \"Q6_K\", \"Q8_0\", \"F16\"]\n",
                "WEBGPU_DTYPE = \"q4f16\" #@param [\"q4f16\", \"q4\", \"fp16\"]\n",
                "PUSH_TO_OWN_HF_REPO = \"\" #@param {type:\"string\"}\n",
                "\n",
                "print(f\"Model Sumber : {MODEL_ID}\")\n",
                "print(f\"Format Target: {TARGET_FORMAT}\")\n",
                "if TARGET_FORMAT == \"gguf\":\n",
                "    print(f\"Kuantisasi   : {GGUF_QUANT}\")\n",
                "elif TARGET_FORMAT == \"webgpu_onnx\":\n",
                "    print(f\"ONNX Dtype   : {WEBGPU_DTYPE}\")\n"
            ]
        },
        {
            "cell_type": "code",
            "metadata": {},
            "execution_count": None,
            "outputs": [],
            "source": [
                "#@title 2. Pre-Flight Check: Validasi Ketersediaan Bobot Safetensors\n",
                "import sys\n",
                "from huggingface_hub import HfApi\n",
                "\n",
                "api = HfApi()\n",
                "files = api.list_repo_files(repo_id=MODEL_ID, repo_type=\"model\")\n",
                "safetensors_files = [f for f in files if f.endswith(\".safetensors\")]\n",
                "has_config = \"config.json\" in files\n",
                "\n",
                "if not safetensors_files or not has_config:\n",
                "    raise RuntimeError(\n",
                "        f\"[STOP] Repositori '{MODEL_ID}' belum berisi bobot 16-bit (.safetensors) & config.json.\\n\"\n",
                "        \"Silakan gunakan versi GGUF siap pakai sementara waktu di:\\n\"\n",
                "        \"https://huggingface.co/lensetek/lensetek-edge-loop-3b-GGUF\"\n",
                "    )\n",
                "\n",
                "print(f\"[OK] Ditemukan {len(safetensors_files)} berkas Safetensors dan config.json. Siap dikonversi!\")\n"
            ]
        },
        {
            "cell_type": "code",
            "metadata": {},
            "execution_count": None,
            "outputs": [],
            "source": [
                "#@title 3. Eksekusi Konversi Sesuai Format Pilihan\n",
                "import os\n",
                "import subprocess\n",
                "from pathlib import Path\n",
                "\n",
                "OUTPUT_ARTIFACT_PATH = None\n",
                "\n",
                "def run_cmd(cmd):\n",
                "    print(f\"\\n$ {cmd}\")\n",
                "    res = subprocess.run(cmd, shell=True)\n",
                "    if res.returncode != 0:\n",
                "        raise RuntimeError(f\"Perintah gagal dengan exit code {res.returncode}: {cmd}\")\n",
                "\n",
                "if TARGET_FORMAT == \"mlx_guide\":\n",
                "    print(\"=\" * 65)\n",
                "    print(\" 🍎 APPLE SILICON (MLX) — JALANKAN DI TERMINAL MAC (M1/M2/M3/M4)\")\n",
                "    print(\"=\" * 65)\n",
                "    print(\"Catatan: MLX hanya dapat dijalankan di macOS Apple Silicon, bukan Linux Colab.\")\n",
                "    print(\"Salin dan jalankan perintah berikut di Terminal Mac Anda:\\n\")\n",
                "    print(\"pip install -U mlx-lm\")\n",
                "    print(f\"mlx_lm.convert --hf-path {MODEL_ID} --mlx-path ./lensetek-edge-loop-3b-mlx-4bit -q --q-bits 4\")\n",
                "\n",
                "elif TARGET_FORMAT == \"gguf\":\n",
                "    local_hf_dir = Path(\"/content/hf_base_model\")\n",
                "    out_dir = Path(\"/content/gguf_output\")\n",
                "    out_dir.mkdir(parents=True, exist_ok=True)\n",
                "\n",
                "    from huggingface_hub import snapshot_download\n",
                "    print(f\"Mengunduh {MODEL_ID} ke {local_hf_dir}...\")\n",
                "    snapshot_download(repo_id=MODEL_ID, local_dir=str(local_hf_dir))\n",
                "\n",
                "    if not Path(\"/content/llama.cpp\").exists():\n",
                "        run_cmd(\"git clone --depth 1 https://github.com/ggml-org/llama.cpp /content/llama.cpp\")\n",
                "    run_cmd(\"pip install -q -r /content/llama.cpp/requirements/requirements-convert_hf_to_gguf.txt\")\n",
                "\n",
                "    f16_path = out_dir / \"lensetek-edge-loop-3b-f16.gguf\"\n",
                "    run_cmd(f\"python3 /content/llama.cpp/convert_hf_to_gguf.py {local_hf_dir} --outfile {f16_path} --outtype f16\")\n",
                "\n",
                "    if GGUF_QUANT.upper() == \"F16\":\n",
                "        OUTPUT_ARTIFACT_PATH = str(f16_path)\n",
                "    else:\n",
                "        run_cmd(\"cmake -S /content/llama.cpp -B /content/llama.cpp/build -DLLAMA_CURL=OFF && cmake --build /content/llama.cpp/build --target llama-quantize -j\")\n",
                "        quant_path = out_dir / f\"lensetek-edge-loop-3b-{GGUF_QUANT.lower()}.gguf\"\n",
                "        run_cmd(f\"/content/llama.cpp/build/bin/llama-quantize {f16_path} {quant_path} {GGUF_QUANT.upper()}\")\n",
                "        if f16_path.exists():\n",
                "            f16_path.unlink()  # Hemat ruang disk Colab\n",
                "        OUTPUT_ARTIFACT_PATH = str(quant_path)\n",
                "\n",
                "    print(f\"\\n[SUCCESS] Berkas GGUF siap di: {OUTPUT_ARTIFACT_PATH}\")\n",
                "\n",
                "elif TARGET_FORMAT == \"webgpu_onnx\":\n",
                "    onnx_out_dir = Path(\"/content/onnx_webgpu_output\")\n",
                "    onnx_out_dir.mkdir(parents=True, exist_ok=True)\n",
                "\n",
                "    run_cmd(\"pip install -q -U transformers optimum[onnxruntime] onnxruntime-genai onnx\")\n",
                "    if not Path(\"/content/transformers.js\").exists():\n",
                "        run_cmd(\"git clone --depth 1 https://github.com/huggingface/transformers.js /content/transformers.js\")\n",
                "\n",
                "    quant_flag = \"--quantize\" if WEBGPU_DTYPE in (\"q4f16\", \"q4\") else \"\"\n",
                "    run_cmd(\n",
                "        f\"cd /content/transformers.js && python3 -m scripts.convert --model_id {MODEL_ID} \"\n",
                "        f\"--task text-generation-with-past --output_parent_dir {onnx_out_dir} {quant_flag}\"\n",
                "    )\n",
                "    OUTPUT_ARTIFACT_PATH = str(onnx_out_dir)\n",
                "    print(f\"\\n[SUCCESS] Folder ONNX WebGPU siap di: {OUTPUT_ARTIFACT_PATH}\")\n"
            ]
        },
        {
            "cell_type": "code",
            "metadata": {},
            "execution_count": None,
            "outputs": [],
            "source": [
                "#@title 4. (Opsional) Push Hasil ke Repo Hugging Face Pribadi atau Unduh\n",
                "import os\n",
                "from getpass import getpass\n",
                "from huggingface_hub import HfApi\n",
                "\n",
                "if not OUTPUT_ARTIFACT_PATH:\n",
                "    print(\"[INFO] Tidak ada file artefak untuk diunduh/diunggah (misal mode mlx_guide).\")\n",
                "elif PUSH_TO_OWN_HF_REPO.strip():\n",
                "    tok = \"\"\n",
                "    try:\n",
                "        from google.colab import userdata\n",
                "        tok = (userdata.get(\"HF_TOKEN\") or \"\").strip()\n",
                "    except Exception:\n",
                "        pass\n",
                "    if not tok:\n",
                "        tok = getpass(\"Masukkan HF_TOKEN (Write) untuk upload hasil konversi: \").strip()\n",
                "\n",
                "    api = HfApi(token=tok)\n",
                "    api.create_repo(repo_id=PUSH_TO_OWN_HF_REPO.strip(), repo_type=\"model\", exist_ok=True)\n",
                "    if os.path.isdir(OUTPUT_ARTIFACT_PATH):\n",
                "        api.upload_folder(folder_path=OUTPUT_ARTIFACT_PATH, repo_id=PUSH_TO_OWN_HF_REPO.strip(), repo_type=\"model\")\n",
                "    else:\n",
                "        api.upload_file(\n",
                "            path_or_fileobj=OUTPUT_ARTIFACT_PATH,\n",
                "            path_in_repo=os.path.basename(OUTPUT_ARTIFACT_PATH),\n",
                "            repo_id=PUSH_TO_OWN_HF_REPO.strip(),\n",
                "            repo_type=\"model\",\n",
                "        )\n",
                "    print(f\"[OK] Berhasil diunggah ke https://huggingface.co/{PUSH_TO_OWN_HF_REPO.strip()}\")\n",
                "else:\n",
                "    print(f\"Artefak tersimpan di: {OUTPUT_ARTIFACT_PATH}\")\n",
                "    if os.path.isfile(OUTPUT_ARTIFACT_PATH):\n",
                "        from google.colab import files\n",
                "        files.download(OUTPUT_ARTIFACT_PATH)\n",
                "    else:\n",
                "        print(\"Gunakan panel Files di sebelah kiri Colab atau isi PUSH_TO_OWN_HF_REPO untuk mengambil folder hasil.\")\n"
            ]
        }
    ]
}

out_file = out_dir / "lensetek_converter_colab.ipynb"
out_file.write_text(json.dumps(notebook, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"[SUCCESS] Created {out_file}")
```

### 4. Buat `converter/README.md`
Buat file singkat `converter/README.md` yang menjelaskan:
1. Cara konversi GGUF 1-klik tanpa kode via Hugging Face Space **[`ggml-org/gguf-my-repo`](https://huggingface.co/spaces/ggml-org/gguf-my-repo)** (target model: `lensetek/lensetek-edge-loop-3b`).
2. Cara menggunakan `lensetek_converter_colab.ipynb` untuk mencetak **GGUF Custom**, **WebGPU ONNX (`Transformers.js v3`)**, dan **Apple Silicon MLX**.
3. Catatan prasyarat: konversi membutuhkan bobot 16-bit Safetensors di `lensetek/lensetek-edge-loop-3b`; untuk pemakaian cepat tanpa konversi, gunakan `lensetek/lensetek-edge-loop-3b-GGUF`.

### 5. Perintah Verifikasi Sprint 2 (WAJIB DIJALANKAN)
```powershell
py -c "import json, ast; nb=json.load(open('converter/lensetek_converter_colab.ipynb', encoding='utf-8')); [ast.parse(''.join(c['source'])) for c in nb['cells'] if c['cell_type']=='code']; print('VALID_CONVERTER_NB_CELLS:', len(nb['cells']))"
```
**Ekspektasi Lulus:** `VALID_CONVERTER_NB_CELLS: 5` tanpa error sintaks atau JSON error.

---

## 🔧 SPRINT 3: Perbarui Dokumentasi *Self-Conversion* (`model_card/README_base.md` & `README.md`)

### 1. Target File
- **Edit:** `model_card/README_base.md` (tepat sebelum bagian `## 🔗 Lensetek Model Family`, sekitar baris 155–165 — baca baris 145–170 dulu sebelum mengedit!).
- **Edit:** `README.md` (tambahkan 1 baris referensi ke folder `converter/` di bagian ekosistem/quickstart bila relevan, tanpa menghapus konten yang sudah ada).

### 2. Konten yang Ditambahkan di `model_card/README_base.md`
Tambahkan seksi **`## 🔄 Self-Conversion: Build Your Own Variant (GGUF / WebGPU / MLX)`** tepat di bawah blok `## 🚀 Quickstart with Hugging Face Transformers` dan sebelum `## 🔗 Lensetek Model Family`:

```markdown
## 🔄 Self-Conversion: Build Your Own Variant (GGUF / WebGPU / MLX)

Once the 16-bit BF16 Safetensors weights are published in this canonical repository, you can convert them into any target hardware format:

| Target Platform | Recommended Method | Requirements |
| :--- | :--- | :--- |
| **GGUF Custom (`Q2_K`–`Q8_0`, `imatrix`)** | 1-Click Cloud via [**`ggml-org/gguf-my-repo`**](https://huggingface.co/spaces/ggml-org/gguf-my-repo) | Zero local setup (runs free on HF Spaces) |
| **WebGPU / Browser (`ONNX q4f16`)** | Run [`converter/lensetek_converter_colab.ipynb`](https://huggingface.co/lensetek/lensetek-edge-ai-agent/blob/main/converter/lensetek_converter_colab.ipynb) | Free Google Colab (T4 GPU / High-RAM) |
| **Apple Silicon (`MLX 4-bit`)** | `mlx_lm.convert --hf-path lensetek/lensetek-edge-loop-3b -q` | macOS M1/M2/M3/M4 |
| **Instant Edge (No Conversion Needed)** | Direct Download from [**`lensetek/lensetek-edge-loop-3b-GGUF`**](https://huggingface.co/lensetek/lensetek-edge-loop-3b-GGUF) | Any CPU / Mini PC / SBC (< 2.5 GB RAM) |
```

> **Catatan Penting:** JANGAN hapus kotak peringatan `> [!IMPORTANT] 🚧 Model Weights Notice` di bagian atas `model_card/README_base.md` sampai bobot `.safetensors` benar-benar selesai diunggah ke Hugging Face!

### 3. Perintah Verifikasi Sprint 3 & Pemeriksaan Keamanan Akhir (WAJIB DIJALANKAN)
```powershell
py -c "
from pathlib import Path
files = ['training/lensetek_train_colab.ipynb', 'converter/lensetek_converter_colab.ipynb', 'converter/README.md', 'model_card/README_base.md']
for f in files:
    p = Path(f)
    assert p.exists(), f'Missing: {f}'
    txt = p.read_text(encoding='utf-8')
    assert 'hf_' not in txt, f'Potential leaked HF token in {f}!'
print('ALL_FILES_EXIST_AND_CREDENTIAL_SAFE: OK')
"
```
**Ekspektasi Lulus:** `ALL_FILES_EXIST_AND_CREDENTIAL_SAFE: OK`.

---

## 🎯 Prompt Siap Pakai untuk Memerintah Gemini 3.8 Flash (Medium)

Anda cukup menyalin prompt berikut satu per satu:

- **Sprint 1:**
  > `Baca PLAN_CONVERTER_FLASH.md bagian SPRINT 1. Jalankan perubahan pada training/lensetek_train_colab.ipynb menggunakan script Python (jangan edit raw JSON), hapus file sementara jika ada, lalu jalankan perintah verifikasi Sprint 1. Jangan lakukan git push.`
- **Sprint 2:**
  > `Baca PLAN_CONVERTER_FLASH.md bagian SPRINT 2. Buat converter/lensetek_converter_colab.ipynb dan converter/README.md, lalu jalankan perintah verifikasi Sprint 2. Jangan lakukan git push.`
- **Sprint 3:**
  > `Baca PLAN_CONVERTER_FLASH.md bagian SPRINT 3. Perbarui model_card/README_base.md sesuai spesifikasi tanpa menghapus notice status unggah bobot, lalu jalankan perintah verifikasi Sprint 3 & cek keamanan kredensial. Jangan lakukan git push.`
