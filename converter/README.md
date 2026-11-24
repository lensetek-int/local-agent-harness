# 🔄 Lensetek Model Converter Toolkit

Toolkit ini dirancang agar pengguna dan developer dapat mengonversi bobot dasar 16-bit (**[`lensetek/lensetek-edge-loop-3b`](https://huggingface.co/lensetek/lensetek-edge-loop-3b)**) ke berbagai varian arsitektur dan format target hardware secara mandiri.

---

## 🚀 Pilihan Metode Konversi Mandiri

### 1. Konversi GGUF 1-Klik Tanpa Kode (Hugging Face Spaces)
Jika Anda hanya membutuhkan varian kuantisasi GGUF khusus (`Q2_K`, `Q3_K_M`, `Q5_K_M`, `Q6_K`, `Q8_0`) tanpa perlu menjalankan kode atau GPU sendiri:
1. Buka Hugging Face Space resmi: [**`ggml-org/gguf-my-repo`**](https://huggingface.co/spaces/ggml-org/gguf-my-repo).
2. Masukkan model ID sumber: `lensetek/lensetek-edge-loop-3b`.
3. Pilih metode kuantisasi yang diinginkan dan klik **Submit**.
4. Hasil kuantisasi GGUF akan otomatis dibuat dan tersimpan langsung di profil Hugging Face Anda.

---

### 2. Konversi Multi-Format via Google Colab (`lensetek_converter_colab.ipynb`)
Untuk konversi ke **WebGPU (Browser)**, **Apple Silicon (MLX)**, atau **GGUF Custom**:
1. Buka notebook [`lensetek_converter_colab.ipynb`](lensetek_converter_colab.ipynb) di Google Colab.
2. Pilih runtime GPU T4 gratis (*Runtime → Change runtime type → T4 GPU*).
3. Pilih format target pada form interaktif:
   * **`gguf`**: Menghasilkan berkas `.gguf` siap pakai dengan kompilasi otomatis `llama.cpp`.
   * **`webgpu_onnx`**: Menghasilkan folder model ONNX terkuantisasi `q4f16` untuk dijalankan langsung di browser menggunakan **Transformers.js v3**.
   * **`mlx_guide`**: Menghasilkan panduan konversi 1-baris untuk Mac M1/M2/M3/M4.
4. Jalankan sel berurutan, lalu unduh berkas hasil atau upload otomatis ke repo Hugging Face pribadi Anda.

---

### 3. Apple Silicon (macOS Terminal)
Jika Anda menggunakan Mac dengan chip Apple Silicon (M1/M2/M3/M4):
```bash
pip install -U mlx-lm
mlx_lm.convert --hf-path lensetek/lensetek-edge-loop-3b --mlx-path ./lensetek-edge-loop-3b-mlx-4bit -q --q-bits 4
```

---

## ⚡ Jalur Cepat (Tanpa Konversi)
Jika Anda membutuhkan model 4-bit yang langsung siap jalan (*ready-to-run*) di perangkat Edge, Mini PC, atau laptop dengan RAM hemat (< 2.5 GB), Anda **tidak perlu melakukan konversi**. Cukup unduh langsung dari repositori resmi:
👉 **[`lensetek/lensetek-edge-loop-3b-GGUF`](https://huggingface.co/lensetek/lensetek-edge-loop-3b-GGUF)** (`lensetek-edge-loop-3b-q4_k_m.gguf` ~1.93 GB).
