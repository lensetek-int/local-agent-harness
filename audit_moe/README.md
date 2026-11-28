# Asadeltek Indo Tax & Audit MoE (`Qwen3-1.7B` MoE & 4 Isolated LoRA)

[Bahasa Indonesia](#bahasa-indonesia) | [English](#english)

---

## Bahasa Indonesia

Sistem **AI Agentic Audit, Akuntansi & Perpajakan Indonesia** berbasis **`Qwen/Qwen3-1.7B`** yang dirancang untuk **Colab T4 (16 GB VRAM)** dan berjalan **100% offline** di laptop CPU-only maupun VPS tanpa GPU.

### Arsitektur Sistem (*Brain + Deterministic Hands*)
* **Brain (LLM):**
  * **Plan A (`asadeltek-indo-tax-moe-5b.gguf`, ~2.82 GiB):** 4-Expert `Qwen3MoeForCausalLM` (~5B total / ~2.3B aktif, `Q4_K_M`) hasil `mergekit-moe` + *Router Calibration*.
  * **Plan B (`loras/*.gguf`, 34 MB/file — Direkomendasikan):** Base `Qwen3-1.7B` (`Q4_K_M`, ~1.1 GB) + **4 Isolated LoRA GGUF** dengan *hot-swap* dinamis di `llama-server` (0% pencampuran bobot antar-expert).
* **Deterministic Hands (`audit_moe/runtime/`):**
  * [db.py](runtime/db.py) — Database lokal **SQLite3** dengan nominal `INTEGER` / `Decimal` dan *Balance Hard-Gate* (`Debit == Kredit` & `Aset == Kewajiban + Ekuitas + Laba`).
  * [tax_engine.py](runtime/tax_engine.py) — Kalkulator pajak Indonesia deterministik (PPN PMK 131/2024 `12% x DPP 11/12`, PPh 21 TER PP 58/2023, PPh 22, PPh 23 NPWP/non-NPWP, PPh 4(2) Final, Koreksi Fiskal PPh Badan 22%).
  * [tools.py](runtime/tools.py) — Sandbox RWED aman, pembaca `.xls`/`.xlsx`, penulis template Excel tanpa merusak formula klien, DOCX/PDF reader, serta `run_python_calc` (AST sandbox `Decimal`).
  * [ocr.py](runtime/ocr.py) & [dashboard.py](runtime/dashboard.py) — OCR lokal (`RapidOCR`/`Tesseract`) dan Dashboard non-HTML (Excel Native `BarChart` & Desktop GUI `Tkinter`).

### Keahlian LoRA 1 s/d 4 (`loras/`)

| ID (`llama-server`) | File Adapter | Keahlian Utama |
| :---: | :--- | :--- |
| **`0`** | `expert_1_accounting-lora.gguf` | **Akuntansi & Penjurnalan (SAK, SAK-EP, PSAP/BUMD):** LPP loket (pokok & denda), Rekap DRD, jurnal majemuk PPN+PPh 23, persediaan kredit, sewa dibayar dimuka, penyusutan aset tetap, gaji & BPJS, CKPN piutang, reklasifikasi CapEx, uang muka sambungan baru, setor kas, dan beban akrual. |
| **`1`** | `expert_2_audit-lora.gguf` | **Audit, Rasio & Proyeksi Keuangan:** EBITDA & Margin, Analisis Varians RKAP, Proyeksi Proforma, Rekonsiliasi Bank (DIT/OSC/jasa giro), Current Ratio, DER, DSCR, Efisiensi Penagihan BUMD, dan Materialitas Audit SA 320. |
| **`2`** | `expert_3_tax_id-lora.gguf` | **Perpajakan Indonesia Lengkap (UU HPP, PMK 131/2024, PP 58/2023):** PPN 12% x DPP Nilai Lain 11/12 & Barang Mewah, PPh 23 (NPWP vs non-NPWP), PPh 4(2) Final (sewa & UMKM 0,5%), PPh 22 pengadaan, PPh 21 TER (A/B/C), Koreksi Fiskal PPh Badan 22%, dan Ekualisasi Omzet PPN-PPh. |
| **`3`** | `expert_4_agentic-lora.gguf` | **Agentic Tool-Caller & Python Calc:** Pemanggilan tool JSON aman (`list_client_files`, `inspect_excel_template`, `write_excel_preserving_template`, `read_document_or_ocr`, `rwed_file`, `run_sqlite_query`, `verify_accounting_balance`, `build_non_html_dashboard`, `run_python_calc`). |

### Hasil Uji Perbandingan (Benchmark Held-Out)
Pengujian dilakukan secara seragam via `llama-server` (`temperature=0.1`) terhadap **8 sampel held-out** (`eval_heldout_200.jsonl`, 2 sampel per expert) dengan validator skema JSON ketat ([validate_and_merge_jsonl.py](training/validate_and_merge_jsonl.py)):

| Model | Total Lulus | Akurasi | Expert 1 (Accounting) | Expert 2 (Audit) | Expert 3 (Tax ID) | Expert 4 (Agentic) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Base:** `Qwen/Qwen3-1.7B` (`Q4_K_M`, tanpa fine-tune) | **0 / 8** | **0.0%** | 0/2 | 0/2 | 0/2 | 0/2 |
| **Base:** `Qwen/Qwen2.5-Coder-3B-Instruct` (`Q4_K_M`, tanpa fine-tune) | **0 / 8** | **0.0%** | 0/2 | 0/2 | 0/2 | 0/2 |
| **Plan A:** [`asadeltek-indo-tax-moe-5b.gguf`](https://huggingface.co/lensetek/asadeltek-indo-tax-moe-5b) (`Qwen3-MoE` + Router Calibration) | **2 / 8** | **25.0%** | 0/2 | **2/2 (100%)** | 0/2 | 0/2 |
| **Plan B:** [`Qwen/Qwen3-1.7B` (`Q4_K_M`) + 4 Isolated LoRA GGUF](https://huggingface.co/lensetek/asadeltek-indo-tax-moe-5b) | **6 / 8** | **75.0%** | 1/2 | **2/2 (100%)** | **2/2 (100%)** | 1/2 |
| **Plan C (Terbaik):** [`asadeltek-indo-tax-3b.gguf`](https://huggingface.co/lensetek/asadeltek-indo-tax-3b) (`Unified 6.48K`) | **8 / 8** | **100.0%** | **2/2 (100%)** | **2/2 (100%)** | **2/2 (100%)** | **2/2 (100%)** |

* **Uji Eksekusi Python Nyata Plan C (`eval_python_calc_24.jsonl`, 12 domain kalkulasi):** **9 / 12 (75.0%)** lulus eksekusi AST sandbox.
* **Dua Repo Hugging Face Saling Terhubung:**
  * Unified 3B (**Plan C**, 100% akurasi): [`lensetek/asadeltek-indo-tax-3b`](https://huggingface.co/lensetek/asadeltek-indo-tax-3b)
  * MoE 5B & 4 Isolated LoRA (**Plan A & B**): [`lensetek/asadeltek-indo-tax-moe-5b`](https://huggingface.co/lensetek/asadeltek-indo-tax-moe-5b)

### Cara Menjalankan Semua LoRA (Multi-LoRA Hot-Swap)
```bash
# 1. Unduh base Qwen3-1.7B Q4_K_M & 4 LoRA dari Hugging Face
huggingface-cli download unsloth/Qwen3-1.7B-GGUF Qwen3-1.7B-Q4_K_M.gguf --local-dir .
huggingface-cli download lensetek/asadeltek-indo-tax-moe-5b --include "loras/*" --local-dir .

# 2. Muat semua 4 LoRA sekaligus tanpa mencampur bobot
./bin/llama-server.exe -m Qwen3-1.7B-Q4_K_M.gguf \
  --lora loras/expert_1_accounting-lora.gguf,loras/expert_2_audit-lora.gguf,loras/expert_3_tax_id-lora.gguf,loras/expert_4_agentic-lora.gguf \
  --lora-init-without-apply --host 127.0.0.1 --port 8080 -c 4096 -t 4

# 3. Aktifkan LoRA sesuai tugas sebelum request (contoh: id 2 = Pajak Indonesia)
curl -X POST http://127.0.0.1:8080/lora-adapters \
  -H "Content-Type: application/json" \
  -d '[{"id": 0, "scale": 0.0}, {"id": 1, "scale": 0.0}, {"id": 2, "scale": 1.0}, {"id": 3, "scale": 0.0}]'
```

---

## English

An **Agentic Indonesian Audit, Accounting & Tax AI System** built on **`Qwen/Qwen3-1.7B`**, trainable on **Google Colab T4 (16 GB VRAM)** and runnable **100% offline** on CPU-only laptops or GPU-less VPS instances.

### LoRA 1–4 Specialties (`loras/`)

| ID (`llama-server`) | Adapter File | Core Capabilities |
| :---: | :--- | :--- |
| **`0`** | `expert_1_accounting-lora.gguf` | **Accounting & Journaling (SAK, SAK-EP, PSAP/BUMD):** Cashier receipts, water billing accruals (DRD), compound VAT+WHT journals, inventory, prepaid rent, depreciation, payroll & BPJS, bad debt allowance, CapEx reclassification, and accrued expenses. |
| **`1`** | `expert_2_audit-lora.gguf` | **Audit, Ratios & Financial Projections:** EBITDA & Margin, RKAP budget variance analysis, Pro Forma projections, Bank Reconciliation, Current Ratio, DER, DSCR, collection efficiency, and SA 320 Audit Materiality. |
| **`2`** | `expert_3_tax_id-lora.gguf` | **Indonesian Taxation (UU HPP, PMK 131/2024, PP 58/2023):** VAT 12% on 11/12 tax base & luxury goods, Art. 23 WHT (with/without NPWP), Art. 4(2) Final Tax, Art. 22, Art. 21 TER (A/B/C), Corporate Tax Fiscal Reconciliation (22%), and VAT-CIT Equalization. |
| **`3`** | `expert_4_agentic-lora.gguf` | **Agentic Tool-Caller & Python Calc:** Safe JSON tool invocation (`list_client_files`, `inspect_excel_template`, `write_excel_preserving_template`, `read_document_or_ocr`, `rwed_file`, `run_sqlite_query`, `verify_accounting_balance`, `build_non_html_dashboard`, `run_python_calc`). |

### Benchmark Comparison (Held-Out Evaluation)
Evaluated uniformly via `llama-server` (`temperature=0.1`) on **8 held-out samples** (`eval_heldout_200.jsonl`, 2 samples per expert) against strict JSON schema validation ([validate_and_merge_jsonl.py](training/validate_and_merge_jsonl.py)):

| Model | Passed | Accuracy | Expert 1 (Accounting) | Expert 2 (Audit) | Expert 3 (Tax ID) | Expert 4 (Agentic) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Base:** `Qwen/Qwen3-1.7B` (`Q4_K_M`, zero-shot) | **0 / 8** | **0.0%** | 0/2 | 0/2 | 0/2 | 0/2 |
| **Base:** `Qwen/Qwen2.5-Coder-3B-Instruct` (`Q4_K_M`, zero-shot) | **0 / 8** | **0.0%** | 0/2 | 0/2 | 0/2 | 0/2 |
| **Plan A:** [`asadeltek-indo-tax-moe-5b.gguf`](https://huggingface.co/lensetek/asadeltek-indo-tax-moe-5b) (`Qwen3-MoE` + Router Calibration) | **2 / 8** | **25.0%** | 0/2 | **2/2 (100%)** | 0/2 | 0/2 |
| **Plan B:** [`Qwen/Qwen3-1.7B` (`Q4_K_M`) + 4 Isolated LoRA GGUFs](https://huggingface.co/lensetek/asadeltek-indo-tax-moe-5b) | **6 / 8** | **75.0%** | 1/2 | **2/2 (100%)** | **2/2 (100%)** | 1/2 |
| **Plan C (Best):** [`asadeltek-indo-tax-3b.gguf`](https://huggingface.co/lensetek/asadeltek-indo-tax-3b) (`Unified 6.48K`) | **8 / 8** | **100.0%** | **2/2 (100%)** | **2/2 (100%)** | **2/2 (100%)** | **2/2 (100%)** |

* **Live Python AST Execution Eval (`eval_python_calc_24.jsonl`):** **9 / 12 (75.0%)** passed exact `Decimal` verification.
* **Linked Hugging Face Repositories:**
  * Unified 3B (**Plan C**, 100% accuracy): [`lensetek/asadeltek-indo-tax-3b`](https://huggingface.co/lensetek/asadeltek-indo-tax-3b)
  * MoE 5B & 4 Isolated LoRAs (**Plan A & B**): [`lensetek/asadeltek-indo-tax-moe-5b`](https://huggingface.co/lensetek/asadeltek-indo-tax-moe-5b)

### Quick Start (Multi-LoRA Hot-Swap — Plan B)
```bash
huggingface-cli download unsloth/Qwen3-1.7B-GGUF Qwen3-1.7B-Q4_K_M.gguf --local-dir .
huggingface-cli download lensetek/asadeltek-indo-tax-moe-5b --include "loras/*" --local-dir .

./bin/llama-server.exe -m Qwen3-1.7B-Q4_K_M.gguf \
  --lora loras/expert_1_accounting-lora.gguf,loras/expert_2_audit-lora.gguf,loras/expert_3_tax_id-lora.gguf,loras/expert_4_agentic-lora.gguf \
  --lora-init-without-apply --host 127.0.0.1 --port 8080 -c 4096 -t 4
```
