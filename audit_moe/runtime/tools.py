"""Tool deterministik aman (sandboxed) untuk RWED file, Excel (.xls/.xlsx), DOCX, PDF, dan SQLite3 RO."""

import shutil
from pathlib import Path
from typing import Any

from runtime.db import get_readonly_connection


class SafeWorkspaceError(PermissionError):
    """Dilempar jika operasi mencoba keluar dari workspace sandbox, menimpa file asli, atau menghapus tanpa izin."""


def _resolve_in_workspace(workspace_root: Path, target_path: str | Path) -> Path:
    """Memastikan path berada di dalam workspace_root untuk mencegah path traversal."""
    root = workspace_root.resolve()
    p = Path(target_path)
    resolved = p.resolve() if p.is_absolute() else (root / p).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise SafeWorkspaceError(f"Akses ditolak di luar workspace: {resolved}") from exc
    return resolved


def rwed_file(
    workspace_root: str | Path,
    action: str,
    path: str,
    content: str | None = None,
    target: str | None = None,
    replacement: str | None = None,
    confirm_delete: bool = False,
) -> dict[str, Any]:
    """Operasi Read, Write, Edit (patch aman), dan Delete file teks dalam sandbox."""
    file_path = _resolve_in_workspace(Path(workspace_root), path)

    if action == "read":
        return {"status": "ok", "path": str(file_path), "content": file_path.read_text(encoding="utf-8")}

    if action == "write":
        if content is None:
            raise ValueError("Parameter 'content' wajib diisi untuk aksi write.")
        file_path.parent.mkdir(parents=True, exist_ok=True)
        if file_path.exists():
            shutil.copy2(file_path, file_path.with_suffix(file_path.suffix + ".bak"))
        file_path.write_text(content, encoding="utf-8")
        return {"status": "ok", "action": "write", "path": str(file_path)}

    if action == "edit":
        if target is None or replacement is None:
            raise ValueError("Parameter 'target' dan 'replacement' wajib diisi untuk aksi edit.")
        existing = file_path.read_text(encoding="utf-8")
        if target not in existing:
            raise ValueError("Teks 'target' tidak ditemukan di dalam file; edit dibatalkan.")
        shutil.copy2(file_path, file_path.with_suffix(file_path.suffix + ".bak"))
        updated = existing.replace(target, replacement, 1)
        file_path.write_text(updated, encoding="utf-8")
        return {"status": "ok", "action": "edit", "path": str(file_path)}

    if action == "delete":
        if not confirm_delete:
            raise SafeWorkspaceError("Operasi delete diblokir: set confirm_delete=True setelah konfirmasi pengguna.")
        if file_path.exists():
            file_path.unlink()
        return {"status": "ok", "action": "delete", "path": str(file_path)}

    raise ValueError(f"Aksi tidak dikenal: {action}")


def list_client_files(
    workspace_root: str | Path,
    directory: str | Path = ".",
    recursive: bool = True,
) -> list[dict[str, Any]]:
    """Mendaftar file keuangan klien (.xls, .xlsx, .docx, .pdf, gambar) secara aman di dalam workspace."""
    base = _resolve_in_workspace(Path(workspace_root), directory)
    allowed_ext = {".xls", ".xlsx", ".docx", ".pdf", ".png", ".jpg", ".jpeg", ".csv"}
    iterator = base.rglob("*") if recursive else base.glob("*")
    return [
        {"name": p.name, "path": str(p), "ext": p.suffix.lower(), "size_bytes": p.stat().st_size}
        for p in iterator
        if p.is_file() and p.suffix.lower() in allowed_ext
    ]


def inspect_excel_template(
    workspace_root: str | Path,
    file_path: str | Path,
    max_rows: int = 25,
) -> dict[str, Any]:
    """Membaca struktur sheet, preview baris awal, dan formula pada file .xlsx atau .xls."""
    target = _resolve_in_workspace(Path(workspace_root), file_path)
    ext = target.suffix.lower()

    if ext == ".xls":
        import xlrd

        book = xlrd.open_workbook(str(target))
        sheets_info: dict[str, Any] = {}
        for name in book.sheet_names():
            sh = book.sheet_by_name(name)
            preview = [sh.row_values(r) for r in range(min(max_rows, sh.nrows))]
            sheets_info[name] = {
                "max_row": sh.nrows,
                "max_col": sh.ncols,
                "formula_cells_sample": [],
                "preview": preview,
            }
        return {"file": str(target), "format": "xls", "sheets": sheets_info}

    import openpyxl

    wb = openpyxl.load_workbook(str(target), data_only=False)
    sheets_info = {}
    for name in wb.sheetnames:
        ws = wb[name]
        preview = []
        formula_cells = []
        for row in ws.iter_rows(min_row=1, max_row=max_rows, values_only=False):
            row_vals = []
            for cell in row:
                val = cell.value
                if isinstance(val, str) and val.startswith("="):
                    formula_cells.append(cell.coordinate)
                row_vals.append(val)
            preview.append(row_vals)
        sheets_info[name] = {
            "max_row": ws.max_row,
            "max_col": ws.max_column,
            "formula_cells_sample": formula_cells[:20],
            "preview": preview,
        }
    wb.close()
    return {"file": str(target), "format": "xlsx", "sheets": sheets_info}


