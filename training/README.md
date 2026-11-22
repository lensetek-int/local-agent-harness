# 🚀 Panduan Eksekusi Training Model di RunPod (~$1.00 USD)

Dokumen ini berisi panduan langkah-demi-langkah menyewa GPU di **RunPod** untuk melatih model **`Lensetek-Edge-Loop-3B`** dan secara otomatis mengunggah hasilnya ke repositori Hugging Face resmi.

---

## 💰 Estimasi Biaya & Spesifikasi Hardware

* **GPU**: NVIDIA RTX 4090 (24 GB VRAM)
* **Tarif Sewa**: **~$0.34 – $0.39 / jam** (*Community Cloud*)
* **Durasi Training**: **~1.5 – 2 jam** untuk 3.000 sampel ChatML
* **Total Biaya**: **~$0.70 – $1.00 USD** (Sangat hemat, jauh di bawah batas anggaran $10 USD!)

---

## 📋 Langkah-demi-Langkah Eksekusi di RunPod

### 1. Buka Akun RunPod & Deploy Pod
1. Masuk ke [RunPod.io](https://runpod.io) dan isi saldo minimal **$5 – $10 USD**.
2. Masuk ke menu **Pods** -> **Deploy New Pod**.
3. Pilih GPU: **1x RTX 4090** (24 GB VRAM).
4. Pilih Template: **RunPod PyTorch 2.4 / 2.2** (atau Ubuntu CUDA 12.1).
5. Klik **Deploy**.

---

### 2. Buka Web Terminal / JupyterLab
Setelah Pod menyala (status *Running*):
1. Klik tombol **Connect** -> **Connect to Web Terminal** (atau via SSH).
2. Di terminal RunPod, jalankan perintah untuk mengunduh dataset dan skrip:

```bash
# Clone repositori aplikasi
git clone https://huggingface.co/lensetek/lensetek-edge-ai-agent
cd lensetek-edge-ai-agent/training
```

---

### 3. Masukkan Token Hugging Face & Jalankan Training
Masukkan token write Hugging Face Anda, lalu jalankan skrip otomatis:

```bash
# Export token Hugging Face (wajib memiliki izin WRITE)
export HF_TOKEN="hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# Jalankan skrip setup & training 1-perintah
bash runpod_setup.sh
```

---

### 4. Hasil Otomatis (Setelah Training Selesai)
Skrip akan otomatis:
1. Menggabungkan bobot LoRA ke presisi 16-bit asli dan mengunggah ke:  
   👉 **`lensetek/lensetek-edge-loop-3b`** (Safetensors).
2. Mengonversi bobot ke kuantisasi 4-bit dan mengunggah file `.gguf` ke:  
   👉 **`lensetek/lensetek-edge-loop-3b-GGUF`** (`lensetek-edge-loop-3b-q4_k_m.gguf`).
3. Setelah selesai, Anda bisa langsung klik **Stop / Terminate Pod** di RunPod agar saldo tidak berkurang.
