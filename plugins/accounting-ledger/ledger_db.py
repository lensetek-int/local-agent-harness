"""
SQLite Double-Entry Bookkeeping Engine for Lensetek Accounting Plugin.
Strictly enforces Debit == Credit on every journal entry. Zero dummy transactions.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_COA = [
    ("1-101", "Kas (Cash)", "asset", "debit"),
    ("1-102", "Bank", "asset", "debit"),
    ("1-103", "Piutang Usaha (Accounts Receivable)", "asset", "debit"),
    ("1-201", "Peralatan & Aset Tetap", "asset", "debit"),
    ("2-101", "Utang Usaha (Accounts Payable)", "liability", "credit"),
    ("2-102", "Utang Pajak", "liability", "credit"),
    ("3-101", "Modal Pemilik (Owner Equity)", "equity", "credit"),
    ("3-102", "Laba Ditahan (Retained Earnings)", "equity", "credit"),
    ("4-101", "Pendapatan Usaha (Revenue)", "revenue", "credit"),
    ("4-102", "Pendapatan Lain-lain", "revenue", "credit"),
    ("5-101", "Beban Operasional", "expense", "debit"),
    ("5-102", "Beban Gaji", "expense", "debit"),
    ("5-103", "Beban Sewa & Utilitas", "expense", "debit"),
]


def get_db_path(workspace_root: Path) -> Path:
    d = Path(workspace_root).resolve() / ".lensetek-accounting"
    d.mkdir(parents=True, exist_ok=True)
    return d / "ledger.db"


def get_conn(workspace_root: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(get_db_path(workspace_root)))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    _init_schema(conn)
    return conn


def _init_schema(conn: sqlite3.Connection):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS accounts (
            code TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('asset','liability','equity','revenue','expense')),
            normal_balance TEXT NOT NULL CHECK(normal_balance IN ('debit','credit'))
        );

        CREATE TABLE IF NOT EXISTS journal_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_date TEXT NOT NULL,
            journal_type TEXT NOT NULL DEFAULT 'general',
            ref_no TEXT DEFAULT '',
            description TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS journal_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_id INTEGER NOT NULL,
            account_code TEXT NOT NULL,
            debit REAL NOT NULL DEFAULT 0,
            credit REAL NOT NULL DEFAULT 0,
            memo TEXT DEFAULT '',
            FOREIGN KEY (entry_id) REFERENCES journal_entries(id) ON DELETE CASCADE,
            FOREIGN KEY (account_code) REFERENCES accounts(code)
        );
        """
    )
    cnt = conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
    if cnt == 0:
        conn.executemany(
            "INSERT INTO accounts (code, name, type, normal_balance) VALUES (?, ?, ?, ?)",
            DEFAULT_COA,
        )
    conn.commit()


def list_accounts(workspace_root: Path) -> List[Dict[str, Any]]:
    conn = get_conn(workspace_root)
    try:
        rows = conn.execute("SELECT * FROM accounts ORDER BY code").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def add_account(workspace_root: Path, code: str, name: str, acc_type: str) -> Dict[str, Any]:
    clean_code = code.strip()
    clean_name = name.strip()
    t = acc_type.strip().lower()
    if not clean_code or not clean_name:
        raise ValueError("Account code and name are required.")
    if t not in ("asset", "liability", "equity", "revenue", "expense"):
        raise ValueError("Invalid account type.")
    normal_bal = "debit" if t in ("asset", "expense") else "credit"

    conn = get_conn(workspace_root)
    try:
        conn.execute(
            "INSERT INTO accounts (code, name, type, normal_balance) VALUES (?, ?, ?, ?)",
            (clean_code, clean_name, t, normal_bal),
        )
        conn.commit()
        return {"code": clean_code, "name": clean_name, "type": t, "normal_balance": normal_bal}
    finally:
        conn.close()


