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
  - agentic
language:
  - id
  - en
pipeline_tag: text-generation
---

# Asadeltek Indo Tax & Audit MoE (`asadeltek-indo-tax-moe-5b.gguf`)

[Bahasa Indonesia](#bahasa-indonesia) | [English](#english)

---

## Bahasa Indonesia

Model **Mixture of Experts (MoE)** berbahasa Indonesia & Inggris berbasis **`Qwen/Qwen3-1.7B`** (4 Experts Spesialis, `Qwen3MoeForCausalLM`, Top-2 Routing, ~5B total parameter / ~2.3B aktif per token) yang dikuantisasi ke **`Q4_K_M` (~2.82 GiB)** agar berjalan **100% offline** di laptop standar (CPU) maupun VPS tanpa GPU.

### Arsitektur 4 Expert
Digabungkan dengan `mergekit-moe` (`gate_mode: cheap_embed`, `experts_per_token: 2`) + *Router Calibration* dari 4 adapter QLoRA yang dilatih dengan 6.000 sampel tervalidasi (1.500/expert):
1. **Expert 1 — Accounting & Journaling:** Pemetaan transaksi ke CoA & jurnal berimbang JSON (SAK, SAK-EP, PSAP/BUMD).
2. **Expert 2 — Audit, Rasio & Proyeksi:** EBITDA, Varians RKAP, Proyeksi Proforma, Rekonsiliasi Bank, Current Ratio, DER, DSCR, dan Materialitas SA 320.
3. **Expert 3 — Perpajakan Indonesia:** PPN (PMK 131/2024 12% x DPP 11/12 & Barang Mewah), PPh 21 TER (PP 58/2023), PPh 22/23/4(2), Koreksi Fiskal PPh Badan 22%, dan Ekualisasi PPN-PPh.
4. **Expert 4 — Agentic Tool-Caller:** Orkestrasi tool JSON (`list_client_files`, `inspect_excel_template`, `write_excel_preserving_template`, `read_document_or_ocr`, `rwed_file`, `run_sqlite_query`, `verify_accounting_balance`, `build_non_html_dashboard`, `run_python_calc`).

### Hasil Uji Perbandingan (8 Sampel Held-Out)
| Model | Lulus | Akurasi |
| :--- | :---: | :---: |
| **Model Asal:** `Qwen/Qwen3-1.7B` (`Q4_K_M`, tanpa fine-tune) | 0 / 8 | 0.0% |
| **Plan A:** `asadeltek-indo-tax-moe-5b.gguf` (`Qwen3-MoE` + Router Calibration) | 2 / 8 | 25.0% |
| **Plan B:** `Qwen/Qwen3-1.7B` (`Q4_K_M`) + 4 Isolated LoRA GGUF | **6 / 8** | **75.0%** *(100% di Audit & Pajak)* |

---

## English

An Indonesian & English **Mixture of Experts (MoE)** model based on **`Qwen/Qwen3-1.7B`** (4 Specialist Experts, `Qwen3MoeForCausalLM`, Top-2 Routing, ~5B total / ~2.3B active parameters), quantized to **`Q4_K_M` (~2.82 GiB)** for **100% offline** execution on CPU-only laptops or VPS instances.

### Held-Out Benchmark Comparison (8 Samples, Strict JSON Schema)
| Model | Passed | Accuracy |
| :--- | :---: | :---: |
| **Base Model:** `Qwen/Qwen3-1.7B` (`Q4_K_M`, zero-shot) | 0 / 8 | 0.0% |
| **Plan A:** `asadeltek-indo-tax-moe-5b.gguf` (`Qwen3-MoE` + Router Calibration) | 2 / 8 | 25.0% |
| **Plan B:** `Qwen/Qwen3-1.7B` (`Q4_K_M`) + 4 Isolated LoRA GGUFs | **6 / 8** | **75.0%** *(100% on Audit & Tax)* |

### Quick Start (`llama.cpp`)
```bash
huggingface-cli download lensetek/asadeltek-indo-tax-moe-5b asadeltek-indo-tax-moe-5b.gguf --local-dir .
./llama-server -m asadeltek-indo-tax-moe-5b.gguf --host 127.0.0.1 --port 8080 -c 4096 -t 4
```
