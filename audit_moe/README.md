# Asadeltek Indo Tax & Audit MoE (`Qwen3-1.7B` MoE & Isolated LoRA)

[Bahasa Indonesia](#bahasa-indonesia) | [English](#english)

---

## Bahasa Indonesia

Sistem **AI Agentic Audit, Akuntansi & Perpajakan Indonesia** berbasis **`Qwen/Qwen3-1.7B`** yang dirancang untuk **Colab T4 (16 GB VRAM)** dan berjalan **100% offline** di laptop CPU-only maupun VPS tanpa GPU.

### Arsitektur Sistem (*Brain + Deterministic Hands*)
* **Brain (LLM):**
  * **Plan A (`asadeltek-indo-tax-moe-5b.gguf`):** 4-Expert `Qwen3MoeForCausalLM` (~5B total / ~2.3B aktif, `Q4_K_M` ~2.82 GiB) hasil `mergekit-moe` + *Router Calibration*.
  * **Plan B (`qwen3-1.7b-q4_k_m.gguf` + 4 Isolated LoRA GGUF):** 1 base model ringan (~1.1 GB) + 4 adapter LoRA terpisah (0% pencampuran bobot antar-expert).
* **Deterministic Hands (`audit_moe/runtime/`):**
  * [db.py](runtime/db.py) — Database lokal **SQLite3** dengan nominal `INTEGER` / `Decimal` dan *Balance Hard-Gate* (`Debit == Kredit` & `Aset == Kewajiban + Ekuitas + Laba`).
  * [tax_engine.py](runtime/tax_engine.py) — Kalkulator pajak Indonesia deterministik (PPN PMK 131/2024 `12% x DPP 11/12`, PPh 21 TER PP 58/2023, PPh 22, PPh 23 NPWP/non-NPWP, PPh 4(2) Final, Koreksi Fiskal PPh Badan 22%).
  * [tools.py](runtime/tools.py) — Sandbox RWED aman, pembaca `.xls`/`.xlsx`, penulis template Excel tanpa merusak formula klien, DOCX/PDF reader, serta `run_python_calc` (AST sandbox `Decimal`).
  * [ocr.py](runtime/ocr.py) & [dashboard.py](runtime/dashboard.py) — OCR lokal (`RapidOCR`/`Tesseract`) dan Dashboard non-HTML (Excel Native `BarChart` & Desktop GUI `Tkinter`).

### Hasil Uji Perbandingan (Benchmark Held-Out)
Pengujian dilakukan secara seragam via `llama-server` (`temperature=0.1`) terhadap **8 sampel held-out** (`eval_heldout_200.jsonl`, 2 sampel per expert) dengan validator skema JSON ketat ([validate_and_merge_jsonl.py](training/validate_and_merge_jsonl.py)):

| Model | Total Lulus | Akurasi | Expert 1 (Accounting) | Expert 2 (Audit) | Expert 3 (Tax ID) | Expert 4 (Agentic) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Model Asal:** `Qwen/Qwen3-1.7B` (`Q4_K_M`, tanpa fine-tune) | **0 / 8** | **0.0%** | 0/2 (`invalid_json`) | 0/2 (`invalid_json`) | 0/2 (`invalid_json`) | 0/2 (`invalid_json`) |
| **Plan A:** `asadeltek-indo-tax-moe-5b.gguf` (`Qwen3-MoE` + Router Calibration) | **2 / 8** | **25.0%** | 0/2 | **2/2 (100%)** | 0/2 | 0/2 |
| **Plan B (Rekomendasi):** `Qwen/Qwen3-1.7B` (`Q4_K_M`) + 4 Isolated LoRA GGUF | **6 / 8** | **75.0%** | 1/2 | **2/2 (100%)** | **2/2 (100%)** | 1/2 |

> **Temuan Kunci:** Meskipun *Router Calibration* menaikkan skor MoE dari `0/8` ke `2/8`, pencampuran bobot `top_k=2` pada MoE masih menggeser nama field JSON ketat. **Plan B (Isolated LoRA GGUF)** menghilangkan pencampuran antar-expert sehingga skor melonjak ke **75.0%** (100% di Audit & Pajak) dengan konsumsi RAM jauh lebih kecil.

### Struktur Folder & Cara Uji Cepat
* `training/build_distilled_datasets.py` — Generator 6.000 data latih + 200 held-out eval (100% entitas fiktif).
* `training/run_colab_plan_a.py` & `training/run_colab_calibrate_and_export.py` — Otomasi training di Colab T4 via `google-colab-cli`.
* `training/eval_local_gguf.py` — Evaluator lokal untuk `llama-server`.

---

## English

An **Agentic Indonesian Audit, Accounting & Tax AI System** built on **`Qwen/Qwen3-1.7B`**, trainable on **Google Colab T4 (16 GB VRAM)** and runnable **100% offline** on commodity CPU-only laptops or GPU-less VPS instances.

### System Architecture (*Brain + Deterministic Hands*)
* **Brain (LLM):**
  * **Plan A (`asadeltek-indo-tax-moe-5b.gguf`):** 4-Expert `Qwen3MoeForCausalLM` (~5B total / ~2.3B active, `Q4_K_M` ~2.82 GiB) built with `mergekit-moe` + *Router Calibration*.
  * **Plan B (`qwen3-1.7b-q4_k_m.gguf` + 4 Isolated LoRA GGUFs):** Lightweight base model (~1.1 GB) + 4 isolated GGUF LoRA adapters (0% cross-expert weight dilution).
* **Deterministic Hands (`audit_moe/runtime/`):**
  * [db.py](runtime/db.py) — Local **SQLite3** ledger using `INTEGER` / `Decimal` precision and a *Balance Hard-Gate* (`Debit == Credit` & `Assets == Liabilities + Equity + Net Income`).
  * [tax_engine.py](runtime/tax_engine.py) — Deterministic Indonesian tax calculator (VAT PMK 131/2024 `12% x 11/12`, PPh 21 TER PP 58/2023, PPh 22/23/4(2), Corporate Tax Fiscal Reconciliation).
  * [tools.py](runtime/tools.py) — Sandboxed RWED file operations, `.xls`/`.xlsx` reader, formula-preserving Excel template writer, DOCX/PDF reader, and `run_python_calc` (AST-sandboxed `Decimal` execution).
  * [ocr.py](runtime/ocr.py) & [dashboard.py](runtime/dashboard.py) — Offline OCR (`RapidOCR`/`Tesseract`) and non-HTML dashboards (Excel Native `BarChart` & `Tkinter` Desktop GUI).

### Benchmark Comparison (Held-Out Evaluation)
Evaluated uniformly via `llama-server` (`temperature=0.1`) on **8 held-out samples** (`eval_heldout_200.jsonl`, 2 samples per expert) against strict JSON schema validation ([validate_and_merge_jsonl.py](training/validate_and_merge_jsonl.py)):

| Model | Passed | Accuracy | Expert 1 (Accounting) | Expert 2 (Audit) | Expert 3 (Tax ID) | Expert 4 (Agentic) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Base Model:** `Qwen/Qwen3-1.7B` (`Q4_K_M`, zero-shot) | **0 / 8** | **0.0%** | 0/2 (`invalid_json`) | 0/2 (`invalid_json`) | 0/2 (`invalid_json`) | 0/2 (`invalid_json`) |
| **Plan A:** `asadeltek-indo-tax-moe-5b.gguf` (`Qwen3-MoE` + Router Calibration) | **2 / 8** | **25.0%** | 0/2 | **2/2 (100%)** | 0/2 | 0/2 |
| **Plan B (Recommended):** `Qwen/Qwen3-1.7B` (`Q4_K_M`) + 4 Isolated LoRA GGUFs | **6 / 8** | **75.0%** | 1/2 | **2/2 (100%)** | **2/2 (100%)** | 1/2 |

> **Key Finding:** While *Router Calibration* improved the MoE score from `0/8` to `2/8`, `top_k=2` expert mixing still causes occasional strict JSON schema drift. **Plan B (Isolated LoRA GGUFs)** eliminates cross-expert interference, jumping to **75.0%** overall (**100%** on Audit & Indonesian Tax) with an even smaller RAM footprint.