def create_journal_entry(
    workspace_root: Path,
    entry_date: str,
    description: str,
    lines: List[Dict[str, Any]],
    journal_type: str = "general",
    ref_no: str = "",
) -> Dict[str, Any]:
    if not description.strip():
        raise ValueError("Description is required.")
    if not lines or len(lines) < 2:
        raise ValueError("A double-entry journal requires at least 2 lines.")

    clean_lines = []
    tot_d = 0.0
    tot_c = 0.0
    for ln in lines:
        code = str(ln.get("account_code", "")).strip()
        d = round(float(ln.get("debit", 0) or 0), 2)
        c = round(float(ln.get("credit", 0) or 0), 2)
        memo = str(ln.get("memo", "")).strip()
        if not code:
            raise ValueError("Each journal line must specify an account_code.")
        if d < 0 or c < 0:
            raise ValueError("Debit/Credit amounts cannot be negative.")
        if d == 0 and c == 0:
            continue
        tot_d = round(tot_d + d, 2)
        tot_c = round(tot_c + c, 2)
        clean_lines.append((code, d, c, memo))

    if len(clean_lines) < 2 or tot_d <= 0:
        raise ValueError("Journal must have valid non-zero debit and credit lines.")
    if abs(tot_d - tot_c) > 0.009:
        raise ValueError(f"Unbalanced journal entry: Debit ({tot_d:,.2f}) != Credit ({tot_c:,.2f}).")

    j_type = journal_type.strip().lower()
    if j_type not in ("general", "sales", "purchase", "cash_in", "cash_out", "adjusting"):
        j_type = "general"

    now_iso = time.strftime("%Y-%m-%dT%H:%M:%S")
    e_date = entry_date.strip() or time.strftime("%Y-%m-%d")

    conn = get_conn(workspace_root)
    try:
        cur = conn.execute(
            "INSERT INTO journal_entries (entry_date, journal_type, ref_no, description, created_at) VALUES (?, ?, ?, ?, ?)",
            (e_date, j_type, ref_no.strip(), description.strip(), now_iso),
        )
        eid = cur.lastrowid
        for code, d, c, memo in clean_lines:
            conn.execute(
                "INSERT INTO journal_lines (entry_id, account_code, debit, credit, memo) VALUES (?, ?, ?, ?, ?)",
                (eid, code, d, c, memo),
            )
        conn.commit()
        return {"id": eid, "entry_date": e_date, "journal_type": j_type, "total": tot_d}
    finally:
        conn.close()


def list_journals(workspace_root: Path, journal_type: str = "") -> List[Dict[str, Any]]:
    conn = get_conn(workspace_root)
    try:
        if journal_type and journal_type != "all":
            entries = conn.execute(
                "SELECT * FROM journal_entries WHERE journal_type = ? ORDER BY entry_date DESC, id DESC",
                (journal_type,),
            ).fetchall()
        else:
            entries = conn.execute(
                "SELECT * FROM journal_entries ORDER BY entry_date DESC, id DESC"
            ).fetchall()

        out = []
        for e in entries:
            ed = dict(e)
            lines = conn.execute(
                """
                SELECT jl.*, a.name AS account_name
                FROM journal_lines jl
                JOIN accounts a ON a.code = jl.account_code
                WHERE jl.entry_id = ?
                ORDER BY jl.id
                """,
                (e["id"],),
            ).fetchall()
            ed["lines"] = [dict(l) for l in lines]
            ed["total_debit"] = round(sum(l["debit"] for l in ed["lines"]), 2)
            ed["total_credit"] = round(sum(l["credit"] for l in ed["lines"]), 2)
            out.append(ed)
        return out
    finally:
        conn.close()


