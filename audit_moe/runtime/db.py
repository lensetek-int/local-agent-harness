"""Layer database SQLite3 lokal untuk CoA, Jurnal, Pajak, dan Audit Trail dengan presisi Integer/Decimal."""

from contextlib import contextmanager
from decimal import Decimal, ROUND_HALF_UP
import json
import sqlite3
from pathlib import Path
from typing import Any, Iterator


def to_rupiah_int(value: int | float | str | Decimal) -> int:
    """Mengonversi angka ke integer Rupiah bulat menggunakan Decimal agar bebas galat float."""
    d = Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(d)


@contextmanager
def get_connection(db_path: str | Path) -> Iterator[sqlite3.Connection]:
    """Membuka koneksi SQLite3 read-write, auto-commit/rollback, dan menutup koneksi saat keluar."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def get_readonly_connection(db_path: str | Path) -> Iterator[sqlite3.Connection]:
    """Membuka koneksi SQLite3 mode read-only (?mode=ro + query_only) untuk query aman dari LLM."""
    resolved = Path(db_path).resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"Database tidak ditemukan: {resolved}")
    uri = f"{resolved.as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON;")
    try:
        yield conn
    finally:
        conn.close()


def init_db(db_path: str | Path) -> None:
    """Inisialisasi skema tabel akuntansi, pajak, dan audit trail (nominal INTEGER)."""
    with get_connection(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS coa (
                code TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL CHECK (category IN ('ASET', 'KEWAJIBAN', 'EKUITAS', 'PENDAPATAN', 'BEBAN')),
                normal_balance TEXT NOT NULL CHECK (normal_balance IN ('DEBIT', 'CREDIT'))
            );

            CREATE TABLE IF NOT EXISTS journals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_date TEXT NOT NULL,
                source_file TEXT,
                description TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'POSTED',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS journal_lines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                journal_id INTEGER NOT NULL REFERENCES journals(id) ON DELETE CASCADE,
                account_code TEXT NOT NULL REFERENCES coa(code),
                debit INTEGER NOT NULL DEFAULT 0 CHECK (debit >= 0),
                credit INTEGER NOT NULL DEFAULT 0 CHECK (credit >= 0),
                tax_code TEXT
            );

            CREATE TABLE IF NOT EXISTS tax_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                journal_id INTEGER REFERENCES journals(id) ON DELETE SET NULL,
                tax_type TEXT NOT NULL,
                dpp INTEGER NOT NULL DEFAULT 0,
                tax_amount INTEGER NOT NULL DEFAULT 0,
                fiscal_correction_type TEXT CHECK (fiscal_correction_type IN ('NONE', 'POSITIVE', 'NEGATIVE'))
            );

            CREATE TABLE IF NOT EXISTS audit_trail (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                actor TEXT NOT NULL,
                action TEXT NOT NULL,
                target TEXT NOT NULL,
                detail_json TEXT
            );
            """
        )


def insert_journal(
    db_path: str | Path,
    entry_date: str,
    description: str,
    lines: list[dict[str, Any]],
    source_file: str | None = None,
) -> int:
    """Menyimpan jurnal dengan validasi ketat Decimal/Integer Debit == Kredit sebelum commit."""
    parsed_lines = []
    total_debit = 0
    total_credit = 0
    for line in lines:
        d = to_rupiah_int(line.get("debit", 0))
        c = to_rupiah_int(line.get("credit", 0))
        if d < 0 or c < 0:
            raise ValueError("Nominal debit/kredit tidak boleh negatif.")
        total_debit += d
        total_credit += c
        parsed_lines.append((line["account_code"], d, c, line.get("tax_code")))

    if total_debit != total_credit or total_debit <= 0:
        raise ValueError(f"Jurnal tidak seimbang: Debit={total_debit}, Kredit={total_credit}")

    with get_connection(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO journals (entry_date, source_file, description) VALUES (?, ?, ?)",
            (entry_date, source_file, description),
        )
        journal_id = int(cur.lastrowid)
        for account_code, d, c, tax_code in parsed_lines:
            conn.execute(
                "INSERT INTO journal_lines (journal_id, account_code, debit, credit, tax_code) VALUES (?, ?, ?, ?, ?)",
                (journal_id, account_code, d, c, tax_code),
            )
        conn.execute(
            "INSERT INTO audit_trail (actor, action, target, detail_json) VALUES (?, ?, ?, ?)",
            ("agent_runtime", "INSERT_JOURNAL", f"journal:{journal_id}", json.dumps({"total": total_debit})),
        )
    return journal_id


def verify_balance_gate(db_path: str | Path) -> dict[str, Any]:
    """Hard-gate validasi Trial Balance (Debit == Kredit) dan Persamaan Akuntansi (Aset == Kewajiban + Ekuitas + Laba)."""
    with get_readonly_connection(db_path) as conn:
        tb_row = conn.execute(
            "SELECT COALESCE(SUM(debit), 0) AS total_debit, COALESCE(SUM(credit), 0) AS total_credit FROM journal_lines"
        ).fetchone()
        cat_rows = conn.execute(
            """
            SELECT c.category, c.normal_balance,
                   COALESCE(SUM(jl.debit), 0) AS sum_debit,
                   COALESCE(SUM(jl.credit), 0) AS sum_credit
            FROM coa c
            LEFT JOIN journal_lines jl ON jl.account_code = c.code
            GROUP BY c.category, c.normal_balance
            """
        ).fetchall()

    total_debit = int(tb_row["total_debit"])
    total_credit = int(tb_row["total_credit"])
    tb_diff = total_debit - total_credit

    totals: dict[str, int] = {k: 0 for k in ("ASET", "KEWAJIBAN", "EKUITAS", "PENDAPATAN", "BEBAN")}
    for r in cat_rows:
        sd, sc = int(r["sum_debit"]), int(r["sum_credit"])
        net = (sd - sc) if r["normal_balance"] == "DEBIT" else (sc - sd)
        totals[r["category"]] += net

    laba_berjalan = totals["PENDAPATAN"] - totals["BEBAN"]
    pasiva_plus_ekuitas = totals["KEWAJIBAN"] + totals["EKUITAS"] + laba_berjalan
    eq_diff = totals["ASET"] - pasiva_plus_ekuitas

    return {
        "balanced": tb_diff == 0 and eq_diff == 0,
        "trial_balance_ok": tb_diff == 0,
        "accounting_eq_ok": eq_diff == 0,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "trial_balance_diff": tb_diff,
        "aset": totals["ASET"],
        "kewajiban": totals["KEWAJIBAN"],
        "ekuitas": totals["EKUITAS"],
        "laba_berjalan": laba_berjalan,
        "accounting_eq_diff": eq_diff,
    }
