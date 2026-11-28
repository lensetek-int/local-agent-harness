"""Builder 480 sampel khusus `run_python_calc` (Audit, Akuntansi & Pajak Indonesia) + merger `unified_plan_c_6480.jsonl`.

Setiap kode Python yang dihasilkan DIEKSEKUSI LANGSUNG di sandbox AST `runtime.tools.run_python_calc`
dan hasil angkanya diverifikasi terhadap perhitungan deterministik (`Decimal` / `tax_engine.py`).
"""

import argparse
from decimal import Decimal, ROUND_HALF_UP
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
from runtime.tools import run_python_calc
from training.teacher_corpus import ENTITIES, SYSTEM_PROMPTS, VENDORS
from training.validate_and_merge_jsonl import validate_record

DATASETS_DIR = Path(__file__).resolve().parent / "datasets"

PY_PREFIXES = [
    "Gunakan tool Python `run_python_calc` (Decimal) untuk menghitung secara eksak:",
    "Delegasikan kalkulasi berikut ke Python melalui `run_python_calc` agar bebas galat pembulatan:",
    "Tulis kode Python Decimal dan panggil `run_python_calc` untuk menyelesaikan perhitungan ini:",
    "Jalankan perhitungan akuntansi/audit berikut menggunakan `run_python_calc`:",
    "Jangan menebak angka secara manual; gunakan `run_python_calc` (Python Decimal) untuk:",
]