def delete_journal_entry(workspace_root: Path, entry_id: int) -> bool:
    conn = get_conn(workspace_root)
    try:
        cur = conn.execute("DELETE FROM journal_entries WHERE id = ?", (entry_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def get_general_ledger(workspace_root: Path, account_code: str) -> Dict[str, Any]:
    conn = get_conn(workspace_root)
    try:
        acc = conn.execute("SELECT * FROM accounts WHERE code = ?", (account_code,)).fetchone()
        if not acc:
            raise ValueError(f"Account '{account_code}' not found.")
        rows = conn.execute(
            """
            SELECT je.entry_date, je.ref_no, je.description, je.journal_type,
                   jl.debit, jl.credit, jl.memo
            FROM journal_lines jl
            JOIN journal_entries je ON je.id = jl.entry_id
            WHERE jl.account_code = ?
            ORDER BY je.entry_date ASC, je.id ASC, jl.id ASC
            """,
            (account_code,),
        ).fetchall()

        bal = 0.0
        movements = []
        is_debit_normal = acc["normal_balance"] == "debit"
        for r in rows:
            d = float(r["debit"])
            c = float(r["credit"])
            bal = round(bal + (d - c if is_debit_normal else c - d), 2)
            item = dict(r)
            item["balance"] = bal
            movements.append(item)

        return {"account": dict(acc), "movements": movements, "ending_balance": bal}
    finally:
        conn.close()


def get_trial_balance(workspace_root: Path) -> Dict[str, Any]:
    conn = get_conn(workspace_root)
    try:
        rows = conn.execute(
            """
            SELECT a.code, a.name, a.type, a.normal_balance,
                   COALESCE(SUM(jl.debit), 0) AS total_debit,
                   COALESCE(SUM(jl.credit), 0) AS total_credit
            FROM accounts a
            LEFT JOIN journal_lines jl ON jl.account_code = a.code
            GROUP BY a.code
            ORDER BY a.code
            """
        ).fetchall()

        accounts = []
        grand_debit = 0.0
        grand_credit = 0.0
        for r in rows:
            td = round(float(r["total_debit"]), 2)
            tc = round(float(r["total_credit"]), 2)
            if td == 0 and tc == 0:
                continue
            net = td - tc
            bal_d = round(net, 2) if net > 0 else 0.0
            bal_c = round(-net, 2) if net < 0 else 0.0
            grand_debit = round(grand_debit + bal_d, 2)
            grand_credit = round(grand_credit + bal_c, 2)
            accounts.append({
                "code": r["code"],
                "name": r["name"],
                "type": r["type"],
                "debit": bal_d,
                "credit": bal_c,
            })

        return {
            "rows": accounts,
            "total_debit": grand_debit,
            "total_credit": grand_credit,
            "is_balanced": abs(grand_debit - grand_credit) < 0.01,
        }
    finally:
        conn.close()


def get_financial_statements(workspace_root: Path) -> Dict[str, Any]:
    tb = get_trial_balance(workspace_root)
    revenues, expenses, assets, liabilities, equities = [], [], [], [], []
    tot_rev = tot_exp = tot_asset = tot_liab = tot_eq = 0.0

    for r in tb["rows"]:
        t = r["type"]
        if t == "revenue":
            amt = round(r["credit"] - r["debit"], 2)
            revenues.append({**r, "amount": amt})
            tot_rev = round(tot_rev + amt, 2)
        elif t == "expense":
            amt = round(r["debit"] - r["credit"], 2)
            expenses.append({**r, "amount": amt})
            tot_exp = round(tot_exp + amt, 2)
        elif t == "asset":
            amt = round(r["debit"] - r["credit"], 2)
            assets.append({**r, "amount": amt})
            tot_asset = round(tot_asset + amt, 2)
        elif t == "liability":
            amt = round(r["credit"] - r["debit"], 2)
            liabilities.append({**r, "amount": amt})
            tot_liab = round(tot_liab + amt, 2)
        elif t == "equity":
            amt = round(r["credit"] - r["debit"], 2)
            equities.append({**r, "amount": amt})
            tot_eq = round(tot_eq + amt, 2)

    net_income = round(tot_rev - tot_exp, 2)
    return {
        "trial_balance": tb,
        "income_statement": {
            "revenues": revenues,
            "expenses": expenses,
            "total_revenue": tot_rev,
            "total_expense": tot_exp,
            "net_income": net_income,
        },
        "balance_sheet": {
            "assets": assets,
            "liabilities": liabilities,
            "equities": equities,
            "total_assets": tot_asset,
            "total_liabilities": tot_liab,
            "total_equity": tot_eq,
            "current_net_income": net_income,
            "total_liab_and_equity": round(tot_liab + tot_eq + net_income, 2),
        },
    }
