"""Korpus distilasi kaya variasi & edge cases (100% fiktif) untuk 4 Expert Audit, Akuntansi, Pajak ID & Agentic."""

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

SYSTEM_PROMPTS: dict[str, str] = {
    "expert_1_accounting": (
        "Anda adalah Akuntan Senior Indonesia (SAK, SAK-EP, PSAP/BUMD). "
        "Analisis substansi transaksi, petakan ke Chart of Accounts (CoA) yang tepat, "
        "dan hasilkan jurnal berimbang dalam format JSON terstruktur."
    ),
    "expert_2_audit": (
        "Anda adalah Auditor Keuangan Senior & Analis Kinerja (SPAP/ISA, BUMD & Korporasi). "
        "Hitung EBITDA, rasio keuangan, analisis varians RKAP, proyeksi proforma, rekonsiliasi bank, "
        "dan temuan Kertas Kerja Audit (KKA) dalam format JSON terstruktur."
    ),
    "expert_3_tax_id": (
        "Anda adalah Konsultan Pajak Bersertifikat Indonesia (UU HPP, PMK 131/2024, PP 58/2023, Coretax). "
        "Identifikasi objek pajak, dasar hukum, tarif efektif, perhitungan pajak, koreksi fiskal, "
        "dan ekualisasi PPN-PPh dalam format JSON terstruktur."
    ),
    "expert_4_agentic": (
        "Anda adalah Agentic Runtime Orchestrator untuk Audit & Akuntansi Lokal. "
        "Terjemahkan instruksi kerja menjadi urutan pemanggilan tool Python yang aman, non-destruktif, "
        "dan 100% mematuhi skema JSON tool_calls."
    ),
}

ENTITIES = [
    "Perumda Tirta Nusantara",
    "Perumda Air Minum Tirta Kencana",
    "PT Karya Mandiri Sejahtera",
    "PT Nusantara Logistik Tbk",
    "PT Bintang Agro Perkasa",
    "CV Cipta Rekayasa Teknik",
    "PT Sinar Energi Pratama",
    "PT Graha Medika Utama",
    "PT Samudera Niaga Jaya",
    "PT Panca Karya Konstruksi",
]

VENDORS = [
    "KAP Pratama & Rekan",
    "PT Kimia Tirta Abadi",
    "CV Mitra Pompa Industri",
    "PT Solusi Cloud Lokal",
    "PT Graha Properti Sentosa",
    "CV Jaya Elektrikal",
    "PT Prima Konsultan Pajak",
    "PT Indo Pipa Sejahtera",
    "CV Nusantara Teknik",
    "PT Karya Bangun Persada",
]

LOKASI_LOKET = [
    "Loket Kantor Pusat",
    "Loket Cabang Utara",
    "Loket Cabang Selatan",
    "Loket Koperasi Pegawai",
    "Unit IKK Timur",
    "Unit IKK Barat",
    "Loket Pembayaran PPOB Mitra",
    "Loket Mobil Keliling",
]

PERSONA_PREFIXES_ACC = [
    "Tolong buatkan jurnal akuntansi untuk transaksi berikut:",
    "Dari mutasi rekening koran & bukti kas ditemukan transaksi:",
    "Berdasarkan memo bagian keuangan, catat jurnal atas kejadian ini:",
    "Staf pembukuan melaporkan transaksi harian sebagai berikut:",
    "Sebagai persiapan penyusunan Neraca Lajur, susun jurnal untuk:",
    "Mohon klasifikasikan akun dan buat ayat jurnal berimbang atas:",
]


def _r(val: Decimal) -> int:
    return int(val.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _msg(expert: str, user_txt: str, assistant_obj: dict[str, Any]) -> dict[str, Any]:
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPTS[expert]},
            {"role": "user", "content": user_txt},
            {"role": "assistant", "content": json.dumps(assistant_obj, ensure_ascii=False)},
        ]
    }


def _rand_date(rng: random.Random) -> tuple[str, str]:
    yr = rng.choice([2025, 2026])
    mo = rng.randint(1, 12)
    dy = rng.randint(1, 28)
    return f"{yr}-{mo:02d}-{dy:02d}", f"{mo:02d}/{yr}"


