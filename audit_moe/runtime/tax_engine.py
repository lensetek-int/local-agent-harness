"""Tax Rule Engine deterministik untuk Perpajakan Indonesia (PPN, PPh 21/22/23/4(2)/Badan, Koreksi Fiskal)."""

from decimal import Decimal, ROUND_HALF_UP
from typing import Any


def _round_rupiah(amount: Decimal) -> int:
    """Membulatkan nominal Decimal ke Rupiah integer terdekat."""
    return int(amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def calculate_ppn(dpp_komersial: int, is_luxury_goods: bool = False) -> dict[str, Any]:
    """Menghitung PPN sesuai PMK 131/2024:
    - Barang mewah: tarif 12% x harga jual/DPP penuh.
    - Barang/jasa non-mewah: tarif 12% x DPP Nilai Lain (11/12 x harga jual/penggantian).
    """
    dpp_val = Decimal(dpp_komersial)
    if dpp_val < 0:
        raise ValueError("DPP tidak boleh negatif.")

    if is_luxury_goods:
        dpp_nilai_lain = dpp_val
        ppn = dpp_nilai_lain * Decimal("0.12")
        skema = "PPN 12% DPP Penuh (Barang Mewah)"
    else:
        dpp_nilai_lain = dpp_val * Decimal("11") / Decimal("12")
        ppn = dpp_nilai_lain * Decimal("0.12")
        skema = "PPN 12% x DPP Nilai Lain (11/12) - PMK 131/2024"

    return {
        "jenis_pajak": "PPN",
        "skema": skema,
        "dpp_komersial": _round_rupiah(dpp_val),
        "dpp_nilai_lain": _round_rupiah(dpp_nilai_lain),
        "ppn_terutang": _round_rupiah(ppn),
    }


def calculate_withholding_tax(
    tax_type: str,
    dpp: int,
    has_npwp: bool = True,
    custom_rate_percent: float | None = None,
) -> dict[str, Any]:
    """Menghitung pemotongan/pemungutan PPh 22, PPh 23, atau PPh 4(2) secara deterministik."""
    dpp_val = Decimal(dpp)
    if dpp_val < 0:
        raise ValueError("DPP tidak boleh negatif.")

    default_rates: dict[str, Decimal] = {
        "PPH_22_PENGADAAN": Decimal("1.5"),
        "PPH_23_JASA": Decimal("2.0"),
        "PPH_23_DIVIDEN_ROYALTI": Decimal("15.0"),
        "PPH_4_2_SEWA_TANAH_BANGUNAN": Decimal("10.0"),
        "PPH_4_2_UMKM": Decimal("0.5"),
    }

    if custom_rate_percent is not None:
        rate = Decimal(str(custom_rate_percent))
    elif tax_type in default_rates:
        rate = default_rates[tax_type]
    else:
        raise ValueError(f"Jenis pajak tidak dikenal tanpa custom_rate_percent: {tax_type}")

    # Catatan: PPh 23 tanpa NPWP dikenakan tarif 100% lebih tinggi (UU PPh)
    multiplier = Decimal("2") if (tax_type.startswith("PPH_23") and not has_npwp) else Decimal("1")
    effective_rate = rate * multiplier
    tax_amount = dpp_val * (effective_rate / Decimal("100"))

    return {
        "jenis_pajak": tax_type,
        "dpp": _round_rupiah(dpp_val),
        "tarif_efektif_persen": float(effective_rate),
        "pajak_terutang": _round_rupiah(tax_amount),
        "has_npwp": has_npwp,
    }


def calculate_pph21_ter(bruto_bulanan: int, ter_rate_percent: float, category: str = "A") -> dict[str, Any]:
    """Menghitung PPh 21 bulanan skema TER (PP 58/2023) berdasarkan tarif tabel kategori A/B/C."""
    if bruto_bulanan < 0 or ter_rate_percent < 0:
        raise ValueError("Bruto dan tarif TER tidak boleh negatif.")
    if category not in ("A", "B", "C"):
        raise ValueError("Kategori TER harus 'A', 'B', atau 'C'.")

    pph21 = Decimal(bruto_bulanan) * (Decimal(str(ter_rate_percent)) / Decimal("100"))
    return {
        "jenis_pajak": "PPh 21 TER",
        "kategori": category,
        "bruto_bulanan": bruto_bulanan,
        "tarif_ter_persen": ter_rate_percent,
        "pph21_terutang": _round_rupiah(pph21),
    }


def calculate_fiscal_reconciliation(
    commercial_profit: int,
    positive_corrections: list[dict[str, Any]],
    negative_corrections: list[dict[str, Any]],
    corporate_tax_rate_percent: float = 22.0,
) -> dict[str, Any]:
    """Menghitung Laba Kena Pajak dan PPh Badan terutang dari rekonsiliasi fiskal."""
    total_pos = sum(int(item["amount"]) for item in positive_corrections)
    total_neg = sum(int(item["amount"]) for item in negative_corrections)
    fiscal_profit = commercial_profit + total_pos - total_neg
    taxable_income = max(0, fiscal_profit)
    pph_badan = _round_rupiah(Decimal(taxable_income) * (Decimal(str(corporate_tax_rate_percent)) / Decimal("100")))

    return {
        "laba_komersial": commercial_profit,
        "koreksi_positif": total_pos,
        "koreksi_negatif": total_neg,
        "laba_fiskal": fiscal_profit,
        "pkp": taxable_income,
        "tarif_pph_badan_persen": corporate_tax_rate_percent,
        "pph_badan_terutang": pph_badan,
    }
