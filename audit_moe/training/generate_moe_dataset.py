"""Generator dataset ChatML berskala + validator otomatis untuk 4 Expert Audit, Akuntansi & Pajak MoE."""

import argparse
import json
from pathlib import Path
import random
import sys
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from runtime.tax_engine import (
    calculate_fiscal_reconciliation,
    calculate_ppn,
    calculate_pph21_ter,
    calculate_withholding_tax,
)
from training.schemas import TOOL_DEFINITIONS

OUTPUT_DIR = Path(__file__).resolve().parent / "datasets"
VALID_TOOL_NAMES = {t["name"] for t in TOOL_DEFINITIONS}

SYSTEM_PROMPTS: dict[str, str] = {
    "expert_1_accounting": (
        "Anda adalah Akuntan Senior Indonesia (SAK, SAK-EP, PSAP/BUMD). "
        "Petakan transaksi ke Chart of Accounts dan hasilkan jurnal berimbang dalam JSON."
    ),
    "expert_2_audit": (
        "Anda adalah Auditor Keuangan & Analis Kinerja. "
        "Hitung EBITDA, rasio keuangan, varians RKAP, proyeksi proforma, dan temuan KKA dalam JSON."
    ),
    "expert_3_tax_id": (
        "Anda adalah Konsultan Pajak Indonesia (UU HPP, PMK 131/2024, PP 58/2023). "
        "Tentukan objek PPh/PPN dan hitung pajak atau koreksi fiskal dalam JSON."
    ),
    "expert_4_agentic": (
        "Anda adalah Agentic Runtime Orchestrator. "
        "Panggil tool Python (RWED, Excel template, DOCX/PDF/OCR, SQLite3, Dashboard non-HTML) "
        "dalam format JSON tool_calls yang valid dan aman."
    ),
}


def _msg(system_key: str, user_text: str, assistant_obj: dict[str, Any]) -> dict[str, Any]:
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPTS[system_key]},
            {"role": "user", "content": user_text},
            {"role": "assistant", "content": json.dumps(assistant_obj, ensure_ascii=False)},
        ]
    }


def gen_accounting_samples(n: int, rng: random.Random) -> list[dict[str, Any]]:
    """Menghasilkan sampel Expert 1: jurnal penerimaan, beban, penyusutan, dan tagihan."""
    templates = [
        ("Penerimaan LPP Loket {lokasi} tgl {tgl} pelunasan rekening air", "1110", "Kas di Loket", "1130", "Piutang Usaha Air"),
        ("Penetapan Rekap DRD bulan {bln} tagihan air pelanggan", "1130", "Piutang Usaha Air", "4110", "Pendapatan Penjualan Air"),
        ("Pembayaran beban bahan kimia pengolahan air via Bank {lokasi}", "5120", "Beban Bahan Kimia", "1120", "Kas di Bank"),
        ("Pembayaran beban listrik pompa distribusi {lokasi}", "5130", "Beban Listrik & Energi", "1120", "Kas di Bank"),
        ("Jurnal penyesuaian penyusutan aset tetap instalasi bulan {bln}", "5210", "Beban Penyusutan Aset Tetap", "1290", "Akumulasi Penyusutan"),
        ("Pembentukan penyisihan piutang ragu-ragu pelanggan air {bln}", "5220", "Beban Kerugian Piutang", "1139", "Cadangan Kerugian Piutang"),
    ]
    lokasi_list = ["Kantor Pusat", "Cabang Utara", "Cabang Selatan", "Koperasi", "Unit IKK"]
    samples: list[dict[str, Any]] = []
    for i in range(n):
        desc_tpl, d_code, d_name, c_code, c_name = templates[i % len(templates)]
        nominal = rng.randint(5, 950) * 100_000
        tgl = f"2026-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}"
        bln = f"{rng.randint(1,12):02d}/2026"
        desc = desc_tpl.format(lokasi=rng.choice(lokasi_list), tgl=tgl, bln=bln)
        user_txt = f"Buatkan jurnal untuk transaksi berikut: {desc} sebesar Rp {nominal:,}."
        obj = {
            "tanggal": tgl,
            "uraian": desc,
            "lines": [
                {"account_code": d_code, "account_name": d_name, "debit": nominal, "credit": 0},
                {"account_code": c_code, "account_name": c_name, "debit": 0, "credit": nominal},
            ],
            "balanced": True,
        }
        samples.append(_msg("expert_1_accounting", user_txt, obj))
    return samples


