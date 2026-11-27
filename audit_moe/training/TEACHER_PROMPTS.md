# Teacher Prompt Templates (Untuk Model Tertinggi)

Gunakan prompt di bawah ini saat kamu sudah beralih ke **model tertinggi** untuk menghasilkan data latih (JSONL ChatML) bagi ke-4 expert MoE.

> **Aturan Wajib:**
> 1. Gunakan **100% nama entitas, NPWP, dan angka fiktif** (jangan pernah menempelkan data asli klien).
> 2. Output wajib berupa **JSONL murni** (1 JSON object per baris, tanpa markdown fence/penjelasan di luar JSON) agar bisa langsung divalidasi oleh `validate_and_merge_jsonl.py`.

---

## Prompt Expert 1 — Accounting & Journaling
```text
Buatkan 50 baris dataset JSONL (1 baris = 1 JSON object) format ChatML untuk melatih model akuntansi Indonesia (SAK, SAK-EP, PSAP/BUMD).
Setiap baris harus mengikuti format persis:
{"messages":[{"role":"system","content":"Anda adalah Akuntan Senior Indonesia (SAK, SAK-EP, PSAP/BUMD). Petakan transaksi ke Chart of Accounts dan hasilkan jurnal berimbang dalam JSON."},{"role":"user","content":"<skenario transaksi realistis bervariasi: LPP loket, rekap DRD, mutasi bank, pengakuan pendapatan, beban dibayar dimuka, penyusutan, penyisihan piutang, koreksi jurnal, atau jurnal gabungan PPN+PPh>"},{"role":"assistant","content":"<JSON string berisi: tanggal, uraian, lines:[{account_code, account_name, debit, credit}], balanced:true>"}]}

Syarat ketat:
- Seluruh angka debit dan credit harus integer Rupiah bulat.
- Total debit WAJIB sama persis dengan total credit dan > 0.
- Variasikan gaya bahasa (memo direksi, catatan staf loket, rekening koran, instruksi auditor).
- Gunakan 100% data fiktif.
```

---

## Prompt Expert 2 — Audit, Rasio & Proyeksi Keuangan
```text
Buatkan 50 baris dataset JSONL (1 baris = 1 JSON object) format ChatML untuk melatih model auditor keuangan & analis kinerja Indonesia.
Format setiap baris:
{"messages":[{"role":"system","content":"Anda adalah Auditor Keuangan & Analis Kinerja. Hitung EBITDA, rasio keuangan, varians RKAP, proyeksi proforma, dan temuan KKA dalam JSON."},{"role":"user","content":"<skenario audit realistis: hitung EBITDA, Current Ratio, DER, efisiensi penagihan piutang, analisis varians RKAP, proyeksi arus kas/proforma, uji cut-off, atau temuan selisih rekonsiliasi bank>"},{"role":"assistant","content":"<JSON string berisi metrik, hasil_hitung, status/risiko, dan catatan_audit/rekomendasi>"}]}

Syarat ketat:
- Pastikan seluruh perhitungan matematika 100% konsisten dengan angka di prompt user.
- Gunakan 100% data fiktif.
```

---

## Prompt Expert 3 — Perpajakan Indonesia Lengkap
```text
Buatkan 50 baris dataset JSONL (1 baris = 1 JSON object) format ChatML untuk melatih model konsultan pajak Indonesia (UU HPP, PMK 131/2024 PPN 12% x DPP Nilai Lain 11/12, PP 58/2023 PPh 21 TER).
Format setiap baris:
{"messages":[{"role":"system","content":"Anda adalah Konsultan Pajak Indonesia (UU HPP, PMK 131/2024, PP 58/2023). Tentukan objek PPh/PPN dan hitung pajak atau koreksi fiskal dalam JSON."},{"role":"user","content":"<skenario pajak realistis: PPN barang/jasa non-mewah vs mewah, PPh 23 ber-NPWP vs non-NPWP, PPh 4(2) sewa/UMKM, PPh 22 pengadaan, PPh 21 TER, koreksi fiskal positif/negatif, atau ekualisasi PPN vs omzet PPh Badan>"},{"role":"assistant","content":"<JSON string berisi jenis_pajak, dasar_hukum, dpp, tarif_persen, pajak_terutang, atau hasil_rekonsiliasi_fiskal>"}]}

Syarat ketat:
- Untuk PPN non-mewah gunakan PMK 131/2024 (tarif 12% x DPP Nilai Lain 11/12 = efektif 11%).
- Untuk PPh 23 tanpa NPWP kenakan tarif 100% lebih tinggi.
- Semua angka harus integer Rupiah bulat dan 100% konsisten.
```

---

## Prompt Expert 4 — Agentic Tool-Caller (RWED, Excel, OCR, SQLite3, Dashboard)
```text
Buatkan 50 baris dataset JSONL (1 baris = 1 JSON object) format ChatML untuk melatih Agentic Orchestrator yang hanya boleh memanggil tool berikut:
[list_client_files, inspect_excel_template, write_excel_preserving_template, read_document_or_ocr, rwed_file, run_sqlite_query, verify_accounting_balance, build_non_html_dashboard]

Format setiap baris:
{"messages":[{"role":"system","content":"Anda adalah Agentic Runtime Orchestrator. Panggil tool Python (RWED, Excel template, DOCX/PDF/OCR, SQLite3, Dashboard non-HTML) dalam format JSON tool_calls yang valid dan aman."},{"role":"user","content":"<instruksi kerja realistis: olah folder klien fiktif, baca .xls/.xlsx, OCR scan PDF faktur, query SQLite3 read-only, cek balance gate, atau buat dashboard Excel native/desktop GUI>"},{"role":"assistant","content":"<JSON string berisi {\"tool_calls\":[{\"name\":\"...\",\"arguments\":{...}}]}>"}]}

Syarat ketat:
- Jangan pernah mengarang nama tool di luar daftar di atas.
- Untuk rwed_file action=delete, confirm_delete harus false jika belum ada konfirmasi user.
- Untuk write_excel_preserving_template, output_path tidak boleh sama dengan template_path.
```