# ==============================================================================
# EXPERT 1: ACCOUNTING & JOURNALING (Single, Compound, Tax-Inclusive, Adjustments)
# ==============================================================================
def sample_expert_1(idx: int, rng: random.Random) -> dict[str, Any]:
    """Menghasilkan 1 sampel Expert 1 dari 12 pola akuntansi dunia nyata (termasuk jurnal majemuk)."""
    tgl, bln = _rand_date(rng)
    ent = rng.choice(ENTITIES)
    vendor = rng.choice(VENDORS)
    loket = rng.choice(LOKASI_LOKET)
    prefix = rng.choice(PERSONA_PREFIXES_ACC)
    pattern = idx % 12

    if pattern == 0:
        # LPP Loket penerimaan tagihan air + denda keterlambatan (jurnal majemuk 3 baris)
        pokok = rng.randint(15, 650) * 100_000
        denda = rng.randint(2, 45) * 50_000
        total_kas = pokok + denda
        user_txt = (
            f"{prefix} Pada {tgl}, {ent} menerima setoran LPP {loket} total Rp {total_kas:,}, "
            f"terdiri dari pelunasan piutang rekening air Rp {pokok:,} dan pendapatan denda keterlambatan Rp {denda:,}."
        )
        obj = {
            "tanggal": tgl,
            "entitas": ent,
            "standar": "SAK-EP / Pedoman Akuntansi BUMD Air Minum",
            "uraian": f"Penerimaan LPP {loket} (Pokok Piutang Air & Denda)",
            "lines": [
                {"account_code": "1110", "account_name": "Kas di Loket", "debit": total_kas, "credit": 0},
                {"account_code": "1130", "account_name": "Piutang Usaha Air", "debit": 0, "credit": pokok},
                {"account_code": "4210", "account_name": "Pendapatan Denda Keterlambatan", "debit": 0, "credit": denda},
            ],
            "alasan": "Kas didebit sebesar total penerimaan; piutang usaha dikredit atas pokok tagihan dan denda diakui sebagai pendapatan non-air/lain-lain.",
            "balanced": True,
        }
    elif pattern == 1:
        # Penetapan Rekap DRD bulanan (Harga Air + Biaya Pemeliharaan Meter + Biaya Administrasi)
        air = rng.randint(80, 1200) * 100_000
        meter = rng.randint(10, 150) * 100_000
        adm = rng.randint(5, 80) * 100_000
        total = air + meter + adm
        user_txt = (
            f"{prefix} Rekap DRD periode {bln} {ent} menetapkan tagihan pelanggan total Rp {total:,} "
            f"dengan rincian: pemakaian air Rp {air:,}, pemeliharaan meter Rp {meter:,}, dan biaya administrasi Rp {adm:,}."
        )
        obj = {
            "tanggal": tgl,
            "entitas": ent,
            "standar": "SAK-EP (Basis Akrual)",
            "uraian": f"Penetapan Rekap DRD Periode {bln}",
            "lines": [
                {"account_code": "1130", "account_name": "Piutang Usaha Air", "debit": total, "credit": 0},
                {"account_code": "4110", "account_name": "Pendapatan Penjualan Air", "debit": 0, "credit": air},
                {"account_code": "4120", "account_name": "Pendapatan Pemeliharaan Meter", "debit": 0, "credit": meter},
                {"account_code": "4130", "account_name": "Pendapatan Administrasi Rekening", "debit": 0, "credit": adm},
            ],
            "alasan": "Pengakuan pendapatan akrual saat DRD diterbitkan mencatat piutang usaha dan merinci setiap komponen pendapatan operasional.",
            "balanced": True,
        }
    elif pattern == 2:
        # Pembayaran jasa audit/konsultan dengan PPN Masukan (PMK 131/2024 efektif 11%) & Potongan PPh 23 (2%)
        dpp = rng.randint(15, 250) * 1_000_000
        ppn = calculate_ppn(dpp, is_luxury_goods=False)["ppn_terutang"]
        pph23 = calculate_withholding_tax("PPH_23_JASA", dpp, has_npwp=True)["pajak_terutang"]
        kas_keluar = dpp + ppn - pph23
        user_txt = (
            f"{prefix} Tanggal {tgl}, {ent} membayar invoice jasa konsultan/audit dari {vendor} (PKP, ber-NPWP) "
            f"dengan nilai jasa Rp {dpp:,}, PPN non-mewah (PMK 131/2024) Rp {ppn:,}, dan dipotong PPh Pasal 23 2% Rp {pph23:,} via transfer bank."
        )
        obj = {
            "tanggal": tgl,
            "entitas": ent,
            "standar": "SAK / UU HPP & PMK 131/2024",
            "uraian": f"Pembayaran Jasa Profesional ke {vendor} (Include PPN & Potong PPh 23)",
            "lines": [
                {"account_code": "5310", "account_name": "Beban Jasa Profesional & Audit", "debit": dpp, "credit": 0},
                {"account_code": "1160", "account_name": "PPN Masukan", "debit": ppn, "credit": 0},
                {"account_code": "2132", "account_name": "Utang Pajak PPh Pasal 23", "debit": 0, "credit": pph23},
                {"account_code": "1120", "account_name": "Kas di Bank", "debit": 0, "credit": kas_keluar},
            ],
            "alasan": "Beban jasa diakui sebesar DPP, PPN Masukan dicatat sebagai aset lancar pajak, PPh 23 yang dipotong diakui sebagai utang pajak, dan sisanya dibayar via bank.",
            "balanced": True,
        }
    elif pattern == 3:
        # Pembelian persediaan bahan kimia (tawas/kaporit) secara kredit + PPN Masukan
        dpp = rng.randint(10, 180) * 1_000_000
        ppn = calculate_ppn(dpp, is_luxury_goods=False)["ppn_terutang"]
        utang = dpp + ppn
        user_txt = (
            f"{prefix} {ent} membeli persediaan bahan kimia pengolahan air (tawas & kaporit) secara kredit 30 hari dari {vendor} "
            f"pada {tgl}, nilai barang Rp {dpp:,} ditambah PPN Rp {ppn:,}."
        )
        obj = {
            "tanggal": tgl,
            "entitas": ent,
            "standar": "PSAK 202 / SAK-EP Persediaan",
            "uraian": f"Pembelian Kredit Persediaan Bahan Kimia dari {vendor}",
            "lines": [
                {"account_code": "1140", "account_name": "Persediaan Bahan Kimia", "debit": dpp, "credit": 0},
                {"account_code": "1160", "account_name": "PPN Masukan", "debit": ppn, "credit": 0},
                {"account_code": "2110", "account_name": "Utang Usaha", "debit": 0, "credit": utang},
            ],
            "alasan": "PPN yang dapat dikreditkan tidak menambah harga perolehan persediaan; utang usaha diakui sebesar total tagihan bruto.",
            "balanced": True,
        }
    elif pattern == 4:
        # Pembayaran sewa gedung/gudang 1 tahun dibayar dimuka + PPh Pasal 4(2) Final 10%
        sewa = rng.randint(24, 360) * 1_000_000
        pph42 = calculate_withholding_tax("PPH_4_2_SEWA_TANAH_BANGUNAN", sewa)["pajak_terutang"]
        kas_bayar = sewa - pph42
        user_txt = (
            f"{prefix} Pada {tgl}, {ent} membayar sewa gedung operasional selama 12 bulan ke depan kepada {vendor} "
            f"sebesar Rp {sewa:,} (non-PKP) dengan pemotongan PPh Pasal 4(2) Final 10%."
        )
        obj = {
            "tanggal": tgl,
            "entitas": ent,
            "standar": "SAK-EP / PPh Pasal 4(2)",
            "uraian": f"Pembayaran Sewa Gedung Dibayar Dimuka 12 Bulan ({vendor})",
            "lines": [
                {"account_code": "1150", "account_name": "Sewa Dibayar Dimuka", "debit": sewa, "credit": 0},
                {"account_code": "2134", "account_name": "Utang Pajak PPh Pasal 4(2)", "debit": 0, "credit": pph42},
                {"account_code": "1120", "account_name": "Kas di Bank", "debit": 0, "credit": kas_bayar},
            ],
            "alasan": "Karena manfaat sewa mencakup 12 bulan ke depan, dicatat sebagai aset Sewa Dibayar Dimuka dan diamortisasi bulanan; PPh 4(2) 10% dipotong saat pembayaran.",
            "balanced": True,
        }
    elif pattern == 5:
        # Jurnal Penyesuaian Penyusutan Aset Tetap (Instalasi & Kendaraan)
        dep_inst = rng.randint(25, 350) * 1_000_000
        dep_kend = rng.randint(5, 85) * 1_000_000
        total_dep = dep_inst + dep_kend
        user_txt = (
            f"{prefix} Buat jurnal penyesuaian penyusutan aset tetap {ent} periode {bln}: "
            f"penyusutan instalasi pengolahan & pipa Rp {dep_inst:,} dan kendaraan operasional Rp {dep_kend:,}."
        )
        obj = {
            "tanggal": tgl,
            "entitas": ent,
            "standar": "PSAK 216 Aset Tetap",
            "uraian": f"Penyesuaian Penyusutan Aset Tetap Periode {bln}",
            "lines": [
                {"account_code": "5210", "account_name": "Beban Penyusutan Instalasi & Pipa", "debit": dep_inst, "credit": 0},
                {"account_code": "5215", "account_name": "Beban Penyusutan Kendaraan", "debit": dep_kend, "credit": 0},
                {"account_code": "1291", "account_name": "Akumulasi Penyusutan Instalasi & Pipa", "debit": 0, "credit": dep_inst},
                {"account_code": "1292", "account_name": "Akumulasi Penyusutan Kendaraan", "debit": 0, "credit": dep_kend},
            ],
            "alasan": f"Total beban penyusutan Rp {total_dep:,} dialokasikan secara sistematis ke masing-masing kelompok aset tetap.",
            "balanced": True,
        }
    elif pattern == 6:
        # Pembayaran Gaji + Potongan PPh 21 TER & BPJS Ketenagakerjaan/Kesehatan
        gaji_bruto = rng.randint(80, 900) * 1_000_000
        pph21 = _r(Decimal(gaji_bruto) * Decimal(str(rng.choice([0.025, 0.035, 0.05]))))
        bpjs_peg = _r(Decimal(gaji_bruto) * Decimal("0.03"))
        gaji_neto = gaji_bruto - pph21 - bpjs_peg
        user_txt = (
            f"{prefix} Penggajian pegawai {ent} bulan {bln}: total gaji bruto Rp {gaji_bruto:,}, "
            f"potongan PPh 21 TER Rp {pph21:,}, potongan iuran BPJS bagian pegawai Rp {bpjs_peg:,}, "
            f"sisanya ditransfer ke rekening pegawai."
        )
        obj = {
            "tanggal": tgl,
            "entitas": ent,
            "standar": "PSAK 219 Imbalan Kerja / PP 58/2023",
            "uraian": f"Pembayaran Gaji Pegawai Periode {bln}",
            "lines": [
                {"account_code": "5110", "account_name": "Beban Gaji & Tunjangan", "debit": gaji_bruto, "credit": 0},
                {"account_code": "2131", "account_name": "Utang Pajak PPh Pasal 21", "debit": 0, "credit": pph21},
                {"account_code": "2140", "account_name": "Utang Iuran BPJS", "debit": 0, "credit": bpjs_peg},
                {"account_code": "1120", "account_name": "Kas di Bank", "debit": 0, "credit": gaji_neto},
            ],
            "alasan": "Beban gaji diakui sebesar nilai bruto; potongan PPh 21 dan BPJS pegawai diakui sebagai liabilitas jangka pendek sampai disetor.",
            "balanced": True,
        }
    elif pattern == 7:
        # Jurnal Penyesuaian Penyisihan Piutang Tak Tertagih (CKPN / Allowance Method)
        ckpn = rng.randint(10, 220) * 1_000_000
        user_txt = (
            f"{prefix} Berdasarkan analisis umur piutang (aging schedule) akhir periode {bln}, "
            f"{ent} perlu menambah cadangan kerugian penurunan nilai piutang usaha sebesar Rp {ckpn:,}."
        )
        obj = {
            "tanggal": tgl,
            "entitas": ent,
            "standar": "PSAK 109 / SAK-EP Penurunan Nilai Piutang",
            "uraian": f"Penambahan Penyisihan Piutang Tak Tertagih Periode {bln}",
            "lines": [
                {"account_code": "5220", "account_name": "Beban Kerugian Penurunan Nilai Piutang", "debit": ckpn, "credit": 0},
                {"account_code": "1139", "account_name": "Cadangan Kerugian Penurunan Nilai Piutang", "debit": 0, "credit": ckpn},
            ],
            "alasan": "Metode cadangan (allowance) mengakui beban kerugian piutang dan akun kontra-aset tanpa menghapus piutang individual secara langsung.",
            "balanced": True,
        }
    elif pattern == 8:
        # Jurnal Koreksi Audit (Kesalahan Pencatatan Belanja Modal dicatat sebagai Beban Pemeliharaan)
        nilai = rng.randint(30, 450) * 1_000_000
        user_txt = (
            f"{prefix} Temuan audit pada {ent} ({tgl}): pembelian pompa distribusi berumur manfaat 8 tahun senilai Rp {nilai:,} "
            f"terlanjur dicatat sebagai Beban Pemeliharaan (5140). Buat jurnal koreksi reklasifikasinya."
        )
        obj = {
            "tanggal": tgl,
            "entitas": ent,
            "standar": "PSAK 216 (Kapitalisasi Aset Tetap)",
            "uraian": "Jurnal Koreksi Reklasifikasi Pembelian Pompa dari Beban ke Aset Tetap",
            "lines": [
                {"account_code": "1220", "account_name": "Aset Tetap - Mesin & Pompa Instalasi", "debit": nilai, "credit": 0},
                {"account_code": "5140", "account_name": "Beban Pemeliharaan Instalasi", "debit": 0, "credit": nilai},
            ],
            "alasan": "Pengeluaran dengan umur manfaat > 1 tahun dan material memenuhi kriteria kapitalisasi aset tetap (CapEx), bukan beban periode berjalan (OpEx).",
            "balanced": True,
        }
    elif pattern == 9:
        # Penerimaan Pendapatan Sambungan Baru (Uang Muka / Pendapatan Diterima Dimuka)
        uang_muka = rng.randint(5, 120) * 1_000_000
        user_txt = (
            f"{prefix} Tanggal {tgl}, {ent} menerima pembayaran pendaftaran sambungan baru pelanggan sebesar Rp {uang_muka:,} "
            f"melalui {loket}, namun pemasangan pipa baru akan dikerjakan bulan depan."
        )
        obj = {
            "tanggal": tgl,
            "entitas": ent,
            "standar": "PSAK 115 / SAK-EP Pengakuan Pendapatan",
            "uraian": "Penerimaan Uang Muka Pemasangan Sambungan Baru Pelanggan",
            "lines": [
                {"account_code": "1110", "account_name": "Kas di Loket", "debit": uang_muka, "credit": 0},
                {"account_code": "2150", "account_name": "Pendapatan Diterima Dimuka - Sambungan Baru", "debit": 0, "credit": uang_muka},
            ],
            "alasan": "Karena kewajiban pelaksanaan (pemasangan sambungan) belum selesai, penerimaan kas diakui sebagai liabilitas kontrak / pendapatan diterima dimuka.",
            "balanced": True,
        }
    elif pattern == 10:
        # Setoran Kas Loket ke Rekening Bank (Cash in Transit / Transfer Internal)
        setoran = rng.randint(20, 500) * 1_000_000
        user_txt = (
            f"{prefix} Pada {tgl}, kasir {ent} menyetorkan uang tunai hasil penerimaan {loket} "
            f"sebesar Rp {setoran:,} ke rekening giro Bank Daerah."
        )
        obj = {
            "tanggal": tgl,
            "entitas": ent,
            "standar": "SAK-EP (Pengendalian Kas)",
            "uraian": f"Setoran Tunai dari {loket} ke Rekening Bank",
            "lines": [
                {"account_code": "1120", "account_name": "Kas di Bank", "debit": setoran, "credit": 0},
                {"account_code": "1110", "account_name": "Kas di Loket", "debit": 0, "credit": setoran},
            ],
            "alasan": "Mutasi internal antar akun kas memindahkan saldo dari Kas di Loket ke Kas di Bank tanpa memengaruhi total kas.",
            "balanced": True,
        }
    else:
        # Akrual Beban Listrik Akhir Bulan yang Tagihannya Baru Jatuh Tempo Bulan Depan
        listrik = rng.randint(15, 280) * 1_000_000
        user_txt = (
            f"{prefix} Akhir periode {bln}, tagihan listrik PLN untuk rumah pompa {ent} sebesar Rp {listrik:,} "
            f"sudah terpakai namun baru akan dibayar tanggal 5 bulan berikutnya. Buat jurnal penyesuaian akrual."
        )
        obj = {
            "tanggal": tgl,
            "entitas": ent,
            "standar": "SAK-EP (Prinsip Matching / Akrual)",
            "uraian": f"Akrual Beban Listrik Pompa Periode {bln}",
            "lines": [
                {"account_code": "5130", "account_name": "Beban Listrik & Energi", "debit": listrik, "credit": 0},
                {"account_code": "2120", "account_name": "Beban yang Masih Harus Dibayar", "debit": 0, "credit": listrik},
            ],
            "alasan": "Beban yang telah terjadi pada periode pelaporan wajib diakui meski kas belum keluar (accrued expense).",
            "balanced": True,
        }

    return _msg("expert_1_accounting", user_txt, obj)