def _r(val: Decimal) -> int:
    return int(val.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def build_python_calc_sample(idx: int, rng: random.Random) -> tuple[dict[str, Any], Any]:
    """Menghasilkan 1 sampel `run_python_calc` (ChatML) beserta nilai ground-truth `expected_result`."""
    ent = rng.choice(ENTITIES)
    vendor = rng.choice(VENDORS)
    prefix = rng.choice(PY_PREFIXES)
    batch_id = rng.randint(1000, 99999)
    pattern = idx % 12

    if pattern == 0:
        # 1. EBITDA & EBITDA Margin
        rev = rng.randint(3000, 45000) * 1_000_000
        ebit = _r(Decimal(rev) * Decimal(str(round(rng.uniform(0.08, 0.30), 3))))
        depr = _r(Decimal(rev) * Decimal(str(round(rng.uniform(0.04, 0.14), 3))))
        amort = rng.randint(15, 300) * 1_000_000
        user_txt = (
            f"[Calc #{batch_id}] {prefix} Data {ent}: Pendapatan Usaha Rp {rev:,}, "
            f"EBIT Rp {ebit:,}, Penyusutan Rp {depr:,}, Amortisasi Rp {amort:,}. "
            f"Hitung EBITDA (Rupiah bulat) dan EBITDA Margin (% 2 desimal)."
        )
        code = (
            f"rev = Decimal('{rev}')\n"
            f"ebit = Decimal('{ebit}')\n"
            f"depr = Decimal('{depr}')\n"
            f"amort = Decimal('{amort}')\n"
            "ebitda = ebit + depr + amort\n"
            "margin = ((ebitda / rev) * Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)\n"
            "result = {'ebitda': int(ebitda), 'ebitda_margin_persen': float(margin)}"
        )
        ebitda_exp = ebit + depr + amort
        margin_exp = float(((Decimal(ebitda_exp) / Decimal(rev)) * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        expected: Any = {"ebitda": ebitda_exp, "ebitda_margin_persen": margin_exp}

    elif pattern == 1:
        # 2. Analisis Varians RKAP (Pendapatan & Beban)
        rkap_rev = rng.randint(4000, 30000) * 1_000_000
        real_rev = _r(Decimal(rkap_rev) * Decimal(str(round(rng.uniform(0.75, 1.22), 3))))
        rkap_exp = _r(Decimal(rkap_rev) * Decimal(str(round(rng.uniform(0.68, 0.88), 3))))
        real_exp = _r(Decimal(rkap_exp) * Decimal(str(round(rng.uniform(0.80, 1.18), 3))))
        user_txt = (
            f"[Calc #{batch_id}] {prefix} Varians RKAP {ent}: Anggaran Pendapatan Rp {rkap_rev:,} "
            f"(Realisasi Rp {real_rev:,}), Anggaran Beban Rp {rkap_exp:,} (Realisasi Rp {real_exp:,}). "
            f"Hitung varians nominal dan persen keduanya."
        )
        code = (
            f"rkap_rev, real_rev = Decimal('{rkap_rev}'), Decimal('{real_rev}')\n"
            f"rkap_exp, real_exp = Decimal('{rkap_exp}'), Decimal('{real_exp}')\n"
            "var_rev = real_rev - rkap_rev\n"
            "var_exp = real_exp - rkap_exp\n"
            "pct_rev = ((var_rev / rkap_rev) * Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)\n"
            "pct_exp = ((var_exp / rkap_exp) * Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)\n"
            "result = {'varians_pendapatan': int(var_rev), 'varians_pendapatan_persen': float(pct_rev), 'varians_beban': int(var_exp), 'varians_beban_persen': float(pct_exp)}"
        )
        vr, ve = real_rev - rkap_rev, real_exp - rkap_exp
        expected = {
            "varians_pendapatan": vr,
            "varians_pendapatan_persen": float(((Decimal(vr) / Decimal(rkap_rev)) * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
            "varians_beban": ve,
            "varians_beban_persen": float(((Decimal(ve) / Decimal(rkap_exp)) * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
        }

    elif pattern == 2:
        # 3. Proyeksi Keuangan Proforma 1-5 Tahun (Majemuk Decimal)
        rev0 = rng.randint(2000, 25000) * 1_000_000
        exp0 = _r(Decimal(rev0) * Decimal(str(round(rng.uniform(0.70, 0.88), 2))))
        g_rev = rng.choice([5, 7, 8, 10, 12, 15])
        g_exp = rng.choice([3, 4, 6, 8, 9])
        yrs = rng.choice([1, 2, 3, 5])
        user_txt = (
            f"[Calc #{batch_id}] {prefix} Proyeksi Proforma {yrs} tahun ke depan untuk {ent}: "
            f"Pendapatan awal Rp {rev0:,} (tumbuh {g_rev}%/thn) dan Beban awal Rp {exp0:,} (naik {g_exp}%/thn). "
            f"Hitung proyeksi pendapatan, beban, dan laba usaha pada tahun ke-{yrs}."
        )
        code = (
            f"rev0, exp0 = Decimal('{rev0}'), Decimal('{exp0}')\n"
            f"g_rev = Decimal('1') + Decimal('{g_rev}') / Decimal('100')\n"
            f"g_exp = Decimal('1') + Decimal('{g_exp}') / Decimal('100')\n"
            f"rev_n = int((rev0 * (g_rev ** {yrs})).quantize(Decimal('1'), rounding=ROUND_HALF_UP))\n"
            f"exp_n = int((exp0 * (g_exp ** {yrs})).quantize(Decimal('1'), rounding=ROUND_HALF_UP))\n"
            "result = {'proyeksi_pendapatan': rev_n, 'proyeksi_beban': exp_n, 'proyeksi_laba_usaha': rev_n - exp_n}"
        )
        rn = _r(Decimal(rev0) * ((Decimal("1") + Decimal(g_rev) / Decimal("100")) ** yrs))
        en = _r(Decimal(exp0) * ((Decimal("1") + Decimal(g_exp) / Decimal("100")) ** yrs))
        expected = {"proyeksi_pendapatan": rn, "proyeksi_beban": en, "proyeksi_laba_usaha": rn - en}

    elif pattern == 3:
        # 4. Current Ratio & Debt-to-Equity Ratio (DER)
        al = rng.randint(500, 12000) * 1_000_000
        ul = rng.randint(300, 7000) * 1_000_000
        tu = ul + rng.randint(200, 8000) * 1_000_000
        eq = rng.randint(1500, 20000) * 1_000_000
        user_txt = (
            f"[Calc #{batch_id}] {prefix} Posisi Neraca {ent}: Aset Lancar Rp {al:,}, "
            f"Utang Lancar Rp {ul:,}, Total Liabilitas Rp {tu:,}, Total Ekuitas Rp {eq:,}. "
            f"Hitung Current Ratio dan DER (2 desimal)."
        )
        code = (
            f"al, ul = Decimal('{al}'), Decimal('{ul}')\n"
            f"tu, eq = Decimal('{tu}'), Decimal('{eq}')\n"
            "cr = (al / ul).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)\n"
            "der = (tu / eq).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)\n"
            "result = {'current_ratio': float(cr), 'der': float(der)}"
        )
        expected = {
            "current_ratio": float((Decimal(al) / Decimal(ul)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
            "der": float((Decimal(tu) / Decimal(eq)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
        }

    elif pattern == 4:
        # 5. DSCR (Debt Service Coverage Ratio)
        ebitda = rng.randint(1200, 15000) * 1_000_000
        pokok = rng.randint(400, 5000) * 1_000_000
        bunga = rng.randint(100, 1800) * 1_000_000
        user_txt = (
            f"[Calc #{batch_id}] {prefix} Analisis covenant kredit {ent}: EBITDA Rp {ebitda:,}, "
            f"angsuran pokok Rp {pokok:,}, dan beban bunga Rp {bunga:,}. Hitung total debt service dan DSCR."
        )
        code = (
            f"ebitda = Decimal('{ebitda}')\n"
            f"ds = Decimal('{pokok}') + Decimal('{bunga}')\n"
            "dscr = (ebitda / ds).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)\n"
            "result = {'total_debt_service': int(ds), 'dscr': float(dscr)}"
        )
        ds_val = pokok + bunga
        expected = {
            "total_debt_service": ds_val,
            "dscr": float((Decimal(ebitda) / Decimal(ds_val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
        }

    elif pattern == 5:
        # 6. Efisiensi Penagihan Piutang BUMD Air Minum (DRD vs Penerimaan)
        drd = rng.randint(1500, 18000) * 1_000_000
        terima = _r(Decimal(drd) * Decimal(str(round(rng.uniform(0.68, 0.99), 3))))
        user_txt = (
            f"[Calc #{batch_id}] {prefix} Kinerja penagihan {ent}: total DRD Rp {drd:,}, "
            f"total penerimaan kas penagihan Rp {terima:,}. Hitung tunggakan dan rasio efisiensi penagihan (%)."
        )
        code = (
            f"drd, terima = Decimal('{drd}'), Decimal('{terima}')\n"
            "ef = ((terima / drd) * Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)\n"
            "result = {'tunggakan': int(drd - terima), 'efisiensi_penagihan_persen': float(ef)}"
        )
        expected = {
            "tunggakan": drd - terima,
            "efisiensi_penagihan_persen": float(((Decimal(terima) / Decimal(drd)) * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
        }

    elif pattern == 6:
        # 7. Penetapan Materialitas Audit SA 320
        rev = rng.randint(12000, 200000) * 1_000_000
        pct = rng.choice(["0.5", "1.0", "1.5", "2.0"])
        user_txt = (
            f"[Calc #{batch_id}] {prefix} Perencanaan KKA SA 320 {ent}: Pendapatan Usaha Rp {rev:,}. "
            f"Hitung Overall Materiality ({pct}%), Performance Materiality (75% dari OM), dan Clearly Trivial (5% dari OM)."
        )
        code = (
            f"rev = Decimal('{rev}')\n"
            f"om = (rev * Decimal('{pct}') / Decimal('100')).quantize(Decimal('1'), rounding=ROUND_HALF_UP)\n"
            "pm = (om * Decimal('0.75')).quantize(Decimal('1'), rounding=ROUND_HALF_UP)\n"
            "ct = (om * Decimal('0.05')).quantize(Decimal('1'), rounding=ROUND_HALF_UP)\n"
            "result = {'overall_materiality': int(om), 'performance_materiality': int(pm), 'clearly_trivial': int(ct)}"
        )
        om = _r(Decimal(rev) * Decimal(pct) / Decimal("100"))
        expected = {
            "overall_materiality": om,
            "performance_materiality": _r(Decimal(om) * Decimal("0.75")),
            "clearly_trivial": _r(Decimal(om) * Decimal("0.05")),
        }

    elif pattern == 7:
        # 8. Rekonsiliasi Bank
        bank = rng.randint(500, 9000) * 1_000_000
        dit = rng.randint(15, 300) * 1_000_000
        osc = rng.randint(10, 250) * 1_000_000
        benar = bank + dit - osc
        giro = rng.randint(1, 20) * 1_000_000
        adm = rng.randint(5, 60) * 100_000
        buku_awal = benar - giro + adm
        user_txt = (
            f"[Calc #{batch_id}] {prefix} Rekonsiliasi bank {ent}: Saldo Rekening Koran Rp {bank:,}, "
            f"DIT Rp {dit:,}, Outstanding Check Rp {osc:,}; Saldo Buku Awal Rp {buku_awal:,}, "
            f"Jasa Giro Rp {giro:,}, Biaya Adm Bank Rp {adm:,}. Hitung saldo disesuaikan dan selisihnya."
        )
        code = (
            f"bank_adj = Decimal('{bank}') + Decimal('{dit}') - Decimal('{osc}')\n"
            f"buku_adj = Decimal('{buku_awal}') + Decimal('{giro}') - Decimal('{adm}')\n"
            "diff = bank_adj - buku_adj\n"
            "result = {'saldo_bank_disesuaikan': int(bank_adj), 'saldo_buku_disesuaikan': int(buku_adj), 'selisih': int(diff), 'seimbang': diff == 0}"
        )
        expected = {
            "saldo_bank_disesuaikan": benar,
            "saldo_buku_disesuaikan": benar,
            "selisih": 0,
            "seimbang": True,
        }

    elif pattern == 8:
        # 9. PPN PMK 131/2024 (Non-Mewah 12% x DPP 11/12 & Barang Mewah 12%)
        dpp = rng.randint(15, 950) * 1_000_000
        lux = (idx % 24 == 8)
        tax_res = calculate_ppn(dpp, is_luxury_goods=lux)
        if lux:
            user_txt = (
                f"[Calc #{batch_id}] {prefix} {ent} membeli barang kena pajak tergolong mewah dari {vendor} "
                f"senilai DPP Rp {dpp:,}. Hitung PPN 12% DPP penuh sesuai PMK 131/2024."
            )
            code = (
                f"dpp = Decimal('{dpp}')\n"
                "ppn = (dpp * Decimal('0.12')).quantize(Decimal('1'), rounding=ROUND_HALF_UP)\n"
                "result = {'dpp_nilai_lain': int(dpp), 'ppn_terutang': int(ppn)}"
            )
        else:
            user_txt = (
                f"[Calc #{batch_id}] {prefix} {ent} melakukan transaksi barang/jasa non-mewah dengan {vendor} "
                f"nilai kontrak Rp {dpp:,}. Hitung DPP Nilai Lain (11/12) dan PPN 12% sesuai PMK 131/2024."
            )
            code = (
                f"dpp = Decimal('{dpp}')\n"
                "dpp_lain = (dpp * Decimal('11') / Decimal('12')).quantize(Decimal('1'), rounding=ROUND_HALF_UP)\n"
                "ppn = ((dpp * Decimal('11') / Decimal('12')) * Decimal('0.12')).quantize(Decimal('1'), rounding=ROUND_HALF_UP)\n"
                "result = {'dpp_nilai_lain': int(dpp_lain), 'ppn_terutang': int(ppn)}"
            )
        expected = {"dpp_nilai_lain": tax_res["dpp_nilai_lain"], "ppn_terutang": tax_res["ppn_terutang"]}

    elif pattern == 9:
        # 10. PPh 23 (NPWP vs non-NPWP) & PPh 4(2) Final
        dpp = rng.randint(10, 500) * 1_000_000
        sub = idx % 3
        if sub == 0:
            tax_res = calculate_withholding_tax("PPH_23_JASA", dpp, has_npwp=True)
            rate_str = "2.0"
            desc = f"jasa audit/konsultan ke {vendor} ber-NPWP (PPh 23 2%)"
        elif sub == 1:
            tax_res = calculate_withholding_tax("PPH_23_JASA", dpp, has_npwp=False)
            rate_str = "4.0"
            desc = f"jasa teknis ke {vendor} tanpa NPWP (PPh 23 2% x 200% = 4%)"
        else:
            tax_res = calculate_withholding_tax("PPH_4_2_SEWA_TANAH_BANGUNAN", dpp)
            rate_str = "10.0"
            desc = f"sewa gedung kantor ke {vendor} (PPh Final 4(2) 10%)"
        user_txt = (
            f"[Calc #{batch_id}] {prefix} Pembayaran {desc} oleh {ent} dengan DPP Rp {dpp:,}. "
            f"Hitung potongan PPh dan kas neto yang dibayarkan ke rekanan."
        )
        code = (
            f"dpp = Decimal('{dpp}')\n"
            f"pajak = (dpp * Decimal('{rate_str}') / Decimal('100')).quantize(Decimal('1'), rounding=ROUND_HALF_UP)\n"
            "result = {'pajak_terutang': int(pajak), 'kas_neto': int(dpp - pajak)}"
        )
        expected = {"pajak_terutang": tax_res["pajak_terutang"], "kas_neto": dpp - tax_res["pajak_terutang"]}

    elif pattern == 10:
        # 11. PPh 21 TER (PP 58/2023) & PPh 22 Pengadaan 1.5%
        if idx % 2 == 0:
            bruto = rng.randint(7, 45) * 1_000_000
            rate = rng.choice([0.5, 1.25, 2.0, 3.5, 6.0, 9.0])
            cat = rng.choice(["A", "B", "C"])
            tax_res = calculate_pph21_ter(bruto, ter_rate_percent=rate, category=cat)
            user_txt = (
                f"[Calc #{batch_id}] {prefix} Gaji bruto bulanan pegawai {ent} (TER Kategori {cat}, tarif {rate}%) "
                f"sebesar Rp {bruto:,}. Hitung potongan PPh 21 TER dan gaji neto."
            )
            code = (
                f"bruto = Decimal('{bruto}')\n"
                f"pph21 = (bruto * Decimal('{rate}') / Decimal('100')).quantize(Decimal('1'), rounding=ROUND_HALF_UP)\n"
                "result = {'pph21_terutang': int(pph21), 'gaji_neto': int(bruto - pph21)}"
            )
            expected = {"pph21_terutang": tax_res["pph21_terutang"], "gaji_neto": bruto - tax_res["pph21_terutang"]}
        else:
            dpp = rng.randint(40, 800) * 1_000_000
            tax_res = calculate_withholding_tax("PPH_22_PENGADAAN", dpp, has_npwp=True)
            user_txt = (
                f"[Calc #{batch_id}] {prefix} Pengadaan barang oleh pemungut {ent} dari {vendor} "
                f"dengan DPP Rp {dpp:,} (PPh 22 tarif 1,5%). Hitung PPh 22 terutang."
            )
            code = (
                f"dpp = Decimal('{dpp}')\n"
                "pph22 = (dpp * Decimal('1.5') / Decimal('100')).quantize(Decimal('1'), rounding=ROUND_HALF_UP)\n"
                "result = {'pph22_terutang': int(pph22)}"
            )
            expected = {"pph22_terutang": tax_res["pajak_terutang"]}

    else:
        # 12. Rekonsiliasi Fiskal PPh Badan 22% + Validasi Keseimbangan Jurnal Majemuk
        komersial = rng.randint(800, 9500) * 1_000_000
        pos1 = rng.randint(10, 120) * 1_000_000
        pos2 = rng.randint(15, 160) * 1_000_000
        neg1 = rng.randint(10, 200) * 1_000_000
        tax_res = calculate_fiscal_reconciliation(
            komersial,
            positive_corrections=[{"item": "Sanksi", "amount": pos1}, {"item": "Natura", "amount": pos2}],
            negative_corrections=[{"item": "Final", "amount": neg1}],
            corporate_tax_rate_percent=22.0,
        )
        user_txt = (
            f"[Calc #{batch_id}] {prefix} Rekonsiliasi fiskal PPh Badan {ent}: Laba Komersial Rp {komersial:,}, "
            f"koreksi positif sanksi Rp {pos1:,} & biaya non-deductible Rp {pos2:,}, "
            f"koreksi negatif penghasilan final Rp {neg1:,}. Hitung PKP dan PPh Badan tarif 22%."
        )
        code = (
            f"kom = Decimal('{komersial}')\n"
            f"pos = Decimal('{pos1}') + Decimal('{pos2}')\n"
            f"neg = Decimal('{neg1}')\n"
            "pkp = max(Decimal('0'), kom + pos - neg)\n"
            "pph_badan = (pkp * Decimal('0.22')).quantize(Decimal('1'), rounding=ROUND_HALF_UP)\n"
            "result = {'pkp': int(pkp), 'pph_badan_terutang': int(pph_badan)}"
        )
        expected = {"pkp": tax_res["pkp"], "pph_badan_terutang": tax_res["pph_badan_terutang"]}

    record = {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPTS["expert_4_agentic"]},
            {"role": "user", "content": user_txt},
            {
                "role": "assistant",
                "content": json.dumps(
                    {"tool_calls": [{"name": "run_python_calc", "arguments": {"code": code}}]},
                    ensure_ascii=False,
                ),
            },
        ]
    }
    return record, expected


def generate_verified_python_calc(
    train_count: int,
    eval_count: int,
    existing_prompts: set[str],
    seed: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Menghasilkan sampel train & eval `run_python_calc` yang 100% dieksekusi & diverifikasi di sandbox AST."""
    rng = random.Random(seed)
    seen = set(existing_prompts)
    train_recs: list[dict[str, Any]] = []
    eval_recs: list[dict[str, Any]] = []
    target_total = train_count + eval_count
    idx = 0

    while len(train_recs) + len(eval_recs) < target_total:
        rec, expected = build_python_calc_sample(idx, rng)
        idx += 1

        ok, reason = validate_record("expert_4_agentic", rec)
        if not ok:
            raise RuntimeError(f"Record Python calc tidak valid: {reason}")

        prompt_key = rec["messages"][-2]["content"].strip()
        if prompt_key in seen:
            continue

        # Eksekusi nyata kode Python di sandbox `run_python_calc`!
        parsed_assistant = json.loads(rec["messages"][-1]["content"])
        code = parsed_assistant["tool_calls"][0]["arguments"]["code"]
        exec_res = run_python_calc(code)
        if exec_res.get("status") != "ok" or exec_res.get("result") != expected:
            raise AssertionError(f"Hasil eksekusi Python tidak cocok! Got {exec_res}, expected {expected}")

        seen.add(prompt_key)
        if len(train_recs) < train_count:
            train_recs.append(rec)
        else:
            eval_recs.append({"expected_result": expected, **rec})

    return train_recs, eval_recs


def main() -> None:
    parser = argparse.ArgumentParser(description="Build 480 sampel run_python_calc + merge unified_plan_c_6480.jsonl")
    parser.add_argument("--python-train", type=int, default=480)
    parser.add_argument("--python-eval", type=int, default=24)
    parser.add_argument("--seed", type=int, default=202605)
    args = parser.parse_args()

    # 1. Muat 6.000 sampel existing + 200 eval held-out untuk jaga zero overlap
    experts = ["expert_1_accounting", "expert_2_audit", "expert_3_tax_id", "expert_4_agentic"]
    existing_train: list[dict[str, Any]] = []
    blocked_prompts: set[str] = set()

    for exp in experts:
        p = DATASETS_DIR / f"{exp}.jsonl"
        rows = [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
        existing_train.extend(rows)
        for r in rows:
            blocked_prompts.add(r["messages"][-2]["content"].strip())

    eval_heldout_path = DATASETS_DIR / "eval_heldout_200.jsonl"
    eval_heldout_rows = [json.loads(line) for line in eval_heldout_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for r in eval_heldout_rows:
        blocked_prompts.add(r["messages"][-2]["content"].strip())

    # 2. Generate & eksekusi-verifikasi 480 sampel train + 24 eval `run_python_calc`
    py_train, py_eval = generate_verified_python_calc(
        train_count=args.python_train,
        eval_count=args.python_eval,
        existing_prompts=blocked_prompts,
        seed=args.seed,
    )

    py_train_path = DATASETS_DIR / "plan_c_python_calc_480.jsonl"
    py_train_path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in py_train) + "\n", encoding="utf-8")

    py_eval_path = DATASETS_DIR / "eval_python_calc_24.jsonl"
    py_eval_path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in py_eval) + "\n", encoding="utf-8")

    # 3. Gabung 6.000 existing + 480 baru -> unified_plan_c_6480.jsonl
    unified = existing_train + py_train
    random.Random(2026).shuffle(unified)
    unified_path = DATASETS_DIR / "unified_plan_c_6480.jsonl"
    unified_path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in unified) + "\n", encoding="utf-8")

    print(f"[OK] plan_c_python_calc_480.jsonl : {len(py_train)} records (100% sandbox-executed & verified)")
    print(f"[OK] eval_python_calc_24.jsonl    : {len(py_eval)} records (zero overlap)")
    print(f"[OK] unified_plan_c_6480.jsonl    : {len(unified)} total records")


if __name__ == "__main__":
    main()
