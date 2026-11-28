---
license: apache-2.0
base_model: Qwen/Qwen2.5-Coder-3B-Instruct
tags:
  - accounting
  - audit
  - tax
  - indonesia
  - gguf
  - agentic
  - qwen2.5-coder
  - python-calc
language:
  - id
  - en
pipeline_tag: text-generation
---

# Asadeltek Indo Tax & Audit 3B (`asadeltek-indo-tax-3b.gguf`)

[Bahasa Indonesia](#bahasa-indonesia) | [English](#english)

---

## Bahasa Indonesia

**`asadeltek-indo-tax-3b.gguf`** adalah model AI **all-in-one (serba bisa dalam 1 file)** berbasis **`Qwen/Qwen2.5-Coder-3B-Instruct`** (`Q4_K_M`, ~1.93 GB) yang dilatih khusus untuk **Akuntansi, Audit Keuangan, Perpajakan Indonesia, Pemanggilan Tool Agentic, serta Penulisan Kode Python (`Decimal`)** agar perhitungan angka dilakukan secara eksak oleh Python. Model ini dapat berjalan **100% offline** di laptop biasa (CPU-only) maupun VPS tanpa GPU.

### Memilih Varian yang Tepat untuk Kebutuhan Kamu
Kami menyediakan 2 repositori model yang saling melengkapi:
* **Model Ini — Unified 3B ([`lensetek/asadeltek-indo-tax-3b`](https://huggingface.co/lensetek/asadeltek-indo-tax-3b)) *(Direkomendasikan)*:**
  * **Paling praktis & paling akurat:** cukup 1 file `asadeltek-indo-tax-3b.gguf` (~1.93 GB) yang langsung menguasai seluruh bidang (Akuntansi, Audit, Pajak Indonesia, dan Agentic Tools + Python `Decimal`) tanpa perlu berganti-ganti adapter.
  * Lulus **8/8 (100.0%)** pada uji format JSON ketat dan **9/12 (75.0%)** pada uji eksekusi kode Python langsung.
* **Varian Ringan MoE & Multi-LoRA ([`lensetek/asadeltek-indo-tax-moe-5b`](https://huggingface.co/lensetek/asadeltek-indo-tax-moe-5b)):**
  * Berbasis `Qwen/Qwen3-1.7B`, menyediakan varian **Multi-LoRA 1.7B** (4 adapter spesialis terpisah ukuran `34 MB/file` yang sangat hemat RAM ~1.3 GB) dan **MoE 5B** (`asadeltek-indo-tax-moe-5b.gguf`).
  * Pilih varian Multi-LoRA jika RAM perangkatmu sangat terbatas (~1.3 GB); pilih **Unified 3B** di repo ini jika ingin kemudahan 1 file dengan akurasi tertinggi.

### Hasil Uji Perbandingan (8 Soal Uji Acak Tersembunyi, Format JSON Ketat)
Seluruh model diuji dengan cara yang sama melalui `llama-server` (`temperature=0.1`) pada 4 bidang (Akuntansi, Audit, Pajak Indonesia, dan Agentic Tools):

| Varian Model | Lulus | Akurasi | Akuntansi | Audit | Pajak ID | Agentic Tools |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Model Dasar:** `Qwen/Qwen3-1.7B` (tanpa fine-tuning) | 0 / 8 | 0.0% | 0/2 | 0/2 | 0/2 | 0/2 |
| **Model Dasar:** `Qwen/Qwen2.5-Coder-3B-Instruct` (tanpa fine-tuning) | 0 / 8 | 0.0% | 0/2 | 0/2 | 0/2 | 0/2 |
| **Varian MoE 5B:** [`asadeltek-indo-tax-moe-5b.gguf`](https://huggingface.co/lensetek/asadeltek-indo-tax-moe-5b) (gabungan 4 pakar) | 2 / 8 | 25.0% | 0/2 | 2/2 | 0/2 | 0/2 |
| **Varian Multi-LoRA 1.7B:** [`Qwen3-1.7B` + 4 LoRA Spesialis](https://huggingface.co/lensetek/asadeltek-indo-tax-moe-5b) | 6 / 8 | 75.0% | 1/2 | 2/2 | 2/2 | 1/2 |
| **Varian Unified 3B (Repo Ini):** `asadeltek-indo-tax-3b.gguf` | **8 / 8** | **100.0%** | **2/2** | **2/2** | **2/2** | **2/2** |

* **Uji Eksekusi Kode Python (`Decimal`):** **9 / 12 (75.0%)** kode Python yang dihasilkan model berhasil dijalankan langsung di sandbox aman dan menghasilkan angka Rupiah yang tepat.

### Cara Menjalankan (`llama.cpp`)
```bash
huggingface-cli download lensetek/asadeltek-indo-tax-3b asadeltek-indo-tax-3b.gguf --local-dir .
./llama-server -m asadeltek-indo-tax-3b.gguf --host 127.0.0.1 --port 8080 -c 4096 -t 4
```

Kode sumber runtime deterministik (`SQLite3`, kalkulator pajak, pembaca/penulis template Excel, OCR, dan Dashboard non-HTML) tersedia di GitHub: [lensetek-int/local-agent-harness](https://github.com/lensetek-int/local-agent-harness).

---

## English

**`asadeltek-indo-tax-3b.gguf`** is an **all-in-one single-file AI model** built on **`Qwen/Qwen2.5-Coder-3B-Instruct`** (`Q4_K_M`, ~1.93 GB), fine-tuned for **Indonesian Accounting, Financial Audit, Taxation, Agentic Tool-Calling, and Python (`Decimal`) Code Generation** so numerical calculations are executed deterministically by Python. It runs **100% offline** on standard CPU-only laptops or GPU-less VPS servers.

### Choosing the Right Variant
We maintain two complementary repositories:
* **This Model — Unified 3B ([`lensetek/asadeltek-indo-tax-3b`](https://huggingface.co/lensetek/asadeltek-indo-tax-3b)) *(Recommended)*:**
  * **Simplest & most accurate:** a single `asadeltek-indo-tax-3b.gguf` file (~1.93 GB) covering all four domains (Accounting, Audit, Indonesian Tax, and Agentic Tools + Python `Decimal`) with no adapter switching required.
  * Scored **8/8 (100.0%)** on strict JSON schema evaluation and **9/12 (75.0%)** on live Python AST sandbox execution.
* **Lightweight MoE & Multi-LoRA Variant ([`lensetek/asadeltek-indo-tax-moe-5b`](https://huggingface.co/lensetek/asadeltek-indo-tax-moe-5b)):**
  * Built on `Qwen/Qwen3-1.7B`, offering **Multi-LoRA 1.7B** (4 isolated `34 MB` specialist adapters using ~1.3 GB RAM total) and **MoE 5B** (`asadeltek-indo-tax-moe-5b.gguf`).
  * Choose Multi-LoRA 1.7B for ultra-tight RAM (~1.3 GB); choose **Unified 3B** here for single-file simplicity and top accuracy.

### Benchmark Comparison (8 Held-Out Samples, Strict JSON Schema)
| Model Variant | Passed | Accuracy | Accounting | Audit | Tax ID | Agentic Tools |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Base Model:** `Qwen/Qwen3-1.7B` (zero-shot) | 0 / 8 | 0.0% | 0/2 | 0/2 | 0/2 | 0/2 |
| **Base Model:** `Qwen/Qwen2.5-Coder-3B-Instruct` (zero-shot) | 0 / 8 | 0.0% | 0/2 | 0/2 | 0/2 | 0/2 |
| **MoE 5B:** [`asadeltek-indo-tax-moe-5b.gguf`](https://huggingface.co/lensetek/asadeltek-indo-tax-moe-5b) (merged 4-expert MoE) | 2 / 8 | 25.0% | 0/2 | 2/2 | 0/2 | 0/2 |
| **Multi-LoRA 1.7B:** [`Qwen3-1.7B` + 4 Specialist LoRAs](https://huggingface.co/lensetek/asadeltek-indo-tax-moe-5b) | 6 / 8 | 75.0% | 1/2 | 2/2 | 2/2 | 1/2 |
| **Unified 3B (This Repo):** `asadeltek-indo-tax-3b.gguf` | **8 / 8** | **100.0%** | **2/2** | **2/2** | **2/2** | **2/2** |

### Quick Start (`llama.cpp`)
```bash
huggingface-cli download lensetek/asadeltek-indo-tax-3b asadeltek-indo-tax-3b.gguf --local-dir .
./llama-server -m asadeltek-indo-tax-3b.gguf --host 127.0.0.1 --port 8080 -c 4096 -t 4
```

Deterministic runtime tools (`SQLite3`, tax calculator, Excel template reader/writer, offline OCR, and non-HTML dashboards) are available on GitHub: [lensetek-int/local-agent-harness](https://github.com/lensetek-int/local-agent-harness).