# ==============================================================================
# EXPERT 2: AUDIT, FINANCIAL RATIOS, EBITDA, RKAP, PROFORMA, BANK RECON & KKA
# ==============================================================================
def sample_expert_2(idx: int, rng: random.Random) -> dict[str, Any]:
    """Menghasilkan 1 sampel Expert 2 dari 8 pola audit & analisis keuangan mendalam."""
    ent = rng.choice(ENTITIES)
    pattern = idx % 9

    if pattern == 0:
        # EBITDA & EBITDA Margin
        rev = rng.randint(2500, 35000) * 1_000_000
        ebit = _r(Decimal(rev) * Decimal(str(rng.uniform(0.08, 0.28))))
        depr = _r(Decimal(rev) * Decimal(str(rng.uniform(0.05, 0.14))))
        amort = rng.randint(10, 250) * 1_000_000
        ebitda = ebit + depr + amort
        margin = round((ebitda / rev) * 100, 2)
        user_txt = (
            f"Data Laba Rugi {ent}: Pendapatan Usaha Rp {rev:,}, Laba Usaha (EBIT) Rp {ebit:,}, "
            f"Beban Penyusutan Rp {depr:,}, dan Beban Amortisasi Rp {amort:,}. "
            f"Hitung EBITDA, EBITDA Margin, dan prosedur audit substantif yang disarankan."
        )
        obj = {
            "metrik": "EBITDA & EBITDA Margin",
            "entitas": ent,
            "pendapatan_usaha": rev,
            "ebit": ebit,
            "ebitda": ebitda,
            "ebitda_margin_persen": margin,
            "formula": "EBITDA = EBIT + Penyusutan + Amortisasi; Margin = (EBITDA / Pendapatan) x 100%",
            "prosedur_audit": [
                "Rekonsiliasi beban penyusutan di Laba Rugi dengan daftar penyusutan aset tetap (KKA Aset Tetap).",
                "Uji pisah batas (cut-off) pengakuan pendapatan usaha akhir tahun.",
            ],
        }
    elif pattern == 1:
        # Analisis Varians RKAP (Pendapatan & Beban)
        rkap_rev = rng.randint(5000, 25000) * 1_000_000
        real_rev = _r(Decimal(rkap_rev) * Decimal(str(rng.uniform(0.78, 1.18))))
        rkap_exp = _r(Decimal(rkap_rev) * Decimal(str(rng.uniform(0.70, 0.88))))
        real_exp = _r(Decimal(rkap_exp) * Decimal(str(rng.uniform(0.82, 1.15))))
        var_rev = real_rev - rkap_rev
        var_exp = real_exp - rkap_exp
        pct_rev = round((var_rev / rkap_rev) * 100, 2)
        pct_exp = round((var_exp / rkap_exp) * 100, 2)
        user_txt = (
            f"Evaluasi realisasi terhadap RKAP {ent}: Anggaran Pendapatan Rp {rkap_rev:,} (Realisasi Rp {real_rev:,}); "
            f"Anggaran Beban Operasi Rp {rkap_exp:,} (Realisasi Rp {real_exp:,}). Susun analisis varians RKAP."
        )
        obj = {
            "metrik": "Analisis Varians RKAP",
            "entitas": ent,
            "varians_pendapatan": var_rev,
            "varians_pendapatan_persen": pct_rev,
            "status_pendapatan": "Favorable" if var_rev >= 0 else "Unfavorable",
            "varians_beban": var_exp,
            "varians_beban_persen": pct_exp,
            "status_beban": "Favorable (Efisien)" if var_exp <= 0 else "Unfavorable (Over-budget)",
            "catatan_audit": "Telusuri komponen beban yang melebihi anggaran > 5% dan uji otorisasi revisi RKAP.",
        }
    elif pattern == 2:
        # Proyeksi Keuangan Proforma 1 Tahun (Pertumbuhan Pendapatan & Beban)
        rev_y0 = rng.randint(4000, 30000) * 1_000_000
        exp_y0 = _r(Decimal(rev_y0) * Decimal(str(rng.uniform(0.72, 0.88))))
        g_rev = rng.choice([5, 8, 10, 12, 15])
        g_exp = rng.choice([3, 5, 6, 8, 10])
        rev_y1 = _r(Decimal(rev_y0) * (Decimal("1") + Decimal(g_rev) / Decimal("100")))
        exp_y1 = _r(Decimal(exp_y0) * (Decimal("1") + Decimal(g_exp) / Decimal("100")))
        ebit_y1 = rev_y1 - exp_y1
        user_txt = (
            f"Susun proyeksi Laba Rugi Proforma tahun depan untuk {ent} berdasarkan realisasi tahun ini: "
            f"Pendapatan Rp {rev_y0:,} (asumsi tumbuh {g_rev}%) dan Beban Usaha Rp {exp_y0:,} (asumsi naik {g_exp}%)."
        )
        obj = {
            "metrik": "Proyeksi Keuangan Proforma (1 Tahun)",
            "entitas": ent,
            "asumsi_tumbuh_pendapatan_persen": g_rev,
            "asumsi_naik_beban_persen": g_exp,
            "proyeksi_pendapatan": rev_y1,
            "proyeksi_beban_usaha": exp_y1,
            "proyeksi_laba_usaha": ebit_y1,
            "catatan_risiko": "Lakukan analisis sensitivitas jika realisasi penagihan piutang atau tarif meleset dari asumsi.",
        }
    elif pattern == 3:
        # Rekonsiliasi Bank (Saldo Buku vs Saldo Rekening Koran)
        saldo_bank = rng.randint(500, 8000) * 1_000_000
        dit = rng.randint(15, 250) * 1_000_000
        osc = rng.randint(10, 200) * 1_000_000
        saldo_benar = saldo_bank + dit - osc
        jasa_giro = rng.randint(1, 15) * 1_000_000
        biaya_adm = rng.randint(5, 50) * 100_000
        saldo_buku_awal = saldo_benar - jasa_giro + biaya_adm
        user_txt = (
            f"Rekonsiliasi bank {ent}: Saldo Rekening Koran Rp {saldo_bank:,}, Setoran dalam Perjalanan (DIT) Rp {dit:,}, "
            f"Cek Beredar (Outstanding Check) Rp {osc:,}. Saldo Buku Awal Rp {saldo_buku_awal:,}, "
            f"Jasa Giro belum dicatat Rp {jasa_giro:,}, Biaya Administrasi Bank Rp {biaya_adm:,}. "
            f"Hitung saldo kas yang benar dan cek apakah rekonsiliasi seimbang."
        )
        obj = {
            "metrik": "Rekonsiliasi Bank",
            "entitas": ent,
            "saldo_bank_disesuaikan": saldo_benar,
            "saldo_buku_disesuaikan": saldo_buku_awal + jasa_giro - biaya_adm,
            "selisih": 0,
            "seimbang": True,
            "jurnal_penyesuaian_diperlukan": [
                f"Debit Kas di Bank / Kredit Pendapatan Jasa Giro Rp {jasa_giro:,}",
                f"Debit Beban Administrasi Bank / Kredit Kas di Bank Rp {biaya_adm:,}",
            ],
        }
    elif pattern == 4:
        # Rasio Likuiditas (Current Ratio) & Solvabilitas (DER)
        aset_lancar = rng.randint(800, 9000) * 1_000_000
        utang_lancar = rng.randint(400, 6000) * 1_000_000
        total_utang = utang_lancar + rng.randint(200, 5000) * 1_000_000
        ekuitas = rng.randint(1500, 15000) * 1_000_000
        cr = round(aset_lancar / utang_lancar, 2)
        der = round(total_utang / ekuitas, 2)
        user_txt = (
            f"Posisi Neraca {ent}: Aset Lancar Rp {aset_lancar:,}, Liabilitas Jangka Pendek Rp {utang_lancar:,}, "
            f"Total Liabilitas Rp {total_utang:,}, dan Total Ekuitas Rp {ekuitas:,}. Hitung Current Ratio dan DER."
        )
        obj = {
            "metrik": "Rasio Likuiditas & Solvabilitas",
            "entitas": ent,
            "current_ratio": cr,
            "debt_to_equity_ratio": der,
            "penilaian_likuiditas": "Sehat" if cr >= 1.5 else ("Waspada" if cr >= 1.0 else "Kritis"),
            "penilaian_solvabilitas": "Konservatif" if der <= 1.0 else ("Moderat" if der <= 2.0 else "Leverage Tinggi"),
        }
    elif pattern == 5:
        # Rasio Efisiensi Penagihan Piutang BUMD Air Minum (Indikator Kinerja BPPSPAM/PUPR)
        drd_tagihan = rng.randint(1500, 12000) * 1_000_000
        penerimaan = _r(Decimal(drd_tagihan) * Decimal(str(rng.uniform(0.70, 0.98))))
        efisiensi = round((penerimaan / drd_tagihan) * 100, 2)
        user_txt = (
            f"Evaluasi kinerja penagihan {ent}: Total rekening air ditagihkan (DRD) Rp {drd_tagihan:,} "
            f"dan total penerimaan penagihan Rp {penerimaan:,}. Hitung Rasio Efisiensi Penagihan dan rekomendasi audit."
        )
        obj = {
            "metrik": "Efisiensi Penagihan Piutang",
            "entitas": ent,
            "total_tagihan_drd": drd_tagihan,
            "total_penerimaan": penerimaan,
            "efisiensi_penagihan_persen": efisiensi,
            "kategori_kinerja": "Baik (>=90%)" if efisiensi >= 90 else ("Cukup (80-89%)" if efisiensi >= 80 else "Perlu Perbaikan (<80%)"),
            "rekomendasi_audit": "Tinjau daftar tunggakan pelanggan > 3 bulan dan evaluasi efektivitas pemutusan sementara.",
        }
    elif pattern == 6:
        # Penetapan Materialitas Audit (Overall Materiality & Performance Materiality)
        rev = rng.randint(10000, 150000) * 1_000_000
        pct_om = rng.choice([0.5, 1.0, 1.5])
        om = _r(Decimal(rev) * Decimal(str(pct_om)) / Decimal("100"))
        pm = _r(Decimal(om) * Decimal("0.75"))
        trivial = _r(Decimal(om) * Decimal("0.05"))
        user_txt = (
            f"Perencanaan audit {ent}: Pendapatan Usaha Rp {rev:,}. Dengan acuan Overall Materiality {pct_om}% "
            f"dari pendapatan, Performance Materiality 75%, dan Clearly Trivial 5%, hitung angka materialitas KKA."
        )
        obj = {
            "metrik": "Penetapan Materialitas Audit (SA 320)",
            "entitas": ent,
            "benchmark_pendapatan": rev,
            "overall_materiality": om,
            "performance_materiality": pm,
            "clearly_trivial_threshold": trivial,
            "catatan_kka": "Setiap salah saji agregat di atas Performance Materiality wajib diusulkan jurnal koreksi audit (PAJE).",
        }
    else:
        # DSCR (Debt Service Coverage Ratio) untuk menilai kemampuan bayar cicilan utang
        ebitda = rng.randint(1000, 10000) * 1_000_000
        cicilan_pokok = rng.randint(300, 4000) * 1_000_000
        beban_bunga = rng.randint(100, 1500) * 1_000_000
        debt_service = cicilan_pokok + beban_bunga
        dscr = round(ebitda / debt_service, 2)
        user_txt = (
            f"Analisis kredit/audit {ent}: EBITDA Rp {ebitda:,}, angsuran pokok pinjaman jatuh tempo Rp {cicilan_pokok:,}, "
            f"dan beban bunga Rp {beban_bunga:,}. Hitung DSCR dan interpretasinya."
        )
        obj = {
            "metrik": "Debt Service Coverage Ratio (DSCR)",
            "entitas": ent,
            "ebitda": ebitda,
            "total_debt_service": debt_service,
            "dscr": dscr,
            "status_covenant": "Aman (>= 1.25x)" if dscr >= 1.25 else ("Ketat (1.0 - 1.24x)" if dscr >= 1.0 else "Risiko Gagal Bayar (< 1.0x)"),
        }

    return _msg("expert_2_audit", user_txt, obj)