def gen_audit_samples(n: int, rng: random.Random) -> list[dict[str, Any]]:
    """Menghasilkan sampel Expert 2: EBITDA, rasio, varians RKAP, dan proyeksi proforma."""
    samples: list[dict[str, Any]] = []
    for i in range(n):
        mode = i % 3
        if mode == 0:
            ebit = rng.randint(200, 3000) * 1_000_000
            depr = rng.randint(50, 600) * 1_000_000
            amort = rng.randint(10, 100) * 1_000_000
            ebitda = ebit + depr + amort
            user_txt = f"Laba Usaha Rp {ebit:,}, Penyusutan Rp {depr:,}, Amortisasi Rp {amort:,}. Hitung EBITDA dan catatan auditnya."
            obj = {
                "metrik": "EBITDA",
                "ebitda": ebitda,
                "catatan_audit": "Verifikasi konsistensi metode penyusutan pada KKA Aset Tetap.",
            }
        elif mode == 1:
            rkap = rng.randint(500, 5000) * 1_000_000
            realisasi = int(rkap * rng.uniform(0.75, 1.25))
            selisih = realisasi - rkap
            pct = round((selisih / rkap) * 100, 2)
            status = "Favorable" if selisih >= 0 else "Unfavorable"
            user_txt = f"Anggaran RKAP Pendapatan Rp {rkap:,}, Realisasi Rp {realisasi:,}. Hitung varians RKAP."
            obj = {
                "metrik": "Analisis Varians RKAP",
                "anggaran": rkap,
                "realisasi": realisasi,
                "varians_nominal": selisih,
                "varians_persen": pct,
                "status": status,
            }
        else:
            aset_lancar = rng.randint(300, 4000) * 1_000_000
            utang_lancar = rng.randint(150, 2500) * 1_000_000
            cr = round(aset_lancar / utang_lancar, 2)
            user_txt = f"Aset Lancar Rp {aset_lancar:,}, Liabilitas Jangka Pendek Rp {utang_lancar:,}. Hitung Current Ratio dan risiko likuiditas."
            obj = {
                "metrik": "Current Ratio",
                "current_ratio": cr,
                "risiko_likuiditas": "Rendah" if cr >= 1.5 else ("Sedang" if cr >= 1.0 else "Tinggi"),
            }
        samples.append(_msg("expert_2_audit", user_txt, obj))
    return samples


def gen_tax_samples(n: int, rng: random.Random) -> list[dict[str, Any]]:
    """Menghasilkan sampel Expert 3 menggunakan Tax Rule Engine deterministik agar angka 100% akurat."""
    samples: list[dict[str, Any]] = []
    for i in range(n):
        mode = i % 4
        if mode == 0:
            dpp = rng.randint(10, 500) * 1_000_000
            lux = (i % 8 == 0)
            res = calculate_ppn(dpp, is_luxury_goods=lux)
            label = "barang mewah" if lux else "jasa/barang non-mewah"
            user_txt = f"Hitung PPN atas penyerahan {label} dengan nilai kontrak/DPP Rp {dpp:,}."
            samples.append(_msg("expert_3_tax_id", user_txt, res))
        elif mode == 1:
            dpp = rng.randint(5, 250) * 1_000_000
            has_npwp = (i % 3 != 0)
            tax_type = "PPH_23_JASA" if i % 2 == 0 else "PPH_4_2_SEWA_TANAH_BANGUNAN"
            res = calculate_withholding_tax(tax_type, dpp, has_npwp=has_npwp)
            npwp_txt = "ber-NPWP" if has_npwp else "tanpa NPWP"
            desc = "jasa konsultan/audit" if tax_type == "PPH_23_JASA" else "sewa gedung kantor"
            user_txt = f"Pembayaran {desc} ke rekanan {npwp_txt} sebesar Rp {dpp:,}. Hitung pemotongan PPh."
            samples.append(_msg("expert_3_tax_id", user_txt, res))
        elif mode == 2:
            bruto = rng.randint(6, 35) * 1_000_000
            rate = rng.choice([0.5, 1.5, 2.5, 5.0, 9.0])
            cat = rng.choice(["A", "B", "C"])
            res = calculate_pph21_ter(bruto, ter_rate_percent=rate, category=cat)
            user_txt = f"Karyawan kategori TER {cat} dengan penghasilan bruto bulanan Rp {bruto:,} dan tarif TER {rate}%. Hitung PPh 21."
            samples.append(_msg("expert_3_tax_id", user_txt, res))
        else:
            komersial = rng.randint(500, 4000) * 1_000_000
            pos = rng.randint(10, 150) * 1_000_000
            neg = rng.randint(5, 100) * 1_000_000
            res = calculate_fiscal_reconciliation(
                komersial,
                positive_corrections=[{"item": "Biaya Natura/Sanksi", "amount": pos}],
                negative_corrections=[{"item": "Bunga Deposito Final", "amount": neg}],
            )
            user_txt = (
                f"Laba komersial Rp {komersial:,}, koreksi fiskal positif Rp {pos:,}, "
                f"koreksi negatif Rp {neg:,}. Hitung PKP dan PPh Badan 22%."
            )
            samples.append(_msg("expert_3_tax_id", user_txt, res))
    return samples


