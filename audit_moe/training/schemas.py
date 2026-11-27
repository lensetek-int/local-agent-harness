"""Skema tool dan kontrak output JSON untuk 4 Expert Audit & Pajak MoE."""

from typing import Any

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "list_client_files",
        "description": "Membaca daftar file (.xls, .xlsx, .docx, .pdf, gambar) di folder kerja klien dalam workspace.",
        "parameters": {
            "type": "object",
            "properties": {
                "directory": {"type": "string", "description": "Path relatif folder klien dalam workspace", "default": "."},
                "recursive": {"type": "boolean", "default": True},
            },
            "required": ["directory"],
        },
    },
    {
        "name": "inspect_excel_template",
        "description": "Membaca nama sheet, header kolom, dan sel berformula pada file Excel (.xls/.xlsx) klien.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
                "max_rows": {"type": "integer", "default": 25},
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "write_excel_preserving_template",
        "description": "Menyalin template .xlsx ke output baru dan menulis baris data tanpa menimpa sel berformula.",
        "parameters": {
            "type": "object",
            "properties": {
                "template_path": {"type": "string"},
                "output_path": {"type": "string"},
                "sheet_name": {"type": "string"},
                "start_row": {"type": "integer"},
                "start_col": {"type": "integer", "default": 1},
                "rows": {"type": "array", "items": {"type": "array"}},
            },
            "required": ["template_path", "output_path", "sheet_name", "start_row", "rows"],
        },
    },
    {
        "name": "read_document_or_ocr",
        "description": "Membaca isi DOCX, PDF teks, atau gambar/PDF scan via OCR lokal.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
                "use_ocr": {"type": "boolean", "default": False},
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "rwed_file",
        "description": "Operasi Read/Write/Edit (patch target->replacement)/Delete file teks dalam sandbox aman.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["read", "write", "edit", "delete"]},
                "path": {"type": "string"},
                "content": {"type": "string"},
                "target": {"type": "string"},
                "replacement": {"type": "string"},
                "confirm_delete": {"type": "boolean", "default": False},
            },
            "required": ["action", "path"],
        },
    },
    {
        "name": "run_sqlite_query",
        "description": "Menjalankan query SQL read-only (SELECT) pada database akuntansi SQLite3 lokal.",
        "parameters": {
            "type": "object",
            "properties": {
                "db_path": {"type": "string"},
                "sql": {"type": "string"},
                "params": {"type": "array", "default": []},
            },
            "required": ["db_path", "sql"],
        },
    },
    {
        "name": "verify_accounting_balance",
        "description": "Memvalidasi keseimbangan Debit == Kredit dan Aset == Kewajiban + Ekuitas + Laba.",
        "parameters": {
            "type": "object",
            "properties": {
                "db_path": {"type": "string"},
                "period": {"type": "string"},
            },
            "required": ["db_path"],
        },
    },
    {
        "name": "build_non_html_dashboard",
        "description": "Membuat dashboard interaktif non-HTML (Excel Native Chart atau Desktop GUI).",
        "parameters": {
            "type": "object",
            "properties": {
                "mode": {"type": "string", "enum": ["excel_native", "desktop_gui"]},
                "db_path": {"type": "string"},
                "output_excel_path": {"type": "string"},
            },
            "required": ["mode", "db_path"],
        },
    },
    {
        "name": "run_python_calc",
        "description": "Menjalankan kode Python berbasis Decimal/math di sandbox aman untuk menghitung angka akuntansi, rasio, dan proyeksi tanpa salah hitung.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Kode Python yang menyimpan hasil akhir ke variabel `result`"},
            },
            "required": ["code"],
        },
    },
]
