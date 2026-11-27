# Blueprint: Audit, Akuntansi & Pajak Indonesia MoE LLM (`Qwen2.5-3B-Instruct`)

Dokumen ini adalah cetak biru teknis untuk membangun **Agentic MoE LLM** berbasis **`Qwen2.5-3B-Instruct`** yang:
- Dapat di-finetune per-expert di **Google Colab T4 (16 GB VRAM)**.
- Digabung menjadi model **MoE (~8.5B–9B total parameter, ~4B aktif per token)** dengan `mergekit-moe`.
- Dapat dijalankan **100% offline/lokal** dalam format **GGUF `Q4_K_M` (~5.5 GB)** di laptop **RAM 15.4 GB (CPU `llama.cpp`)** maupun **VPS tanpa GPU (RAM 8–16 GB)**.

---

## 1. Arsitektur Model MoE

| Komponen | Spesifikasi |
| :--- | :--- |
| **Base Model** | `Qwen/Qwen2.5-3B-Instruct` |
| **Jumlah Expert** | 4 Expert Spesialis |
| **Routing** | Top-2 Experts aktif per token (`experts_per_token: 2`) |
| **Total Parameter** | ~8.5B – 9.0B (shared Attention, 4x MLP/FFN) |
| **Active Parameter** | ~4.0B per token |
| **Quantization Target** | GGUF `Q4_K_M` (~5.5 GB file, ~6.5–7.5 GB RAM saat jalan) |

### Pembagian 4 Expert
1. **Expert 1 — Accounting & Journaling (`expert_1_accounting`)**
   - Pemetaan transaksi mentah (LPP loket, rekap DRD, rekening koran, invoice) ke **Chart of Accounts (CoA)**.
   - Jurnal umum, jurnal penyesuaian (penyusutan, akrual, penyisihan piutang), serta struktur **Neraca Lajur, Laba Rugi, Neraca, Arus Kas, Perubahan Ekuitas** (SAK, SAK-EP, PSAP/BUMD).
2. **Expert 2 — Audit, Rasio & Proyeksi (`expert_2_audit`)**
   - Perhitungan & interpretasi **EBITDA**, rasio likuiditas, solvabilitas, profitabilitas, dan efisiensi penagihan.
   - **Proyeksi Keuangan (*Financial Projection / Proforma*)** dan **Analisis Varians RKAP** (Realisasi vs Anggaran).
   - Penyusunan **Kertas Kerja Audit (KKA)**, *audit sampling*, deteksi anomali/duplikasi, dan **Audit Trail**.
3. **Expert 3 — Perpajakan Indonesia Lengkap (`expert_3_tax_id`)**
   - Klasifikasi objek & tarif **PPh 21 (TER)**, **PPh 22, 23, 26, 4(2)**, **PPh Badan (25/29)**, dan **PPN (Masukan/Keluaran)**.
   - **Koreksi Fiskal Positif & Negatif** (rekonsiliasi Laba Rugi komersial -> fiskal).
   - **Ekualisasi Omzet PPN vs Peredaran Bruto PPh Badan**.
4. **Expert 4 — Agentic Tool-Caller (`expert_4_agentic`)**
   - Orkestrasi **RWED File** (`read`, `write`, `edit`, `delete` dengan guard).
   - Pembuatan query **SQLite3**, inspeksi & pengisian **template Excel klien** (`.xls`/`.xlsx`), pemanggilan **DOCX/PDF/OCR**, serta pembuatan **Dashboard Interaktif (Non-HTML)**.

---

## 2. Arsitektur Runtime: Brain + Deterministic Hands

> **Prinsip Utama:** LLM tidak boleh menghitung saldo secara manual di teks atau menimpa sel Excel mentah. LLM bertugas sebagai **Planner & JSON Tool-Caller**, sedangkan **Python** menjalankan kalkulasi, database, dan manipulasi file secara deterministik.

```text
[User Prompt / Folder Klien]
        │
        ▼
[MoE LLM (GGUF Q4_K_M via llama.cpp)]  <── Konteks Schema Excel, CoA, & SQLite3
        │
        │ (JSON Tool Calls)
        ▼
[Python Agent Runtime]
  ├── RWED Sandbox        : Read / Write / Edit / Delete (auto-backup & confirm gate)
  ├── Excel Engine        : xlrd (.xls) + openpyxl (.xlsx template preserver)
  ├── Doc & OCR Engine    : python-docx, pdfplumber, pymupdf, RapidOCR / SmolVLM
  ├── SQLite3 Ledger      : Tabel coa, journals, ledger, tax_items, audit_trail
  ├── Balance Hard-Gate   : Validasi Debit == Kredit & Aktiva == Pasiva + Ekuitas
  └── Dashboard (Non-HTML): Excel Native Chart Dashboard & Desktop GUI (PySide6/Tk)
```

---

## 3. Skema Database Lokal (`SQLite3`)
Database lokal menyimpan seluruh state akuntansi agar rekonsiliasi ribuan baris cepat dan dapat diaudit:
- `coa` (`code`, `name`, `category`, `normal_balance`)
- `journals` (`id`, `entry_date`, `source_file`, `description`, `status`, `created_at`)
- `journal_lines` (`id`, `journal_id`, `account_code`, `debit`, `credit`, `tax_code`)
- `tax_items` (`id`, `journal_id`, `tax_type`, `dpp`, `tax_amount`, `fiscal_correction_type`)
- `audit_trail` (`id`, `timestamp`, `actor`, `action`, `target`, `detail_json`)

---

## 4. Pipeline Training (Colab T4 -> Laptop / VPS)
1. **Generate & Kurasi Dataset (`training/generate_moe_dataset.py`):**
   - Hasilkan 1.500–2.000 sampel per expert dalam format ChatML dengan JSON schema tervalidasi.
2. **Fine-Tune 4 Expert Terpisah di Colab T4:**
   - Gunakan **Unsloth QLoRA (4-bit)** pada `Qwen/Qwen2.5-3B-Instruct` (`max_seq_length=2048`, `r=16`).
   - Simpan hasil merge 16-bit masing-masing expert (`./experts/accounting`, `./experts/audit`, `./experts/tax_id`, `./experts/agentic`).
3. **Gabungkan Menjadi MoE (`config/mergekit_moe_3b.yaml`):**
   - Jalankan `mergekit-moe` (Mixtral-style, `top_k: 2`).
4. **Router Calibration (Opsional):**
   - Fine-tune singkat khusus layer *gate/router* dengan campuran data dari 4 expert.
5. **Export & Quantize ke GGUF:**
   - Convert ke `F16.gguf` lalu quantize ke **`Q4_K_M`** menggunakan `llama-quantize`.

---

## 5. Keamanan & Guardrails
- **Privasi 100% Lokal/Private:** Tidak ada data keuangan, NPWP, atau dokumen klien yang dikirim ke API eksternal.
- **Non-Destructive File Policy:** File asli klien tidak pernah ditimpa langsung; hasil kerja diarahkan ke folder output baru (misal `Laporan_Baru_2026`).
- **Safe RWED Gate:** Operasi `delete` atau overwrite file wajib melalui konfirmasi pengguna dan mencatat jejak di `audit_trail`.
- **Balance Hard-Gate:** Sistem menolak ekspor laporan final jika `Total Debit != Total Kredit` atau Neraca tidak seimbang.
- **Keamanan VPS (jika di-deploy di VPS):** Bind `llama.cpp` ke `127.0.0.1` saja, akses melalui VPN/SSH Tunnel atau Reverse Proxy ber-HTTPS + autentikasi.