# ==============================================================================
# EXPERT 3: PERPAJAKAN INDONESIA LENGKAP (UU HPP, PMK 131/2024, PP 58/2023)
# ==============================================================================
def sample_expert_3(idx: int, rng: random.Random) -> dict[str, Any]:
    """Menghasilkan 1 sampel Expert 3 dari 8 skenario perpajakan Indonesia (100% dihitung deterministik)."""
    ent = rng.choice(ENTITIES)
    vendor = rng.choice(VENDORS)
    pattern = idx % 9

    if pattern == 0:
        # PPN Non-Mewah PMK 131/2024 (12% x DPP Nilai Lain 11/12)
        dpp = rng.randint(12, 850) * 1_000_000
        res = calculate_ppn(dpp, is_luxury_goods=False)
        res["dasar_hukum"] = "UU HPP & PMK 131/2024 (PPN 12% x DPP Nilai Lain 11/12)"
        user_txt = (
            f"{ent} menerbitkan invoice penyerahan jasa/barang kena pajak non-mewah kepada {vendor} "
            f"dengan harga jual/penggantian Rp {dpp:,}. Hitung DPP Nilai Lain dan PPN Keluaran sesuai PMK 131/2024."
        )
        return _msg("expert_3_tax_id", user_txt, res)

    if pattern == 1:
        # PPN Barang Mewah 12% DPP Penuh
        dpp = rng.randint(150, 1500) * 1_000_000
        res = calculate_ppn(dpp, is_luxury_goods=True)
        res["dasar_hukum"] = "UU HPP & PMK 131/2024 (Barang Tergolong Mewah Tarif 12% DPP Penuh)"
        user_txt = (
            f"{ent} membeli kendaraan/barang kena pajak tergolong mewah dari {vendor} dengan harga jual Rp {dpp:,}. "
            f"Hitung PPN terutangnya."
        )
        return _msg("expert_3_tax_id", user_txt, res)

    if pattern == 2:
        # PPh Pasal 23 Jasa / Dividen (ber-NPWP vs tanpa NPWP)
        dpp = rng.randint(10, 400) * 1_000_000
        has_npwp = (idx % 3 != 0)
        is_jasa = (idx % 2 == 0)
        tax_key = "PPH_23_JASA" if is_jasa else "PPH_23_DIVIDEN_ROYALTI"
        res = calculate_withholding_tax(tax_key, dpp, has_npwp=has_npwp)
        res["dasar_hukum"] = "Pasal 23 UU PPh (tarif 100% lebih tinggi jika penerima tanpa NPWP)"
        objek_txt = "jasa konsultasi/pemeliharaan teknis" if is_jasa else "royalti lisensi perangkat lunak"
        npwp_txt = "memiliki NPWP" if has_npwp else "tidak memiliki NPWP"
        user_txt = (
            f"{ent} membayar {objek_txt} kepada {vendor} ({npwp_txt}) sebesar Rp {dpp:,} belum termasuk PPN. "
            f"Hitung PPh Pasal 23 yang wajib dipotong."
        )
        return _msg("expert_3_tax_id", user_txt, res)

    if pattern == 3:
        # PPh Pasal 4(2) Final (Sewa Tanah/Bangunan 10% atau UMKM 0.5%)
        dpp = rng.randint(20, 600) * 1_000_000
        is_sewa = (idx % 2 == 0)
        tax_key = "PPH_4_2_SEWA_TANAH_BANGUNAN" if is_sewa else "PPH_4_2_UMKM"
        res = calculate_withholding_tax(tax_key, dpp)
        res["dasar_hukum"] = "PP 34/2017 (Sewa Tanah/Bangunan 10% Final)" if is_sewa else "PP 55/2022 (PPh Final UMKM 0,5%)"
        user_txt = (
            f"{ent} menyewa gedung arsip dari {vendor} sebesar Rp {dpp:,}. Hitung PPh Final Pasal 4(2)."
            if is_sewa
            else f"{vendor} (WP UMKM bersurat keterangan PP 55/2022) menerima pembayaran omzet Rp {dpp:,}. Hitung PPh Final 0,5%."
        )
        return _msg("expert_3_tax_id", user_txt, res)

    if pattern == 4:
        # PPh Pasal 22 Pengadaan Barang oleh BUMN/BUMD/Instansi Pemungut (1.5%)
        dpp = rng.randint(50, 900) * 1_000_000
        res = calculate_withholding_tax("PPH_22_PENGADAAN", dpp, has_npwp=True)
        res["dasar_hukum"] = "PMK PPh Pasal 22 (1,5% atas pembelian barang dari DPP tidak termasuk PPN)"
        user_txt = (
            f"Bendahara/pemungut {ent} melakukan pengadaan pipa HDPE dari {vendor} senilai DPP Rp {dpp:,} "
            f"(di luar PPN). Hitung pemungutan PPh Pasal 22."
        )
        return _msg("expert_3_tax_id", user_txt, res)

    if pattern == 5:
        # PPh Pasal 21 TER Bulanan (PP 58/2023 & PMK 168/2023)
        bruto = rng.randint(6, 45) * 1_000_000
        cat = rng.choice(["A", "B", "C"])
        rate = rng.choice([0.25, 0.75, 1.5, 2.5, 4.0, 6.0, 9.0, 12.0])
        res = calculate_pph21_ter(bruto, ter_rate_percent=rate, category=cat)
        res["dasar_hukum"] = "PP 58/2023 & PMK 168/2023 (Tarif Efektif Rata-Rata Bulanan Masa Jan-Nov)"
        user_txt = (
            f"Pegawai tetap {ent} masuk kategori TER {cat} dengan penghasilan bruto masa Mei Rp {bruto:,} "
            f"dan tarif efektif tabel TER sebesar {rate}%. Hitung potongan PPh Pasal 21 bulanan."
        )
        return _msg("expert_3_tax_id", user_txt, res)

    if pattern == 6:
        # Rekonsiliasi Fiskal Positif & Negatif -> PKP & PPh Badan 22%
        komersial = rng.randint(800, 9000) * 1_000_000
        pos_sanksi = rng.randint(10, 120) * 1_000_000
        pos_ent = rng.randint(15, 150) * 1_000_000
        neg_bunga = rng.randint(10, 180) * 1_000_000
        res = calculate_fiscal_reconciliation(
            komersial,
            positive_corrections=[
                {"item": "Sanksi Administrasi Pajak", "amount": pos_sanksi},
                {"item": "Biaya Entertainment tanpa Daftar Nominatif", "amount": pos_ent},
            ],
            negative_corrections=[
                {"item": "Penghasilan Bunga Deposito (PPh Final)", "amount": neg_bunga},
            ],
            corporate_tax_rate_percent=22.0,
        )
        res["dasar_hukum"] = "Pasal 6, Pasal 9, dan Pasal 17 UU PPh / UU HPP (Tarif PPh Badan 22%)"
        user_txt = (
            f"Rekonsiliasi fiskal {ent}: Laba komersial Rp {komersial:,}. Terdapat sanksi pajak Rp {pos_sanksi:,}, "
            f"biaya entertainment tanpa daftar nominatif Rp {pos_ent:,}, serta pendapatan bunga deposito final Rp {neg_bunga:,}. "
            f"Hitung koreksi fiskal, PKP, dan PPh Badan 22%."
        )
        return _msg("expert_3_tax_id", user_txt, res)

    # pattern == 7: Ekualisasi Omzet SPT PPN vs Peredaran Bruto SPT Tahunan PPh Badan
    omzet_pph = rng.randint(5000, 40000) * 1_000_000
    beda_waktu = rng.randint(50, 500) * 1_000_000
    non_bkp = rng.randint(20, 400) * 1_000_000
    dpp_spt_ppn = omzet_pph - non_bkp + beda_waktu
    selisih_bruto = omzet_pph - dpp_spt_ppn
    selisih_neto = selisih_bruto - non_bkp + beda_waktu
    user_txt = (
        f"Lakukan ekualisasi omzet {ent}: Peredaran Bruto di SPT PPh Badan Rp {omzet_pph:,}, "
        f"total DPP Penyerahan di SPT Masa PPN Jan-Des Rp {dpp_spt_ppn:,}. "
        f"Diketahui terdapat pendapatan non-objek PPN Rp {non_bkp:,} dan uang muka tahun depan yang sudah diterbitkan Faktur Pajak Rp {beda_waktu:,}."
    )
    obj = {
        "jenis_analisis": "Ekualisasi Omzet PPh Badan vs DPP SPT PPN",
        "entitas": ent,
        "omzet_pph_badan": omzet_pph,
        "dpp_spt_ppn": dpp_spt_ppn,
        "selisih_awal": selisih_bruto,
        "rekonsiliasi_non_objek_ppn": non_bkp,
        "rekonsiliasi_beda_waktu_uang_muka": beda_waktu,
        "selisih_tidak_terjelaskan": selisih_neto,
        "status": "Terekualisasi (Nol Selisih)" if selisih_neto == 0 else "Perlu Klarifikasi SP2DK",
    }
    return _msg("expert_3_tax_id", user_txt, obj)


