# Plan C: Unified 3B Model (`lensetek/asadeltek-indo-tax-3b`)

Dokumen rencana final (setelah tinjauan teknis) untuk membangun, menguji, dan merilis **Plan C (`asadeltek-indo-tax-3b.gguf`)** berbasis **`Qwen/Qwen2.5-Coder-3B-Instruct`**.

---

## Hasil Tinjauan Teknis (Perbaikan Sebelum Eksekusi)
1. **Disambiguasi System Prompt (Kritis):** Seluruh **480 sampel baru `run_python_calc`** wajib menggunakan system prompt `expert_4_agentic` (*Agentic Runtime Orchestrator*) agar **tidak bentrok** dengan format JSON langsung milik `expert_2_audit` & `expert_3_tax_id` pada `eval_heldout_200.jsonl`.
2. **Eksekusi Nyata di Sandbox AST:** Setiap kode Python dalam 480 sampel tambahan (dan 24 sampel eval Python baru) **wajib dieksekusi langsung melalui `runtime.tools.run_python_calc`** saat build dataset, untuk menjamin 100% bebas syntax error, bebas operasi terlarang (`import`), dan hasilnya cocok dengan `Decimal`/`tax_engine.py`.
3. **Jadwal Learning Rate Lebih Halus:** Gunakan `lr_scheduler_type="cosine"` dan `warmup_steps=30` untuk 6.480 sampel multi-domain agar konvergensi antar-4-domain lebih stabil.
4. **Benchmark Dua Lapis:**
   * **Lapis 1 (Adil 100% dengan Plan A/B):** Uji pada **8 sampel identik** dari `eval_heldout_200.jsonl` (tanpa uji ulang model lama).
   * **Lapis 2 (Uji Eksekusi Python Nyata):** Uji tambahan pada **12–24 sampel unseen `eval_python_calc_24.jsonl`** dengan benar-benar menjalankan kode Python keluaran model di `run_python_calc` dan memverifikasi nilai Rupiah akhirnya!

---

## 1. Spesifikasi Target & Repo Baru
* **Base Model:** `unsloth/Qwen2.5-Coder-3B-Instruct-bnb-4bit` (`Qwen/Qwen2.5-Coder-3B-Instruct`)
* **Arsitektur:** Unified Dense 3B (1 model tunggal menguasai seluruh 4 domain + `run_python_calc`)
* **File Output:** `asadeltek-indo-tax-3b.gguf` (`Q4_K_M`, estimasi ~1.9–2.1 GB)
* **Repo Hugging Face Baru:** `lensetek/asadeltek-indo-tax-3b`

---

## 2. Dataset Unified (6.480 Sampel Latih, Eval Held-Out Tetap Murni)
* **6.000 sampel gabungan** dari 4 file yang sudah ada (`expert_1_accounting.jsonl`, `expert_2_audit.jsonl`, `expert_3_tax_id.jsonl`, `expert_4_agentic.jsonl`).
* **+480 sampel baru `plan_c_python_calc_480.jsonl`** (12 domain kalkulasi × 40 variasi realistis):
  1. EBITDA & EBITDA Margin
  2. Analisis Varians RKAP (Pendapatan & Beban)
  3. Proyeksi Proforma 1–5 tahun (pertumbuhan majemuk `Decimal`)
  4. Current Ratio & Debt-to-Equity Ratio (DER)
  5. Debt Service Coverage Ratio (DSCR)
  6. Efisiensi Penagihan Piutang BUMD (DRD vs Penerimaan)
  7. Penetapan Materialitas Audit SA 320 (OM, PM 75%, Clearly Trivial 5%)
  8. Rekonsiliasi Bank (Saldo Bank + DIT - OSC vs Saldo Buku + Jasa Giro - Adm)
  9. PPN PMK 131/2024 (`12% x DPP Nilai Lain 11/12` & Barang Mewah `12%`)
  10. PPh Pasal 23 (NPWP vs non-NPWP) & PPh 4(2) Final (Sewa 10% / UMKM 0,5%)
  11. PPh Pasal 21 TER (PP 58/2023) & PPh Pasal 22 Pengadaan (`1,5%`)
  12. Rekonsiliasi Fiskal PPh Badan (`22%`) & Validasi Jurnal Majemuk (`sum(debit) == sum(credit)`)
