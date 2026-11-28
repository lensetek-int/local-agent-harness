---
license: apache-2.0
base_model: Qwen/Qwen3-1.7B
tags:
  - moe
  - qwen3moe
  - accounting
  - audit
  - tax
  - indonesia
  - gguf
  - lora
  - agentic
language:
  - id
  - en
pipeline_tag: text-generation
---

# Asadeltek Indo Tax & Audit MoE (`Qwen3-1.7B` MoE & 4 Isolated LoRA)

[Bahasa Indonesia](#bahasa-indonesia) | [English](#english)

---

## Bahasa Indonesia

Repositori ini menyediakan **2 mode deployment** berbasis **`Qwen/Qwen3-1.7B`** untuk **Audit, Akuntansi & Perpajakan Indonesia** (100% offline di CPU laptop maupun VPS tanpa GPU):
* **Plan A (`asadeltek-indo-tax-moe-5b.gguf`, ~2.82 GiB):** 1 file MoE tunggal (`Qwen3MoeForCausalLM`, Top-2 Routing + *Router Calibration*).
* **Plan B (`loras/*.gguf`, masing-masing 34 MB — Direkomendasikan):** Base `Qwen3-1.7B` (`Q4_K_M`, ~1.1 GB) + **4 Isolated LoRA Adapters** dengan *hot-swap* dinamis di `llama-server` (0% pencampuran bobot antar-expert).

### Keahlian LoRA 1 s/d 4 (`loras/`)

| ID (`llama-server`) | File Adapter | Keahlian Utama |
| :---: | :--- | :--- |
| **`0`** | `loras/expert_1_accounting-lora.gguf` | **Akuntansi & Penjurnalan (SAK, SAK-EP, PSAP/BUMD):** LPP loket (pokok & denda), Rekap DRD, jurnal majemuk PPN+PPh 23, persediaan kredit, sewa dibayar dimuka, penyusutan aset tetap, gaji & BPJS, CKPN piutang, reklasifikasi CapEx, uang muka sambungan baru, setor kas, dan beban akrual. |
| **`1`** | `loras/expert_2_audit-lora.gguf` | **Audit, Rasio & Proyeksi Keuangan:** Perhitungan & prosedur audit EBITDA/Margin, Analisis Varians RKAP, Proyeksi Proforma, Rekonsiliasi Bank (DIT/OSC/jasa giro), Current Ratio, DER, DSCR, Efisiensi Penagihan BUMD, dan Materialitas Audit SA 320. |
| **`2`** | `loras/expert_3_tax_id-lora.gguf` | **Perpajakan Indonesia Lengkap (UU HPP, PMK 131/2024, PP 58/2023):** PPN 12% x DPP Nilai Lain 11/12 & Barang Mewah, PPh 23 (NPWP vs non-NPWP), PPh 4(2) Final (sewa & UMKM 0,5%), PPh 22 pengadaan, PPh 21 TER (A/B/C), Koreksi Fiskal PPh Badan 22%, dan Ekualisasi Omzet PPN-PPh. |
| **`3`** | `loras/expert_4_agentic-lora.gguf` | **Agentic Tool-Caller & Python Calc:** Pemanggilan tool JSON aman (`list_client_files`, `inspect_excel_template`, `write_excel_preserving_template`, `read_document_or_ocr`, `rwed_file`, `run_sqlite_query`, `verify_accounting_balance`, `build_non_html_dashboard`, `run_python_calc`). |

### Hasil Uji Perbandingan (8 Sampel Held-Out, Skema JSON Ketat)
| Model | Lulus | Akurasi |
| :--- | :---: | :---: |
| **Model Asal:** `Qwen/Qwen3-1.7B` (`Q4_K_M`, tanpa fine-tune) | 0 / 8 | 0.0% |
| **Model Asal:** `Qwen/Qwen2.5-Coder-3B-Instruct` (`Q4_K_M`, tanpa fine-tune) | 0 / 8 | 0.0% |
| **Plan A:** `asadeltek-indo-tax-moe-5b.gguf` (`Qwen3-MoE` + Router Calibration) | 2 / 8 | 25.0% |
| **Plan B:** `Qwen/Qwen3-1.7B` (`Q4_K_M`) + 4 Isolated LoRA GGUF | 6 / 8 | 75.0% *(100% di Audit & Pajak)* |
| **Plan C (Varian Unified 3B):** [`lensetek/asadeltek-indo-tax-3b`](https://huggingface.co/lensetek/asadeltek-indo-tax-3b) (`asadeltek-indo-tax-3b.gguf`) | **8 / 8** | **100.0%** *(+ 9/12 uji Python AST)* |

> **Varian Unified 3B:** Jika kamu menginginkan **1 file GGUF tunggal** tanpa *hot-swap* LoRA dengan akurasi **100%** pada keempat domain, gunakan [`lensetek/asadeltek-indo-tax-3b`](https://huggingface.co/lensetek/asadeltek-indo-tax-3b) (`asadeltek-indo-tax-3b.gguf`). Pilih varian di repo ini (**Plan B**) jika kamu membutuhkan jejak RAM lebih kecil (~1.3 GB) dengan arsitektur multi-LoRA.

### Cara Menjalankan (`llama.cpp`)

#### Opsi 1: Plan B — Muat Semua 4 LoRA dengan Hot-Swap Dinamis (Paling Akurat)
```bash
# Unduh base model (~1.1 GB) dan 4 LoRA adapter (~134 MB)
huggingface-cli download unsloth/Qwen3-1.7B-GGUF Qwen3-1.7B-Q4_K_M.gguf --local-dir .
huggingface-cli download lensetek/asadeltek-indo-tax-moe-5b --include "loras/*" --local-dir .

# Jalankan 1 server dengan semua LoRA siap hot-swap
./llama-server -m Qwen3-1.7B-Q4_K_M.gguf \
  --lora loras/expert_1_accounting-lora.gguf,loras/expert_2_audit-lora.gguf,loras/expert_3_tax_id-lora.gguf,loras/expert_4_agentic-lora.gguf \
  --lora-init-without-apply \
  --host 127.0.0.1 --port 8080 -c 4096 -t 4
```

Aktifkan LoRA sesuai tugas sebelum mengirim prompt (contoh: aktifkan `id: 2` untuk **Pajak Indonesia**):
```bash
curl -X POST http://127.0.0.1:8080/lora-adapters \
  -H "Content-Type: application/json" \
  -d '[{"id": 0, "scale": 0.0}, {"id": 1, "scale": 0.0}, {"id": 2, "scale": 1.0}, {"id": 3, "scale": 0.0}]'
```

*(Opsional: jika ingin menggabungkan semua LoRA aktif bersamaan tanpa hot-swap, gunakan `--lora-scaled loras/expert_1_accounting-lora.gguf:0.25,loras/expert_2_audit-lora.gguf:0.25,loras/expert_3_tax_id-lora.gguf:0.25,loras/expert_4_agentic-lora.gguf:0.25`.)*

#### Opsi 2: Plan A — File MoE Tunggal
```bash
huggingface-cli download lensetek/asadeltek-indo-tax-moe-5b asadeltek-indo-tax-moe-5b.gguf --local-dir .
./llama-server -m asadeltek-indo-tax-moe-5b.gguf --host 127.0.0.1 --port 8080 -c 4096 -t 4
```

---

## English

This repository provides **two offline deployment modes** built on **`Qwen/Qwen3-1.7B`** for **Indonesian Audit, Accounting & Taxation** (runs 100% offline on CPU-only laptops or GPU-less VPS instances):
* **Plan A (`asadeltek-indo-tax-moe-5b.gguf`, ~2.82 GiB):** Single-file `Qwen3MoeForCausalLM` (Top-2 Routing + *Router Calibration*).
* **Plan B (`loras/*.gguf`, 34 MB each — Recommended):** Lightweight `Qwen3-1.7B` (`Q4_K_M`, ~1.1 GB) base + **4 Isolated LoRA Adapters** with dynamic hot-swapping in `llama-server` (0% cross-expert weight interference).

### LoRA 1–4 Specialties (`loras/`)

| ID (`llama-server`) | Adapter File | Core Capabilities |
| :---: | :--- | :--- |
| **`0`** | `loras/expert_1_accounting-lora.gguf` | **Accounting & Journaling (SAK, SAK-EP, PSAP/BUMD):** Cashier receipts, water billing accruals (DRD), compound VAT+WHT journals, inventory, prepaid rent, depreciation, payroll & BPJS, bad debt allowance, CapEx reclassification, and accrued expenses. |
| **`1`** | `loras/expert_2_audit-lora.gguf` | **Audit, Ratios & Financial Projections:** EBITDA & Margin, RKAP budget variance analysis, Pro Forma projections, Bank Reconciliation, Current Ratio, DER, DSCR, collection efficiency, and SA 320 Audit Materiality. |
| **`2`** | `loras/expert_3_tax_id-lora.gguf` | **Indonesian Taxation (UU HPP, PMK 131/2024, PP 58/2023):** VAT 12% on 11/12 tax base & luxury goods, Art. 23 WHT (with/without NPWP), Art. 4(2) Final Tax, Art. 22, Art. 21 TER (A/B/C), Corporate Tax Fiscal Reconciliation (22%), and VAT-CIT Equalization. |
| **`3`** | `loras/expert_4_agentic-lora.gguf` | **Agentic Tool-Caller & Python Calc:** Safe JSON tool invocation (`list_client_files`, `inspect_excel_template`, `write_excel_preserving_template`, `read_document_or_ocr`, `rwed_file`, `run_sqlite_query`, `verify_accounting_balance`, `build_non_html_dashboard`, `run_python_calc`). |

### Held-Out Benchmark Comparison (8 Samples, Strict JSON Schema)
| Model | Passed | Accuracy |
| :--- | :---: | :---: |
| **Base:** `Qwen/Qwen3-1.7B` (`Q4_K_M`, zero-shot) | 0 / 8 | 0.0% |
| **Base:** `Qwen/Qwen2.5-Coder-3B-Instruct` (`Q4_K_M`, zero-shot) | 0 / 8 | 0.0% |
| **Plan A:** `asadeltek-indo-tax-moe-5b.gguf` (`Qwen3-MoE` + Router Calibration) | 2 / 8 | 25.0% |
| **Plan B:** `Qwen/Qwen3-1.7B` (`Q4_K_M`) + 4 Isolated LoRA GGUFs | 6 / 8 | 75.0% *(100% on Audit & Tax)* |
| **Plan C (Sister Repo):** [`lensetek/asadeltek-indo-tax-3b`](https://huggingface.co/lensetek/asadeltek-indo-tax-3b) (`asadeltek-indo-tax-3b.gguf`) | **8 / 8** | **100.0%** *(+ 9/12 Python AST eval)* |

> **Sister Repo (`Unified 3B`):** If you prefer a **single GGUF file** without LoRA hot-swapping and **100%** accuracy across all 4 domains, see [`lensetek/asadeltek-indo-tax-3b`](https://huggingface.co/lensetek/asadeltek-indo-tax-3b) (`asadeltek-indo-tax-3b.gguf`). Choose this repo (**Plan B**) for a smaller RAM footprint (~1.3 GB) with isolated multi-LoRA switching.

### Quick Start (`llama.cpp` Multi-LoRA Hot-Swap — Plan B)
```bash
huggingface-cli download unsloth/Qwen3-1.7B-GGUF Qwen3-1.7B-Q4_K_M.gguf --local-dir .
huggingface-cli download lensetek/asadeltek-indo-tax-moe-5b --include "loras/*" --local-dir .

./llama-server -m Qwen3-1.7B-Q4_K_M.gguf \
  --lora loras/expert_1_accounting-lora.gguf,loras/expert_2_audit-lora.gguf,loras/expert_3_tax_id-lora.gguf,loras/expert_4_agentic-lora.gguf \
  --lora-init-without-apply \
  --host 127.0.0.1 --port 8080 -c 4096 -t 4
```

Activate a specific LoRA before sending a request (e.g., `id: 2` for **Indonesian Tax**):
```bash
curl -X POST http://127.0.0.1:8080/lora-adapters \
  -H "Content-Type: application/json" \
  -d '[{"id": 0, "scale": 0.0}, {"id": 1, "scale": 0.0}, {"id": 2, "scale": 1.0}, {"id": 3, "scale": 0.0}]'
```