def gen_agentic_samples(n: int, rng: random.Random) -> list[dict[str, Any]]:
    """Menghasilkan sampel Expert 4: pemanggilan tool RWED, Excel, OCR, SQLite3, dan Dashboard."""
    samples: list[dict[str, Any]] = []
    folders = ["Perumdam_Seruyan", "Audit_2026", "Klien_BUMD", "Laporan_Q2"]
    for i in range(n):
        folder = rng.choice(folders)
        mode = i % 4
        if mode == 0:
            user_txt = f"Scan seluruh file di folder {folder} lalu periksa struktur template Neraca Lajur 2026.xlsx."
            calls = [
                {"name": "list_client_files", "arguments": {"directory": folder, "recursive": True}},
                {"name": "inspect_excel_template", "arguments": {"file_path": f"{folder}/Neraca Lajur 2026.xlsx", "max_rows": 25}},
            ]
        elif mode == 1:
            user_txt = f"Ekstrak teks scan PDF faktur pajak di {folder}/scan_faktur.pdf menggunakan OCR lokal."
            calls = [
                {"name": "read_document_or_ocr", "arguments": {"file_path": f"{folder}/scan_faktur.pdf", "use_ocr": True}},
            ]
        elif mode == 2:
            user_txt = f"Cek keseimbangan neraca pada database {folder}/ledger.db dan buat dashboard Excel native."
            calls = [
                {"name": "verify_accounting_balance", "arguments": {"db_path": f"{folder}/ledger.db"}},
                {"name": "build_non_html_dashboard", "arguments": {"mode": "excel_native", "db_path": f"{folder}/ledger.db", "output_excel_path": f"{folder}/Laporan_Baru_2026/Dashboard_2026.xlsx"}},
            ]
        else:
            user_txt = f"Ambil 10 jurnal terakhir dari {folder}/ledger.db secara aman."
            calls = [
                {"name": "run_sqlite_query", "arguments": {"db_path": f"{folder}/ledger.db", "sql": "SELECT id, entry_date, description FROM journals ORDER BY id DESC LIMIT 10", "params": []}},
            ]
        samples.append(_msg("expert_4_agentic", user_txt, {"tool_calls": calls}))
    return samples


def validate_dataset(expert_name: str, records: list[dict[str, Any]]) -> None:
    """Validator otomatis untuk memastikan JSON valid, jurnal seimbang, dan nama tool sah."""
    for idx, rec in enumerate(records):
        assistant_raw = rec["messages"][-1]["content"]
        parsed = json.loads(assistant_raw)
        if expert_name == "expert_1_accounting":
            d = sum(line["debit"] for line in parsed["lines"])
            c = sum(line["credit"] for line in parsed["lines"])
            if d != c or d <= 0:
                raise ValueError(f"Record {idx} expert_1 tidak seimbang: {d} != {c}")
        elif expert_name == "expert_4_agentic":
            for tc in parsed["tool_calls"]:
                if tc["name"] not in VALID_TOOL_NAMES:
                    raise ValueError(f"Tool tidak valid pada record {idx}: {tc['name']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generator dataset MoE Audit/Akuntansi/Pajak")
    parser.add_argument("--per-expert", type=int, default=250, help="Jumlah sampel per expert (default: 250)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    rng = random.Random(args.seed)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    datasets = {
        "expert_1_accounting": gen_accounting_samples(args.per_expert, rng),
        "expert_2_audit": gen_audit_samples(args.per_expert, rng),
        "expert_3_tax_id": gen_tax_samples(args.per_expert, rng),
        "expert_4_agentic": gen_agentic_samples(args.per_expert, rng),
    }

    for name, records in datasets.items():
        validate_dataset(name, records)
        out_path = OUTPUT_DIR / f"{name}.jsonl"
        with out_path.open("w", encoding="utf-8") as f:
            for item in records:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        print(f"Validated & wrote {len(records)} records -> {out_path}")


if __name__ == "__main__":
    main()
