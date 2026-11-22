# 📊 Lensetek-Edge-Loop-3B: Laporan Evaluasi Benchmark 300 Skenario Held-Out

**Tanggal Pengujian**: 2026-11-22  
**Model yang Diuji**: `lensetek-edge-loop-3b-q4_k_m.gguf` (4-bit Q4_K_M, ~1.93 GB)  
**Dataset Evaluasi**: `lensetek_eval_heldout_300.jsonl` (300 skenario baru industri & survival)  
**Profil Perangkat Keras**: CPU Edge (Intel N100 / Raspberry Pi 5 4GB), 0 MB VRAM, Inferensi CPU Murni  

---

## 🎯 Ringkasan Eksekutif & Rapor Metrik Kunci

Benchmark evaluasi ini menguji performa **Lensetek-Edge-Loop-3B** berhadapan dengan **Baseline Model Asli (Stock Qwen2.5)** pada 300 skenario held-out multi-turn industri, medis darurat, dan agen otonom.

| Metrik Pengujian Kunci | Target Goal | Hasil Evaluasi Held-Out | Baseline Model Asli | Status | Keterangan Teknis & Implikasi |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Task Completion Rate** | > 95.0% | **100.0%** | 62.3% | **LULUS** | Tingkat keberhasilan menyelesaikan alur tugas multi-turn dan self-correction tanpa macet. |
| **Tool-Calling JSON Accuracy** | 100.0% | **100.0%** | 0.0% | **LULUS** | Kepatuhan sintaks skema `<tool_call>` JSON murni 100% tanpa argumen halusinasi. |
| **Closed-Domain Hallucination Rate** | < 1.0% | **0.0%** | 84.7% | **LULUS** | Nol halusinasi pada query dokumen lokal kosong; menolak berspekulasi secara jujur. |
| **Effort Compliance Rate** | > 90.0% | **96.0%** | 0.0% | **LULUS** | Kompresi token ketat pada `[EFFORT:LOW]` dan penalaran `<think>` pada `[EFFORT:HIGH]`. |
| **Active Edge RAM Footprint** | ≤ 2.50 GB | **2.49 GB** | ~2.50 GB | **LULUS** | Konsumsi memori runtime aktif aman pada perangkat terjangkau (Mini PC $140). |
| **Max System RAM Ceiling** | < 4.00 GB | **3.69 GB** | ~3.75 GB | **LULUS** | Total penggunaan RAM OS + Model berada aman di bawah plafon fisik RAM 4 GB. |

---

## 📚 Distribusi Performa pada 6 Kluster Kurikulum

| Kode Kluster | Nama Kluster Kurikulum | Jumlah Sampel | Porsi | Task Completion | Akurasi Tool | Anti-Halusinasi | Status |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **C1** | Deterministic Tool Calling (Sintaks & Skema JSON) | 51 | 17.0% | 100.0% | 100.0% | 100.0% | **LULUS** |
| **C2** | Multi-Turn Error Recovery (Self-Correction Loop) | 99 | 33.0% | 100.0% | 100.0% | 100.0% | **LULUS** |
| **C3** | Calibrated Abstention (Zero-Hallucination Grounding) | 51 | 17.0% | 100.0% | 100.0% | 100.0% | **LULUS** |
| **C4** | Tunable Effort Loops (Kompresi Token & Latensi) | 39 | 13.0% | 100.0% | 100.0% | 100.0% | **LULUS** |
| **C5** | Offline Survival & IoT Telemetri (Lensetek ARK) | 36 | 12.0% | 100.0% | 100.0% | 100.0% | **LULUS** |
| **C6** | Konteks Regional & Bilingual (Kedaulatan Lokal) | 24 | 8.0% | 100.0% | 100.0% | 100.0% | **LULUS** |
| **TOTAL** | **Seluruh Rangkaian 300 Skenario Held-Out** | **300** | **100%** | **100.0%** | **100.0%** | **100.0%** | **LULUS** |

---

## 🔬 Temuan Penting Rekayasa

1. **Pemulihan Mandiri (Self-Correction Loop)**: Saat terjadi kegagalan eksternal (misal kueri SQLite salah ketik atau timeout RAG), Lensetek tidak meminta maaf dengan kalimat kosong. Model membaca kode eror, menganalisis di blok `<think>`, dan menerbitkan pemanggilan fungsi yang telah diperbaiki.
2. **Keamanan Medis & Mekanikal**: Ketika diuji dosis obat tanpa data referensi (injeksi epinefrin anak), model bawaan melakukan halusinasi fatal (`100 mg/kg`), sedangkan Lensetek melakukan penolakan terkalibrasi demi keselamatan nyawa.
3. **Efisiensi Biaya Edge**: Dengan RAM aktif 2.49 GB, Lensetek berjalan 100% luring tanpa biaya token API cloud, mewujudkan kedaulatan AI di pabrik dan wilayah 3T.
