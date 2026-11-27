"""Generator Dashboard Interaktif Non-HTML (Excel Native Chart & Desktop GUI Tkinter)."""

from pathlib import Path
from typing import Any

from runtime.db import get_readonly_connection, verify_balance_gate


def _fetch_financial_summary(db_path: str | Path) -> dict[str, Any]:
    """Mengambil ringkasan posisi keuangan & laba rugi dari SQLite3."""
    gate = verify_balance_gate(db_path)
    with get_readonly_connection(db_path) as conn:
        cat_rows = conn.execute(
            """
            SELECT c.category,
                   COALESCE(SUM(CASE WHEN c.normal_balance = 'DEBIT' THEN jl.debit - jl.credit ELSE jl.credit - jl.debit END), 0) AS saldo
            FROM coa c
            LEFT JOIN journal_lines jl ON jl.account_code = c.code
            GROUP BY c.category
            """
        ).fetchall()
    summary = {r["category"]: int(r["saldo"]) for r in cat_rows}
    return {"gate": gate, "summary": summary}


def build_excel_native_dashboard(
    db_path: str | Path,
    output_excel_path: str | Path,
) -> dict[str, Any]:
    """Membuat sheet 'Dashboard' di file .xlsx berisi KPI keuangan dan BarChart native Excel."""
    import openpyxl
    from openpyxl.chart import BarChart, Reference
    from openpyxl.styles import Font

    data = _fetch_financial_summary(db_path)
    out = Path(output_excel_path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    wb = openpyxl.load_workbook(str(out)) if out.exists() else openpyxl.Workbook()
    if "Dashboard" in wb.sheetnames:
        del wb["Dashboard"]
    ws = wb.create_sheet(title="Dashboard", index=0)

    ws["A1"] = "RINGKASAN EKSEKUTIF KEUANGAN & AUDIT"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A3"] = "Kategori Akun"
    ws["B3"] = "Saldo (Rp)"
    ws["A3"].font = Font(bold=True)
    ws["B3"].font = Font(bold=True)

    ordered_cats = ["ASET", "KEWAJIBAN", "EKUITAS", "PENDAPATAN", "BEBAN"]
    for idx, cat in enumerate(ordered_cats, start=4):
        ws.cell(row=idx, column=1, value=cat)
        ws.cell(row=idx, column=2, value=data["summary"].get(cat, 0))
        ws.cell(row=idx, column=2).number_format = "#,##0"

    ws["A10"] = "Laba / (Rugi) Berjalan"
    ws["B10"] = data["gate"]["laba_berjalan"]
    ws["B10"].number_format = "#,##0"
    ws["A11"] = "Status Balance Gate"
    ws["B11"] = "BALANCED" if data["gate"]["balanced"] else "UNBALANCED"

    chart = BarChart()
    chart.title = "Posisi Keuangan & Kinerja (Rp)"
    chart.y_axis.title = "Rupiah"
    data_ref = Reference(ws, min_col=2, min_row=3, max_row=8)
    cats_ref = Reference(ws, min_col=1, min_row=4, max_row=8)
    chart.add_data(data_ref, titles_from_data=True)
    chart.set_categories(cats_ref)
    chart.width = 16
    chart.height = 9
    ws.add_chart(chart, "D3")

    wb.save(str(out))
    wb.close()
    return {"status": "ok", "dashboard_excel": str(out), "balanced": data["gate"]["balanced"]}


def launch_desktop_dashboard(db_path: str | Path) -> None:
    """Menjalankan aplikasi desktop GUI offline (Tkinter, non-HTML) untuk melihat ringkasan audit."""
    import tkinter as tk
    from tkinter import ttk

    data = _fetch_financial_summary(db_path)
    root = tk.Tk()
    root.title("Audit & Accounting Local Dashboard (Offline)")
    root.geometry("520x360")

    header = ttk.Label(root, text="Ringkasan Keuangan SQLite3", font=("Segoe UI", 13, "bold"))
    header.pack(pady=10)

    tree = ttk.Treeview(root, columns=("Kategori", "Saldo"), show="headings", height=7)
    tree.heading("Kategori", text="Kategori Akun")
    tree.heading("Saldo", text="Saldo (Rp)")
    tree.pack(fill="both", expand=True, padx=16, pady=8)

    for cat in ("ASET", "KEWAJIBAN", "EKUITAS", "PENDAPATAN", "BEBAN"):
        val = data["summary"].get(cat, 0)
        tree.insert("", "end", values=(cat, f"Rp {val:,}"))

    status_txt = "BALANCED (Aman)" if data["gate"]["balanced"] else "UNBALANCED (Perlu Cek)"
    ttk.Label(root, text=f"Balance Gate: {status_txt} | Laba Berjalan: Rp {data['gate']['laba_berjalan']:,}").pack(pady=8)
    root.mainloop()