def write_excel_preserving_template(
    workspace_root: str | Path,
    template_path: str | Path,
    output_path: str | Path,
    sheet_name: str,
    start_row: int,
    rows: list[list[Any]],
    start_col: int = 1,
) -> dict[str, Any]:
    """Menyalin template .xlsx ke output baru dan mengisi sel data tanpa menimpa sel berformula."""
    import openpyxl

    root = Path(workspace_root)
    src = _resolve_in_workspace(root, template_path)
    dst = _resolve_in_workspace(root, output_path)
    if src == dst:
        raise SafeWorkspaceError("Dilarang menimpa file template asli; gunakan output_path yang berbeda.")

    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists():
        shutil.copy2(src, dst)

    wb = openpyxl.load_workbook(str(dst))
    if sheet_name not in wb.sheetnames:
        wb.close()
        raise ValueError(f"Sheet '{sheet_name}' tidak ditemukan di {dst.name}")

    ws = wb[sheet_name]
    written = 0
    skipped_formulas: list[str] = []
    for r_offset, row_values in enumerate(rows):
        for c_offset, val in enumerate(row_values):
            cell = ws.cell(row=start_row + r_offset, column=start_col + c_offset)
            if isinstance(cell.value, str) and cell.value.startswith("="):
                skipped_formulas.append(cell.coordinate)
                continue
            cell.value = val
            written += 1

    wb.save(str(dst))
    wb.close()
    return {
        "status": "ok",
        "output_path": str(dst),
        "sheet_name": sheet_name,
        "cells_written": written,
        "skipped_formula_cells": skipped_formulas,
    }


def run_sqlite_query(
    workspace_root: str | Path,
    db_path: str | Path,
    sql: str,
    params: list[Any] | None = None,
) -> list[dict[str, Any]]:
    """Menjalankan query SQL read-only (SELECT) pada database SQLite3 di dalam workspace."""
    target_db = _resolve_in_workspace(Path(workspace_root), db_path)
    with get_readonly_connection(target_db) as conn:
        rows = conn.execute(sql, params or []).fetchall()
    return [dict(r) for r in rows]


def read_docx(workspace_root: str | Path, file_path: str | Path) -> str:
    """Mengekstrak teks paragraf dan tabel dari file .docx di dalam workspace."""
    import docx

    target = _resolve_in_workspace(Path(workspace_root), file_path)
    doc = docx.Document(str(target))
    parts = [p.text for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            parts.append(" | ".join(cell.text.strip() for cell in row.cells))
    return "\n".join(parts)


def read_pdf(workspace_root: str | Path, file_path: str | Path) -> str:
    """Mengekstrak teks dari PDF berbasis teks di dalam workspace."""
    import fitz

    target = _resolve_in_workspace(Path(workspace_root), file_path)
    doc = fitz.open(str(target))
    pages = [page.get_text("text") for page in doc]
    doc.close()
    return "\n--- PAGE BREAK ---\n".join(pages)


def run_python_calc(code: str) -> dict[str, Any]:
    """Menjalankan perhitungan matematika/akuntansi Python dalam sandbox AST aman (hanya Decimal, math, statistics).
    Kode wajib menetapkan hasil akhir ke variabel `result` atau `hasil`.
    """
    import ast
    from decimal import Decimal, ROUND_HALF_UP
    import math
    import statistics

    tree = ast.parse(code, mode="exec")
    forbidden_nodes = (ast.Import, ast.ImportFrom, ast.With, ast.AsyncWith, ast.Try, ast.ClassDef, ast.Global, ast.Nonlocal)
    for node in ast.walk(tree):
        if isinstance(node, forbidden_nodes):
            raise SafeWorkspaceError(f"Operasi tidak diizinkan di sandbox hitung: {type(node).__name__}")
        if isinstance(node, ast.Name) and node.id.startswith("__"):
            raise SafeWorkspaceError("Akses dunder attribute diblokir di sandbox.")
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise SafeWorkspaceError("Akses dunder attribute diblokir di sandbox.")

    safe_globals: dict[str, Any] = {
        "__builtins__": {
            "abs": abs,
            "round": round,
            "min": min,
            "max": max,
            "sum": sum,
            "len": len,
            "range": range,
            "int": int,
            "float": float,
            "str": str,
            "dict": dict,
            "list": list,
            "tuple": tuple,
        },
        "Decimal": Decimal,
        "ROUND_HALF_UP": ROUND_HALF_UP,
        "math": math,
        "statistics": statistics,
    }
    local_env: dict[str, Any] = {}
    exec(compile(tree, "<python_calc>", "exec"), safe_globals, local_env)
    output = local_env.get("result", local_env.get("hasil"))
    if isinstance(output, Decimal):
        output = str(output)
    return {"status": "ok", "result": output}