* Digabung & di-shuffle (`seed=2026`) ke `unified_plan_c_6480.jsonl` dengan **0 overlap** terhadap `eval_heldout_200.jsonl` dan `eval_python_calc_24.jsonl`.

---

## 3. Training & Export GGUF di Colab T4 (`colab` CLI WSL)
1. Provisioning session GPU T4 baru (`colab new -s plan_c_t4 --gpu T4`) dan upload `unified_plan_c_6480.jsonl`, `eval_heldout_200.jsonl`, serta `eval_python_calc_24.jsonl`.
2. Fine-tuning QLoRA tunggal: `r=16`, `lora_alpha=16`, `max_length=2048`, `num_train_epochs=2`, `per_device_train_batch_size=2`, `gradient_accumulation_steps=4`, `learning_rate=2e-4`, `lr_scheduler_type="cosine"`, `warmup_steps=30` (estimasi ~30–40 menit di T4).
3. Merge 16-bit -> build `llama.cpp` -> convert ke F16 -> quantize ke **`asadeltek-indo-tax-3b.gguf` (`Q4_K_M`)** -> hapus file `F16`.

---

## 4. Benchmark Perbandingan (Tanpa Uji Ulang Model Lama)
Di Colab, **hanya menguji 2 model** pada **8 sampel held-out yang sama** (`eval_heldout_200.jsonl`, 2/expert, `temperature=0.1`):
1. **Base `Qwen/Qwen2.5-Coder-3B-Instruct` (`Q4_K_M`, zero-shot)**
2. **Plan C `asadeltek-indo-tax-3b.gguf` (`Q4_K_M`, Unified 6.480 sampel)**

Ditambah uji eksekusi Python nyata pada **`eval_python_calc_24.jsonl`**, lalu digabungkan dengan hasil `benchmark_results.json` sebelumnya:
* Base `Qwen/Qwen3-1.7B` (`Q4_K_M`): **0 / 8 (0.0%)**
* Plan A `asadeltek-indo-tax-moe-5b.gguf` (`Qwen3-MoE` + Router Calibration): **2 / 8 (25.0%)**
* Plan B `Qwen/Qwen3-1.7B` + 4 Isolated LoRA GGUF: **6 / 8 (75.0%)**
* Base `Qwen/Qwen2.5-Coder-3B-Instruct` (`Q4_K_M`): *(diisi hasil uji Plan C)*
* Plan C `asadeltek-indo-tax-3b.gguf` (`Unified 6.48K`): *(diisi hasil uji Plan C)*

---

## 5. README Bilingual (ID & EN) + Saling Menjelaskan & Cross-Link 2 Repo HF
1. **`lensetek/asadeltek-indo-tax-3b` (`README.md`):**
   * Menjelaskan model Unified 3B (`asadeltek-indo-tax-3b.gguf`), kemampuan 4 domain + `run_python_calc`, panduan Quick Start `llama-server`, dan tabel benchmark gabungan 5 model.
   * **Menjelaskan & menautkan** ke repo saudara **`https://huggingface.co/lensetek/asadeltek-indo-tax-moe-5b`** (versi `Qwen3-1.7B` MoE 5B & 4 Isolated LoRA, kapan memilih `3b` Unified vs `moe-5b`/Isolated LoRA) serta GitHub `https://github.com/lensetek-int/local-agent-harness`.
2. **`lensetek/asadeltek-indo-tax-moe-5b` (`README.md`):**
   * Diperbarui agar **menjelaskan & menautkan** ke **`https://huggingface.co/lensetek/asadeltek-indo-tax-3b`** (`asadeltek-indo-tax-3b.gguf`) beserta tabel benchmark gabungan terbaru.
3. **`audit_moe/README.md` (GitHub):**
   * Diperbarui dengan tabel benchmark gabungan 5 model dan link kedua repo HF.

---

## 6. Rilis & Cleanup
1. Buat repo HF baru `lensetek/asadeltek-indo-tax-3b` dan upload `asadeltek-indo-tax-3b.gguf` + `README.md` + `benchmark_results_plan_c.json`.
2. Push pembaruan `README.md` pada `lensetek/asadeltek-indo-tax-moe-5b`.
3. Daftarkan `asadeltek-indo-tax-3b` ke `cli-agent/list.json`, lalu commit & push seluruh perubahan ke GitHub.
4. Hentikan sesi Colab T4 (`colab stop -s plan_c_t4`).
