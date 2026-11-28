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

**`asadeltek-indo-tax-3b.gguf`** (**Plan C — Unified Dense 3B**) adalah model tunggal berbasis **`Qwen/Qwen2.5-Coder-3B-Instruct`** (`Q4_K_M`, ~1.9 GB) yang dilatih *jointly* pada **6.480 sampel** untuk **Audit, Akuntansi, Perpajakan Indonesia, Agentic Tool-Calling, serta Perhitungan Python `Decimal` (`run_python_calc`)** — berjalan 100% offline di laptop CPU-only maupun VPS tanpa GPU.

### Perbandingan dengan Varian Lain (`lensetek/asadeltek-indo-tax-moe-5b`)
* **Model Ini ([`lensetek/asadeltek-indo-tax-3b`](https://huggingface.co/lensetek/asadeltek-indo-tax-3b)):**
  * **1 file GGUF tunggal** (`asadeltek-indo-tax-3b.gguf`), langsung menguasai keempat domain + menulis kode Python `Decimal` (`run_python_calc`) tanpa perlu *hot-swap* LoRA.
  * Mencapai **8/8 (100.0%)** pada evaluasi held-out skema JSON ketat dan **9/12 (75.0%)** pada uji eksekusi kode Python nyata di sandbox AST.
* **Varian MoE & Multi-LoRA ([`lensetek/asadeltek-indo-tax-moe-5b`](https://huggingface.co/lensetek/asadeltek-indo-tax-moe-5b)):**
  * Berbasis `Qwen/Qwen3-1.7B`, menyediakan **Plan A** (MoE 5B `asadeltek-indo-tax-moe-5b.gguf`, 25.0%) dan **Plan B** (4 *Isolated LoRA GGUF* `34 MB/file`, 75.0% dengan *hot-swap* `POST /lora-adapters` pada ~1.3 GB RAM).
  * Pilih `moe-5b` (Plan B) jika RAM sangat ketat (~1.3 GB) dan menggunakan arsitektur estafet multi-LoRA; pilih **`asadeltek-indo-tax-3b.gguf`** jika ingin **1 model tunggal dengan akurasi 100% di keempat domain**.

### Hasil Uji Perbandingan Lengkap (8 Sampel Held-Out, Skema JSON Ketat)
Diuji seragam via `llama-server` (`temperature=0.1`) pada `eval_heldout_200.jsonl` (2 sampel per expert):

| Model | Total Lulus | Akurasi | Expert 1 (Accounting) | Expert 2 (Audit) | Expert 3 (Tax ID) | Expert 4 (Agentic) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Base:** `Qwen/Qwen3-1.7B` (`Q4_K_M`, tanpa fine-tune) | 0 / 8 | 0.0% | 0/2 | 0/2 | 0/2 | 0/2 |
| **Base:** `Qwen/Qwen2.5-Coder-3B-Instruct` (`Q4_K_M`, tanpa fine-tune) | 0 / 8 | 0.0% | 0/2 | 0/2 | 0/2 | 0/2 |
| **Plan A:** [`asadeltek-indo-tax-moe-5b.gguf`](https://huggingface.co/lensetek/asadeltek-indo-tax-moe-5b) (`Qwen3-MoE` + Router Calibration) | 2 / 8 | 25.0% | 0/2 | 2/2 | 0/2 | 0/2 |
| **Plan B:** [`Qwen3-1.7B` + 4 Isolated LoRA GGUF](https://huggingface.co/lensetek/asadeltek-indo-tax-moe-5b) | 6 / 8 | 75.0% | 1/2 | 2/2 | 2/2 | 1/2 |
| **Plan C (Repo Ini):** `asadeltek-indo-tax-3b.gguf` (`Unified 6.48K`) | **8 / 8** | **100.0%** | **2/2** | **2/2** | **2/2** | **2/2** |

* **Uji Eksekusi Python Nyata (`eval_python_calc_24.jsonl`, 12 domain kalkulasi):** **9 / 12 (75.0%)** lulus eksekusi AST sandbox & cocok nilai Rupiah `Decimal` hingga satuan rupiah.

### Quick Start (`llama.cpp`)
```bash
huggingface-cli download lensetek/asadeltek-indo-tax-3b asadeltek-indo-tax-3b.gguf --local-dir .
./llama-server -m asadeltek-indo-tax-3b.gguf --host 127.0.0.1 --port 8080 -c 4096 -t 4
```

Kode sumber runtime deterministik (`SQLite3`, `tax_engine.py`, `tools.py`, `ocr.py`, `dashboard.py`) tersedia di GitHub: [lensetek-int/local-agent-harness](https://github.com/lensetek-int/local-agent-harness).

---

## English

**`asadeltek-indo-tax-3b.gguf`** (**Plan C — Unified Dense 3B**) is a single unified model built on **`Qwen/Qwen2.5-Coder-3B-Instruct`** (`Q4_K_M`, ~1.9 GB), jointly fine-tuned on **6,480 curated samples** for **Indonesian Audit, Accounting, Taxation, Agentic Tool-Calling, and Python `Decimal` Calculation (`run_python_calc`)** — running 100% offline on CPU-only laptops or GPU-less VPS instances.

### Relationship with Sister Repo (`lensetek/asadeltek-indo-tax-moe-5b`)
* **This Repo ([`lensetek/asadeltek-indo-tax-3b`](https://huggingface.co/lensetek/asadeltek-indo-tax-3b)):**
  * **Single GGUF file** (`asadeltek-indo-tax-3b.gguf`) handling all 4 domains plus Python `Decimal` code generation (`run_python_calc`) without LoRA hot-swapping.
  * Achieved **8/8 (100.0%)** on strict JSON schema held-out evaluation and **9/12 (75.0%)** on live Python AST sandbox execution.
* **Sister Repo ([`lensetek/asadeltek-indo-tax-moe-5b`](https://huggingface.co/lensetek/asadeltek-indo-tax-moe-5b)):**
  * Built on `Qwen/Qwen3-1.7B`, providing **Plan A** (5B MoE `asadeltek-indo-tax-moe-5b.gguf`, 25.0%) and **Plan B** (4 Isolated LoRA GGUFs `34 MB/file`, 75.0% via `POST /lora-adapters` hot-swap in ~1.3 GB RAM).
  * Choose `moe-5b` (Plan B) for ultra-tight RAM (~1.3 GB) with multi-LoRA orchestration; choose **`asadeltek-indo-tax-3b.gguf`** for a **single-file model with 100% held-out schema accuracy**.

### Full Benchmark Comparison (8 Held-Out Samples, Strict JSON Schema)
| Model | Passed | Accuracy | Accounting | Audit | Tax ID | Agentic |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Base:** `Qwen/Qwen3-1.7B` (`Q4_K_M`, zero-shot) | 0 / 8 | 0.0% | 0/2 | 0/2 | 0/2 | 0/2 |
| **Base:** `Qwen/Qwen2.5-Coder-3B-Instruct` (`Q4_K_M`, zero-shot) | 0 / 8 | 0.0% | 0/2 | 0/2 | 0/2 | 0/2 |
| **Plan A:** [`asadeltek-indo-tax-moe-5b.gguf`](https://huggingface.co/lensetek/asadeltek-indo-tax-moe-5b) (`Qwen3-MoE`) | 2 / 8 | 25.0% | 0/2 | 2/2 | 0/2 | 0/2 |
| **Plan B:** [`Qwen3-1.7B` + 4 Isolated LoRA GGUFs](https://huggingface.co/lensetek/asadeltek-indo-tax-moe-5b) | 6 / 8 | 75.0% | 1/2 | 2/2 | 2/2 | 1/2 |
| **Plan C (This Repo):** `asadeltek-indo-tax-3b.gguf` (`Unified 6.48K`) | **8 / 8** | **100.0%** | **2/2** | **2/2** | **2/2** | **2/2** |

### Quick Start (`llama.cpp`)
```bash
huggingface-cli download lensetek/asadeltek-indo-tax-3b asadeltek-indo-tax-3b.gguf --local-dir .
./llama-server -m asadeltek-indo-tax-3b.gguf --host 127.0.0.1 --port 8080 -c 4096 -t 4
```

Deterministic runtime tools (`SQLite3`, `tax_engine.py`, `tools.py`, `ocr.py`, `dashboard.py`) are available on GitHub: [lensetek-int/local-agent-harness](https://github.com/lensetek-int/local-agent-harness).
