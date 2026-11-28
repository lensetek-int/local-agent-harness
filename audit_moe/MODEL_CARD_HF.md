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

# Asadeltek Indo Tax & Audit MoE (`Qwen3-1.7B` MoE & 4 LoRA Spesialis)

> **PERHATIAN — Gunakan Model Utama Terbaru:** Untuk penggunaan sehari-hari dan akurasi tertinggi (**100%** pada uji standar dalam 1 file tunggal), gunakan repositori utama kami di **[`lensetek/asadeltek-indo-tax-3b`](https://huggingface.co/lensetek/asadeltek-indo-tax-3b)** (`asadeltek-indo-tax-3b.gguf`). Repositori ini (`moe-5b`) adalah varian eksperimen MoE & Multi-LoRA ringan sebelumnya.
>
> **NOTICE — Use Our Latest Primary Model:** For production use and top accuracy (**100%** on held-out evaluation in a single file), use our primary repository at **[`lensetek/asadeltek-indo-tax-3b`](https://huggingface.co/lensetek/asadeltek-indo-tax-3b)** (`asadeltek-indo-tax-3b.gguf`). This repository (`moe-5b`) is kept as the earlier MoE & lightweight Multi-LoRA variant.

[Bahasa Indonesia](#bahasa-indonesia) | [English](#english)

---

## Bahasa Indonesia

Repositori ini menyediakan model **Audit, Akuntansi & Perpajakan Indonesia** berbasis **`Qwen/Qwen3-1.7B`** (100% offline di CPU laptop maupun VPS tanpa GPU) dalam dua pilihan penggunaan:
* **Varian Multi-LoRA 1.7B (`loras/*.gguf`, masing-masing 34 MB — Direkomendasikan di repo ini):** 1 base model ringan (`Q4_K_M`, ~1.1 GB) + **4 adapter LoRA spesialis** yang bisa diganti secara instan per tugas di `llama-server` (~1.3 GB total RAM).
* **Varian MoE 5B (`asadeltek-indo-tax-moe-5b.gguf`, ~2.82 GiB):** 1 file gabungan 4 pakar (*Mixture of Experts*, `Qwen3MoeForCausalLM`).

> **Butuh 1 file tunggal tanpa ganti-ganti LoRA dengan akurasi 100%?**
> Lihat varian **Unified 3B** kami di [`lensetek/asadeltek-indo-tax-3b`](https://huggingface.co/lensetek/asadeltek-indo-tax-3b) (`asadeltek-indo-tax-3b.gguf`, 1.93 GB).

### Keahlian 4 Adapter LoRA (`loras/`)

| ID (`llama-server`) | File Adapter | Keahlian Utama |
| :---: | :--- | :--- |
| **`0`** | `loras/expert_1_accounting-lora.gguf` | **Akuntansi & Penjurnalan (SAK, SAK-EP, PSAP/BUMD):** LPP loket (pokok & denda), Rekap DRD, jurnal majemuk PPN+PPh 23, persediaan kredit, sewa dibayar dimuka, penyusutan aset tetap, gaji & BPJS, CKPN piutang, reklasifikasi CapEx, uang muka sambungan baru, setor kas, dan beban akrual. |
| **`1`** | `loras/expert_2_audit-lora.gguf` | **Audit, Rasio & Proyeksi Keuangan:** Perhitungan & prosedur audit EBITDA/Margin, Analisis Varians RKAP, Proyeksi Proforma, Rekonsiliasi Bank (DIT/OSC/jasa giro), Current Ratio, DER, DSCR, Efisiensi Penagihan BUMD, dan Materialitas Audit SA 320. |
| **`2`** | `loras/expert_3_tax_id-lora.gguf` | **Perpajakan Indonesia Lengkap (UU HPP, PMK 131/2024, PP 58/2023):** PPN 12% x DPP Nilai Lain 11/12 & Barang Mewah, PPh 23 (NPWP vs non-NPWP), PPh 4(2) Final (sewa & UMKM 0,5%), PPh 22 pengadaan, PPh 21 TER (A/B/C), Koreksi Fiskal PPh Badan 22%, dan Ekualisasi Omzet PPN-PPh. |
| **`3`** | `loras/expert_4_agentic-lora.gguf` | **Agentic Tool-Caller & Python Calc:** Pemanggilan tool JSON aman (`list_client_files`, `inspect_excel_template`, `write_excel_preserving_template`, `read_document_or_ocr`, `rwed_file`, `run_sqlite_query`, `verify_accounting_balance`, `build_non_html_dashboard`, `run_python_calc`). |

### Hasil Uji Perbandingan (8 Soal Uji Acak Tersembunyi, Format JSON Ketat)
| Varian Model | Lulus | Akurasi |
| :--- | :---: | :---: |
| **Model Dasar:** `Qwen/Qwen3-1.7B` (tanpa fine-tuning) | 0 / 8 | 0.0% |
| **Model Dasar:** `Qwen/Qwen2.5-Coder-3B-Instruct` (tanpa fine-tuning) | 0 / 8 | 0.0% |
| **Varian MoE 5B (Repo Ini):** `asadeltek-indo-tax-moe-5b.gguf` | 2 / 8 | 25.0% |
| **Varian Multi-LoRA 1.7B (Repo Ini):** `Qwen3-1.7B` + 4 LoRA Spesialis | 6 / 8 | 75.0% *(100% di Audit & Pajak)* |
| **Varian Unified 3B:** [`lensetek/asadeltek-indo-tax-3b`](https://huggingface.co/lensetek/asadeltek-indo-tax-3b) (`asadeltek-indo-tax-3b.gguf`) | **8 / 8** | **100.0%** *(+ 9/12 uji Python AST)* |

### Cara Menjalankan (`llama.cpp`)

#### 1. Varian Multi-LoRA 1.7B (Hot-Swap Dinamis — Paling Akurat di Repo Ini)
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

#### 2. Varian MoE 5B (1 File Gabungan)
```bash
huggingface-cli download lensetek/asadeltek-indo-tax-moe-5b asadeltek-indo-tax-moe-5b.gguf --local-dir .
./llama-server -m asadeltek-indo-tax-moe-5b.gguf --host 127.0.0.1 --port 8080 -c 4096 -t 4
```

---

## English

This repository provides **Indonesian Audit, Accounting & Taxation** models built on **`Qwen/Qwen3-1.7B`** (100% offline on CPU laptops or GPU-less VPS instances) in two deployment options:
* **Multi-LoRA 1.7B (`loras/*.gguf`, 34 MB each — Recommended in this repo):** Lightweight `Qwen3-1.7B` (`Q4_K_M`, ~1.1 GB) base + **4 isolated specialist LoRA adapters** hot-swappable per task in `llama-server` (~1.3 GB total RAM).
* **MoE 5B (`asadeltek-indo-tax-moe-5b.gguf`, ~2.82 GiB):** Single merged 4-expert `Qwen3MoeForCausalLM` file.

> **Looking for a single-file model with no LoRA switching and 100% accuracy?**
> Check out our **Unified 3B** variant at [`lensetek/asadeltek-indo-tax-3b`](https://huggingface.co/lensetek/asadeltek-indo-tax-3b) (`asadeltek-indo-tax-3b.gguf`, 1.93 GB).

### LoRA 1–4 Specialties (`loras/`)

| ID (`llama-server`) | Adapter File | Core Capabilities |
| :---: | :--- | :--- |
| **`0`** | `loras/expert_1_accounting-lora.gguf` | **Accounting & Journaling (SAK, SAK-EP, PSAP/BUMD):** Cashier receipts, water billing accruals (DRD), compound VAT+WHT journals, inventory, prepaid rent, depreciation, payroll & BPJS, bad debt allowance, CapEx reclassification, and accrued expenses. |
| **`1`** | `loras/expert_2_audit-lora.gguf` | **Audit, Ratios & Financial Projections:** EBITDA & Margin, RKAP budget variance analysis, Pro Forma projections, Bank Reconciliation, Current Ratio, DER, DSCR, collection efficiency, and SA 320 Audit Materiality. |
| **`2`** | `loras/expert_3_tax_id-lora.gguf` | **Indonesian Taxation (UU HPP, PMK 131/2024, PP 58/2023):** VAT 12% on 11/12 tax base & luxury goods, Art. 23 WHT (with/without NPWP), Art. 4(2) Final Tax, Art. 22, Art. 21 TER (A/B/C), Corporate Tax Fiscal Reconciliation (22%), and VAT-CIT Equalization. |
| **`3`** | `loras/expert_4_agentic-lora.gguf` | **Agentic Tool-Caller & Python Calc:** Safe JSON tool invocation (`list_client_files`, `inspect_excel_template`, `write_excel_preserving_template`, `read_document_or_ocr`, `rwed_file`, `run_sqlite_query`, `verify_accounting_balance`, `build_non_html_dashboard`, `run_python_calc`). |

### Benchmark Comparison (8 Held-Out Samples, Strict JSON Schema)
| Model Variant | Passed | Accuracy |
| :--- | :---: | :---: |
| **Base:** `Qwen/Qwen3-1.7B` (zero-shot) | 0 / 8 | 0.0% |
| **Base:** `Qwen/Qwen2.5-Coder-3B-Instruct` (zero-shot) | 0 / 8 | 0.0% |
| **MoE 5B (This Repo):** `asadeltek-indo-tax-moe-5b.gguf` | 2 / 8 | 25.0% |
| **Multi-LoRA 1.7B (This Repo):** `Qwen3-1.7B` + 4 Specialist LoRAs | 6 / 8 | 75.0% *(100% on Audit & Tax)* |
| **Unified 3B:** [`lensetek/asadeltek-indo-tax-3b`](https://huggingface.co/lensetek/asadeltek-indo-tax-3b) (`asadeltek-indo-tax-3b.gguf`) | **8 / 8** | **100.0%** *(+ 9/12 Python AST eval)* |

### Quick Start (`llama.cpp` Multi-LoRA Hot-Swap)
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