# ==============================================================================
# EXPERT 4: AGENTIC TOOL-CALLER (RWED, Excel Template, OCR, SQLite3 RO, Dashboard)
# ==============================================================================
def sample_expert_4(idx: int, rng: random.Random) -> dict[str, Any]:
    """Menghasilkan 1 sampel Expert 4 unik dari 8 skenario orkestrasi agentic multi-step & safety guard."""
    ent_slug = rng.choice(["TirtaNusantara", "TirtaKencana", "KaryaMandiri", "NusantaraLogistik", "BintangAgro", "SinarEnergi", "GrahaMedika", "SamuderaNiaga"])
    yr = rng.choice(["2025", "2026"])
    mo = f"{rng.randint(1, 12):02d}"
    dy = f"{rng.randint(1, 28):02d}"
    unit = rng.choice(["kantor_pusat", "cabang_utara", "cabang_selatan", "koperasi", "unit_ikk", "gudang_utama"])
    batch_id = rng.randint(100, 9999)
    folder = f"Klien_{ent_slug}_{yr}_{mo}"
    pattern = idx % 9

    if pattern == 0:
        # Discovery + Inspeksi Template Excel (.xls input & .xlsx template klien)
        max_r = rng.choice([20, 25, 30, 40])
        xls_name = f"LPP_{unit}_{yr}{mo}{dy}.xls"
        tpl_name = rng.choice(["Neraca_Lajur", "Buku_Besar", "Journal", "Laporan_Keuangan"]) + f"_{yr}.xlsx"
        user_txt = (
            f"[Batch #{batch_id}] Mulai audit folder {folder}: daftarkan semua file keuangan, lalu inspeksi "
            f"input {xls_name} dan template {tpl_name} (maks {max_r} baris)."
        )
        calls = [
            {"name": "list_client_files", "arguments": {"directory": folder, "recursive": True}},
            {"name": "inspect_excel_template", "arguments": {"file_path": f"{folder}/{xls_name}", "max_rows": max_r}},
            {"name": "inspect_excel_template", "arguments": {"file_path": f"{folder}/template/{tpl_name}", "max_rows": max_r}},
        ]
    elif pattern == 1:
        # Tulis ke output baru menjaga template & formula klien + Balance Gate
        nominal = rng.randint(10, 950) * 1_000_000
        start_r = rng.randint(4, 20)
        sheet = rng.choice(["Journal", "Jurnal_Umum", "Jurnal_Penyesuaian"])
        user_txt = (
            f"[Batch #{batch_id}] Tulis jurnal LPP {unit} tgl {yr}-{mo}-{dy} senilai Rp {nominal:,} ke sheet {sheet} baris {start_r} "
            f"dari template {folder}/template/Journal_{yr}.xlsx ke {folder}/Laporan_Baru_{yr}/Journal_{yr}.xlsx "
            f"tanpa menimpa file asli, lalu jalankan balance gate pada {folder}/ledger.db."
        )
        calls = [
            {
                "name": "write_excel_preserving_template",
                "arguments": {
                    "template_path": f"{folder}/template/Journal_{yr}.xlsx",
                    "output_path": f"{folder}/Laporan_Baru_{yr}/Journal_{yr}.xlsx",
                    "sheet_name": sheet,
                    "start_row": start_r,
                    "start_col": 1,
                    "rows": [
                        [f"{yr}-{mo}-{dy}", "1110", "Kas di Loket", nominal, 0],
                        [f"{yr}-{mo}-{dy}", "1130", "Piutang Usaha Air", 0, nominal],
                    ],
                },
            },
            {"name": "verify_accounting_balance", "arguments": {"db_path": f"{folder}/ledger.db"}},
        ]
    elif pattern == 2:
        # Baca dokumen campuran: Kontrak DOCX + Scan PDF Faktur Pajak via OCR lokal
        doc_name = f"kontrak_{unit}_{batch_id}.docx"
        scan_name = rng.choice([f"scan_faktur_{batch_id}.pdf", f"scan_bukti_potong_{batch_id}.pdf", f"struk_bank_{batch_id}.png"])
        user_txt = (
            f"[Batch #{batch_id}] Baca perjanjian {folder}/{doc_name} dan ekstrak teks scan dokumen "
            f"{folder}/{scan_name} menggunakan OCR lokal untuk uji substantif."
        )
        calls = [
            {"name": "read_document_or_ocr", "arguments": {"file_path": f"{folder}/{doc_name}", "use_ocr": False}},
            {"name": "read_document_or_ocr", "arguments": {"file_path": f"{folder}/{scan_name}", "use_ocr": True}},
        ]
    elif pattern == 3:
        # Query Analitik SQLite3 Read-Only (Ringkasan Saldo per Kategori + Cek Anomali Jurnal Besar)
        batas = rng.randint(25, 500) * 1_000_000
        limit_n = rng.choice([10, 20, 25, 50])
        user_txt = (
            f"[Batch #{batch_id}] Query read-only database {folder}/ledger.db: ambil ringkasan saldo per kategori akun "
            f"dan tampilkan {limit_n} jurnal dengan debit di atas Rp {batas:,} untuk sampling audit."
        )
        calls = [
            {
                "name": "run_sqlite_query",
                "arguments": {
                    "db_path": f"{folder}/ledger.db",
                    "sql": "SELECT c.category, SUM(jl.debit) AS total_debit, SUM(jl.credit) AS total_credit FROM coa c LEFT JOIN journal_lines jl ON jl.account_code = c.code GROUP BY c.category",
                    "params": [],
                },
            },
            {
                "name": "run_sqlite_query",
                "arguments": {
                    "db_path": f"{folder}/ledger.db",
                    "sql": f"SELECT j.id, j.entry_date, j.description, jl.account_code, jl.debit FROM journals j JOIN journal_lines jl ON j.id = jl.journal_id WHERE jl.debit > ? ORDER BY jl.debit DESC LIMIT {limit_n}",
                    "params": [batas],
                },
            },
        ]
    elif pattern == 4:
        # Verifikasi Balance Gate sebelum membangun Dashboard Non-HTML (Excel Native + Desktop GUI)
        mode_dash = rng.choice(["excel_native", "desktop_gui"])
        user_txt = (
            f"[Batch #{batch_id}] Verifikasi keseimbangan Neraca di {folder}/ledger.db periode {yr}-{mo}, "
            f"lalu buat dashboard interaktif non-HTML mode {mode_dash}."
        )
        dash_args: dict[str, Any] = {"mode": mode_dash, "db_path": f"{folder}/ledger.db"}
        if mode_dash == "excel_native":
            dash_args["output_excel_path"] = f"{folder}/Laporan_Baru_{yr}/Dashboard_{unit}_{mo}.xlsx"
        calls = [
            {"name": "verify_accounting_balance", "arguments": {"db_path": f"{folder}/ledger.db", "period": f"{yr}-{mo}"}},
            {"name": "build_non_html_dashboard", "arguments": dash_args},
        ]
    elif pattern == 5:
        # RWED Safe Patch Edit pada file catatan KKA / konfigurasi mapping CoA
        kka_file = f"kka_{unit}_{yr}_{mo}.md"
        old_st, new_st = rng.choice([("DRAFT", "REVIEWED"), ("OPEN", "CLOSED"), ("PENDING", "VERIFIED")])
        user_txt = (
            f"[Batch #{batch_id}] Baca file {folder}/{kka_file} lalu perbarui 'Status: {old_st}' menjadi "
            f"'Status: {new_st}' dengan patch edit aman."
        )
        calls = [
            {"name": "rwed_file", "arguments": {"action": "read", "path": f"{folder}/{kka_file}"}},
            {
                "name": "rwed_file",
                "arguments": {
                    "action": "edit",
                    "path": f"{folder}/{kka_file}",
                    "target": f"Status: {old_st}",
                    "replacement": f"Status: {new_st}",
                },
            },
        ]
    elif pattern == 6:
        # RWED Write Memo Temuan Audit Baru
        memo_file = f"memo_audit_{unit}_{batch_id}.txt"
        topik = rng.choice(["Ekualisasi PPN & PPh 23", "Rekonsiliasi Bank", "Aging Piutang Air", "Varians RKAP"])
        user_txt = f"[Batch #{batch_id}] Simpan ringkasan temuan {topik} ke {folder}/Laporan_Baru_{yr}/{memo_file}."
        calls = [
            {
                "name": "rwed_file",
                "arguments": {
                    "action": "write",
                    "path": f"{folder}/Laporan_Baru_{yr}/{memo_file}",
                    "content": f"Ringkasan Temuan {topik} ({ent_slug} {yr}-{mo}) telah diverifikasi berbasis SQLite3.\n",
                },
            }
        ]
    elif pattern == 7:
        # Safe Delete Guard: user minta hapus file sementara tanpa konfirmasi eksplisit -> confirm_delete=False
        tmp_file = f"draft_sementara_{unit}_{batch_id}.txt"
        user_txt = f"[Batch #{batch_id}] Hapus file sementara {folder}/{tmp_file} dari folder kerja (belum ada konfirmasi eksplisit)."
        calls = [
            {
                "name": "rwed_file",
                "arguments": {
                    "action": "delete",
                    "path": f"{folder}/{tmp_file}",
                    "confirm_delete": False,
                },
            }
        ]
    else:
        # Program-Aided Calculation: delegasikan perhitungan proyeksi/EBITDA/rasio ke Python Decimal sandbox
        rev = rng.randint(1500, 15000) * 1_000_000
        growth = rng.choice([6, 8, 10, 12, 15])
        years = rng.choice([3, 5])
        user_txt = (
            f"[Batch #{batch_id}] Hitung proyeksi pendapatan {ent_slug} selama {years} tahun "
            f"dari basis Rp {rev:,} dengan pertumbuhan majemuk {growth}%/tahun menggunakan Python Decimal."
        )
        code = (
            f"base = Decimal('{rev}')\n"
            f"rate = Decimal('1') + Decimal('{growth}') / Decimal('100')\n"
            f"result = int((base * (rate ** {years})).quantize(Decimal('1'), rounding=ROUND_HALF_UP))"
        )
        calls = [{"name": "run_python_calc", "arguments": {"code": code}}]

    return _msg("expert_4_agentic", user_txt, {"tool_calls": calls})
