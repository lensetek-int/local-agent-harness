# Asadeltek Indo Tax & Audit (`Qwen2.5-Coder-3B` Unified & `Qwen3-1.7B` MoE/Multi-LoRA)

[Bahasa Indonesia](#bahasa-indonesia) | [English](#english)

---

## Bahasa Indonesia

Sistem **AI Agentic Audit, Akuntansi & Perpajakan Indonesia** yang dapat dilatih di **Google Colab T4 (16 GB VRAM)** dan berjalan **100% offline** di laptop CPU-only maupun VPS tanpa GPU.

### Pilihan Model (Hugging Face)
1. **Varian Unified 3B (Rekomendasi Utama — Akurasi 100%):** [`lensetek/asadeltek-indo-tax-3b`](https://huggingface.co/lensetek/asadeltek-indo-tax-3b) (`asadeltek-indo-tax-3b.gguf`, ~1.93 GB).
   * 1 file GGUF tunggal berbasis `Qwen/Qwen2.5-Coder-3B-Instruct` yang langsung menguasai Akuntansi, Audit, Pajak Indonesia, Agentic Tools, dan penulisan kode Python `Decimal` (`run_python_calc`) tanpa perlu ganti-ganti LoRA.
2. **Varian Multi-LoRA 1.7B & MoE 5B (Ultra-Ringan ~1.3 GB RAM):** [`lensetek/asadeltek-indo-tax-moe-5b`](https://huggingface.co/lensetek/asadeltek-indo-tax-moe-5b) (`loras/*.gguf` & `asadeltek-indo-tax-moe-5b.gguf`).
   * Berbasis `Qwen/Qwen3-1.7B` dengan 4 adapter LoRA spesialis terpisah (`34 MB/file`) yang bisa di-hot-swap per tugas di `llama-server`.

### Arsitektur Sistem (*Otak AI + Runtime Deterministik Python*)
* **Deterministic Hands (`audit_moe/runtime/`):**
  * [db.py](runtime/db.py) — Database lokal **SQLite3** dengan nominal `INTEGER` / `Decimal` dan *Balance Hard-Gate* (`Debit == Kredit` & `Aset == Kewajiban + Ekuitas + Laba`).
  * [tax_engine.py](runtime/tax_engine.py) — Kalkulator pajak Indonesia deterministik (PPN PMK 131/2024 `12% x DPP 11/12`, PPh 21 TER PP 58/2023, PPh 22, PPh 23 NPWP/non-NPWP, PPh 4(2) Final, Koreksi Fiskal PPh Badan 22%).
  * [tools.py](runtime/tools.py) — Sandbox RWED aman, pembaca `.xls`/`.xlsx`, penulis template Excel tanpa merusak formula klien, DOCX/PDF reader, serta `run_python_calc` (AST sandbox `Decimal`).
  * [ocr.py](runtime/ocr.py) & [dashboard.py](runtime/dashboard.py) — OCR lokal (`RapidOCR`/`Tesseract`) dan Dashboard non-HTML (Excel Native `BarChart` & Desktop GUI `Tkinter`).

### Keahlian 4 Domain
| ID (`llama-server`) | File Adapter (Varian Multi-LoRA) | Keahlian Utama |
| :---: | :--- | :--- |
| **`0`** | `expert_1_accounting-lora.gguf` | **Akuntansi & Penjurnalan (SAK, SAK-EP, PSAP/BUMD):** LPP loket, Rekap DRD, jurnal majemuk PPN+PPh 23, persediaan, sewa dibayar dimuka, penyusutan, gaji & BPJS, CKPN piutang, reklasifikasi CapEx, uang muka, dan beban akrual. |
| **`1`** | `expert_2_audit-lora.gguf` | **Audit, Rasio & Proyeksi Keuangan:** EBITDA & Margin, Varians RKAP, Proyeksi Proforma, Rekonsiliasi Bank, Current Ratio, DER, DSCR, Efisiensi Penagihan BUMD, dan Materialitas Audit SA 320. |
| **`2`** | `expert_3_tax_id-lora.gguf` | **Perpajakan Indonesia Lengkap (UU HPP, PMK 131/2024, PP 58/2023):** PPN 12% x DPP 11/12 & Barang Mewah, PPh 23 (NPWP vs non-NPWP), PPh 4(2) Final, PPh 22, PPh 21 TER, Koreksi Fiskal 22%, dan Ekualisasi PPN-PPh. |
| **`3`** | `expert_4_agentic-lora.gguf` | **Agentic Tool-Caller & Python Calc:** Pemanggilan tool JSON aman (`list_client_files`, `inspect_excel_template`, `write_excel_preserving_template`, `read_document_or_ocr`, `rwed_file`, `run_sqlite_query`, `verify_accounting_balance`, `build_non_html_dashboard`, `run_python_calc`). |

### Hasil Uji Perbandingan (8 Soal Uji Acak Tersembunyi, Format JSON Ketat)
| Varian Model | Total Lulus | Akurasi | Akuntansi | Audit | Pajak ID | Agentic Tools |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Model Dasar:** `Qwen/Qwen3-1.7B` (tanpa fine-tuning) | **0 / 8** | **0.0%** | 0/2 | 0/2 | 0/2 | 0/2 |
| **Model Dasar:** `Qwen/Qwen2.5-Coder-3B-Instruct` (tanpa fine-tuning) | **0 / 8** | **0.0%** | 0/2 | 0/2 | 0/2 | 0/2 |
| **Varian MoE 5B:** [`asadeltek-indo-tax-moe-5b.gguf`](https://huggingface.co/lensetek/asadeltek-indo-tax-moe-5b) | **2 / 8** | **25.0%** | 0/2 | **2/2 (100%)** | 0/2 | 0/2 |
| **Varian Multi-LoRA 1.7B:** [`Qwen3-1.7B` + 4 LoRA Spesialis](https://huggingface.co/lensetek/asadeltek-indo-tax-moe-5b) | **6 / 8** | **75.0%** | 1/2 | **2/2 (100%)** | **2/2 (100%)** | 1/2 |
| **Varian Unified 3B (Terbaik):** [`asadeltek-indo-tax-3b.gguf`](https://huggingface.co/lensetek/asadeltek-indo-tax-3b) | **8 / 8** | **100.0%** | **2/2 (100%)** | **2/2 (100%)** | **2/2 (100%)** | **2/2 (100%)** |

* **Uji Eksekusi Kode Python (`Decimal`):** **9 / 12 (75.0%)** kode Python dari Unified 3B lolos eksekusi sandbox AST dan menghasilkan angka Rupiah tepat.

### Cara Menjalankan Cepat (`llama-server`)
**Opsi 1 — Unified 3B (1 File Tunggal, Paling Praktis & Akurat):**
```bash
huggingface-cli download lensetek/asadeltek-indo-tax-3b asadeltek-indo-tax-3b.gguf --local-dir .
./bin/llama-server.exe -m asadeltek-indo-tax-3b.gguf --host 127.0.0.1 --port 8080 -c 4096 -t 4
```

**Opsi 2 — Multi-LoRA 1.7B (Hot-Swap per Tugas, RAM ~1.3 GB):**
```bash
huggingface-cli download unsloth/Qwen3-1.7B-GGUF Qwen3-1.7B-Q4_K_M.gguf --local-dir .
huggingface-cli download lensetek/asadeltek-indo-tax-moe-5b --include "loras/*" --local-dir .

./bin/llama-server.exe -m Qwen3-1.7B-Q4_K_M.gguf \
  --lora loras/expert_1_accounting-lora.gguf,loras/expert_2_audit-lora.gguf,loras/expert_3_tax_id-lora.gguf,loras/expert_4_agentic-lora.gguf \
  --lora-init-without-apply --host 127.0.0.1 --port 8080 -c 4096 -t 4
```

---

## English

An **Agentic Indonesian Audit, Accounting & Tax AI System**, trainable on **Google Colab T4 (16 GB VRAM)** and runnable **100% offline** on CPU-only laptops or GPU-less VPS servers.

### Model Options (Hugging Face)
1. **Unified 3B (Recommended — 100% Held-Out Accuracy):** [`lensetek/asadeltek-indo-tax-3b`](https://huggingface.co/lensetek/asadeltek-indo-tax-3b) (`asadeltek-indo-tax-3b.gguf`, ~1.93 GB) — Single-file `Qwen/Qwen2.5-Coder-3B-Instruct` covering all 4 domains plus `run_python_calc` without adapter switching.
2. **Multi-LoRA 1.7B & MoE 5B (Ultra-Lightweight ~1.3 GB RAM):** [`lensetek/asadeltek-indo-tax-moe-5b`](https://huggingface.co/lensetek/asadeltek-indo-tax-moe-5b) (`loras/*.gguf` & `asadeltek-indo-tax-moe-5b.gguf`).

### Benchmark Comparison (8 Held-Out Samples, Strict JSON Schema)
| Model Variant | Passed | Accuracy | Accounting | Audit | Tax ID | Agentic Tools |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Base Model:** `Qwen/Qwen3-1.7B` (zero-shot) | **0 / 8** | **0.0%** | 0/2 | 0/2 | 0/2 | 0/2 |
| **Base Model:** `Qwen/Qwen2.5-Coder-3B-Instruct` (zero-shot) | **0 / 8** | **0.0%** | 0/2 | 0/2 | 0/2 | 0/2 |
| **MoE 5B:** [`asadeltek-indo-tax-moe-5b.gguf`](https://huggingface.co/lensetek/asadeltek-indo-tax-moe-5b) | **2 / 8** | **25.0%** | 0/2 | **2/2 (100%)** | 0/2 | 0/2 |
| **Multi-LoRA 1.7B:** [`Qwen3-1.7B` + 4 Specialist LoRAs](https://huggingface.co/lensetek/asadeltek-indo-tax-moe-5b) | **6 / 8** | **75.0%** | 1/2 | **2/2 (100%)** | **2/2 (100%)** | 1/2 |
| **Unified 3B (Best):** [`asadeltek-indo-tax-3b.gguf`](https://huggingface.co/lensetek/asadeltek-indo-tax-3b) | **8 / 8** | **100.0%** | **2/2 (100%)** | **2/2 (100%)** | **2/2 (100%)** | **2/2 (100%)** |

* **Live Python AST Execution Eval (`eval_python_calc_24.jsonl`):** **9 / 12 (75.0%)** passed exact `Decimal` verification.
