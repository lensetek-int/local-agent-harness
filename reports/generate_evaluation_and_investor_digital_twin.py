#!/usr/bin/env python3
"""
Generator Laporan Komprehensif Evaluasi Plan, Analisis Pre-Mortem &
Simulasi Digital Twin 100 Calon Investor Startup (VC, CVC, PE, Crowdfunding, Angel, Grant, FO).

Output:
1. reports/Data_100_Digital_Twin_Investor_dan_PreMortem_Lensetek.xlsx
2. reports/Laporan_Evaluasi_PreMortem_dan_100_Digital_Twin_Investor_Lensetek.docx
3. reports/investor_digital_twin_100.csv
4. reports/investor_digital_twin_100.json
"""

import os
import sys
import json
from collections import Counter
from datetime import datetime

import pandas as pd
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

REPORT_DIR = os.path.dirname(os.path.abspath(__file__))
if REPORT_DIR not in sys.path:
    sys.path.insert(0, REPORT_DIR)

from data_premortem_and_eval import EVALUATION_8_DIMENSIONS, PRE_MORTEM_SCENARIOS
from data_investors_part1 import INVESTORS_PART1
from data_investors_part2 import INVESTORS_PART2

ALL_INVESTORS = INVESTORS_PART1 + INVESTORS_PART2

EXCEL_PATH = os.path.join(REPORT_DIR, "Data_100_Digital_Twin_Investor_dan_PreMortem_Lensetek.xlsx")
DOCX_PATH = os.path.join(REPORT_DIR, "Laporan_Evaluasi_PreMortem_dan_100_Digital_Twin_Investor_Lensetek.docx")
CSV_PATH = os.path.join(REPORT_DIR, "investor_digital_twin_100.csv")
JSON_PATH = os.path.join(REPORT_DIR, "investor_digital_twin_100.json")


# ==============================================================================
# EXCEL BUILDER (OPENPYXL)
# ==============================================================================
def style_header_row(ws, row_idx, max_col, bg_hex="1B365D"):
    fill = PatternFill(start_color=bg_hex, end_color=bg_hex, fill_type="solid")
    font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin = Side(border_style="thin", color="CCCCCC")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    ws.row_dimensions[row_idx].height = 30
    for col in range(1, max_col + 1):
        cell = ws.cell(row=row_idx, column=col)
        cell.fill = fill
        cell.font = font
        cell.alignment = align
        cell.border = border


def build_excel(df_inv, df_seg, df_dec, df_prod):
    wb = openpyxl.Workbook()

    thin_side = Side(border_style="thin", color="D9D9D9")
    cell_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)
    zebra_fill = PatternFill(start_color="F7F9FC", end_color="F7F9FC", fill_type="solid")
    white_fill = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")

    decision_styles = {
        "STRONG YES": (PatternFill("solid", fgColor="D4EDDA"), Font("Calibri", 10, bold=True, color="155724")),
        "CONDITIONAL YES": (PatternFill("solid", fgColor="FFF3CD"), Font("Calibri", 10, bold=True, color="856404")),
        "WAIT & SEE": (PatternFill("solid", fgColor="D1ECF1"), Font("Calibri", 10, bold=True, color="0C5460")),
        "PASS": (PatternFill("solid", fgColor="F8D7DA"), Font("Calibri", 10, bold=True, color="721C24")),
    }
    risk_styles = {
        "CRITICAL": (PatternFill("solid", fgColor="F8D7DA"), Font("Calibri", 10, bold=True, color="721C24")),
        "HIGH": (PatternFill("solid", fgColor="FFE5D0"), Font("Calibri", 10, bold=True, color="984C0C")),
        "MEDIUM-HIGH": (PatternFill("solid", fgColor="FFF3CD"), Font("Calibri", 10, bold=True, color="856404")),
        "MEDIUM": (PatternFill("solid", fgColor="D1ECF1"), Font("Calibri", 10, bold=True, color="0C5460")),
    }

    # --------------------------------------------------------------------------
    # SHEET 1: 100_Digital_Twin_Investor
    # --------------------------------------------------------------------------
    ws1 = wb.active
    ws1.title = "100_Digital_Twin_Investor"

    cols_s1 = [
        ("investor_id", "ID Investor", 11),
        ("nama_persona", "Nama Persona & Jabatan", 28),
        ("institusi_archetype", "Institusi (Digital Twin Archetype)", 34),
        ("kategori_investor", "Kategori Investor", 25),
        ("sub_sektor_fokus", "Fokus Sektor / Tesis", 30),
        ("lokasi_region", "Region", 18),
        ("tahap_investasi", "Tahap / Instrumen", 20),
        ("estimasi_tiket_usd", "Estimasi Tiket (USD)", 22),
        ("skor_teknologi_edge", "Skor Tek Edge (1-5)", 13),
        ("skor_moat_ip", "Skor Moat IP (1-5)", 13),
        ("skor_kebutuhan_pasar", "Skor Urgensi Pasar (1-5)", 14),
        ("skor_kelayakan_monetisasi", "Skor Monetisasi (1-5)", 14),
        ("skor_kesiapan_regulasi_risiko", "Skor Regulasi/Risiko (1-5)", 15),
        ("skor_kualitas_tim_eksekusi", "Skor Eksekusi Tim (1-5)", 14),
        ("skor_konviksi_total", "Konviksi (0-100)", 14),
        ("probabilitas_investasi_pct", "Prob. Deal (%)", 13),
        ("keputusan_investasi", "Keputusan Investasi", 18),
        ("produk_paling_diminati", "Produk Paling Diminati", 34),
        ("red_flag_utama", "Red Flag / Kekhawatiran Utama", 45),
        ("syarat_kunci_deal", "Syarat Kunci (Unlock Milestone)", 45),
        ("verbatim_feedback_persona", "Verbatim Feedback Persona Digital Twin", 58),
    ]

    for c_idx, (_, title, width) in enumerate(cols_s1, 1):
        ws1.cell(row=1, column=c_idx, value=title)
        ws1.column_dimensions[get_column_letter(c_idx)].width = width
    style_header_row(ws1, 1, len(cols_s1))

    for r_idx, row in df_inv.iterrows():
        excel_row = r_idx + 2
        row_fill = zebra_fill if r_idx % 2 == 1 else white_fill
        ws1.row_dimensions[excel_row].height = 68

        for c_idx, (key, _, _) in enumerate(cols_s1, 1):
            val = row[key]
            cell = ws1.cell(row=excel_row, column=c_idx, value=val)
            cell.border = cell_border
            cell.fill = row_fill
            cell.font = Font(name="Calibri", size=10)

            if key in (
                "skor_teknologi_edge", "skor_moat_ip", "skor_kebutuhan_pasar",
                "skor_kelayakan_monetisasi", "skor_kesiapan_regulasi_risiko",
                "skor_kualitas_tim_eksekusi", "probabilitas_investasi_pct"
            ):
                cell.alignment = Alignment(horizontal="center", vertical="center")
            elif key == "skor_konviksi_total":
                cell.alignment = Alignment(horizontal="center", vertical="center")
                cell.number_format = "0.0"
                cell.font = Font(name="Calibri", size=10, bold=True)
            elif key == "keputusan_investasi":
                cell.alignment = Alignment(horizontal="center", vertical="center")
                fill_d, font_d = decision_styles.get(val, (row_fill, Font(name="Calibri", size=10)))
                cell.fill = fill_d
                cell.font = font_d
            elif key == "investor_id":
                cell.alignment = Alignment(horizontal="center", vertical="center")
                cell.font = Font(name="Calibri", size=10, bold=True)
            else:
                cell.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)

    ws1.freeze_panes = "D2"
    ws1.auto_filter.ref = f"A1:{get_column_letter(len(cols_s1))}{len(df_inv) + 1}"

    # --------------------------------------------------------------------------
    # SHEET 2: Ringkasan_Segmen_Investor
    # --------------------------------------------------------------------------
    ws2 = wb.create_sheet("Ringkasan_Segmen_Investor")
    ws2["A1"] = "RINGKASAN ANALITIK 100 DIGITAL TWIN INVESTOR PER SEGMEN"
    ws2["A1"].font = Font(name="Calibri", size=14, bold=True, color="1B365D")
    ws2["A2"] = f"Tanggal Simulasi: {datetime.now().strftime('%d %B %Y')} | Total Sampel: {len(df_inv)} Persona Digital Twin"
    ws2["A2"].font = Font(name="Calibri", size=10, italic=True, color="555555")

    seg_headers = [
        ("Kategori Investor", 28),
        ("Jumlah Twin", 13),
        ("Rata-rata Konviksi", 17),
        ("Avg Tek Edge", 13),
        ("Avg Moat IP", 13),
        ("Avg Pasar", 13),
        ("Avg Monetisasi", 14),
        ("Avg Risiko/Reg", 14),
        ("STRONG YES", 13),
        ("CONDITIONAL YES", 16),
        ("WAIT & SEE", 13),
        ("PASS", 11),
        ("Minat Utama (Top Product Fit)", 38),
    ]
    start_row = 4
    for c_idx, (h, w) in enumerate(seg_headers, 1):
        ws2.cell(row=start_row, column=c_idx, value=h)
        ws2.column_dimensions[get_column_letter(c_idx)].width = w
    style_header_row(ws2, start_row, len(seg_headers))

    for i, srow in df_seg.iterrows():
        er = start_row + 1 + i
        ws2.row_dimensions[er].height = 28
        vals = [
            srow["kategori_investor"], int(srow["jumlah"]), float(srow["avg_konviksi"]),
            float(srow["avg_tek"]), float(srow["avg_moat"]), float(srow["avg_pasar"]),
            float(srow["avg_monet"]), float(srow["avg_risiko"]),
            int(srow["strong_yes"]), int(srow["cond_yes"]), int(srow["wait_see"]), int(srow["pass_cnt"]),
            srow["top_product"]
        ]
        for c_idx, v in enumerate(vals, 1):
            cell = ws2.cell(row=er, column=c_idx, value=v)
            cell.border = cell_border
            cell.fill = zebra_fill if i % 2 == 1 else white_fill
            cell.font = Font(name="Calibri", size=10, bold=(c_idx == 1))
            if 2 <= c_idx <= 12:
                cell.alignment = Alignment(horizontal="center", vertical="center")
                if 3 <= c_idx <= 8:
                    cell.number_format = "0.00" if c_idx >= 4 else "0.0"
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)

    # Baris Total
    tot_row = start_row + 1 + len(df_seg)
    ws2.row_dimensions[tot_row].height = 26
    tot_vals = [
        "TOTAL / RATA-RATA KESELURUHAN",
        len(df_inv),
        round(df_inv["skor_konviksi_total"].mean(), 1),
        round(df_inv["skor_teknologi_edge"].mean(), 2),
        round(df_inv["skor_moat_ip"].mean(), 2),
        round(df_inv["skor_kebutuhan_pasar"].mean(), 2),
        round(df_inv["skor_kelayakan_monetisasi"].mean(), 2),
        round(df_inv["skor_kesiapan_regulasi_risiko"].mean(), 2),
        int((df_inv["keputusan_investasi"] == "STRONG YES").sum()),
        int((df_inv["keputusan_investasi"] == "CONDITIONAL YES").sum()),
        int((df_inv["keputusan_investasi"] == "WAIT & SEE").sum()),
        int((df_inv["keputusan_investasi"] == "PASS").sum()),
        df_inv["produk_paling_diminati"].mode()[0],
    ]
    for c_idx, v in enumerate(tot_vals, 1):
        cell = ws2.cell(row=tot_row, column=c_idx, value=v)
        cell.border = cell_border
        cell.fill = PatternFill("solid", fgColor="E9ECEF")
        cell.font = Font(name="Calibri", size=10, bold=True)
        cell.alignment = Alignment(horizontal="center" if 2 <= c_idx <= 12 else "left", vertical="center", wrap_text=True)

    # Tabel Distribusi Keputusan & Produk
    dec_start = tot_row + 3
    ws2.cell(row=dec_start, column=1, value="DISTRIBUSI KEPUTUSAN INVESTASI (N=100)").font = Font(name="Calibri", size=12, bold=True, color="1B365D")
    for c_idx, h in enumerate(["Keputusan Investasi", "Jumlah Investor", "Persentase (%)"], 1):
        ws2.cell(row=dec_start + 1, column=c_idx, value=h)
    style_header_row(ws2, dec_start + 1, 3)

    for i, drow in df_dec.iterrows():
        er = dec_start + 2 + i
        for c_idx, v in enumerate([drow["keputusan"], int(drow["jumlah"]), float(drow["persen"])], 1):
            cell = ws2.cell(row=er, column=c_idx, value=v)
            cell.border = cell_border
            cell.font = Font(name="Calibri", size=10, bold=(c_idx == 1))
            cell.alignment = Alignment(horizontal="center" if c_idx > 1 else "left", vertical="center")
            if c_idx == 1 and v in decision_styles:
                cell.fill, cell.font = decision_styles[v]
            if c_idx == 3:
                cell.number_format = "0.0%"

    prod_start = dec_start
    ws2.cell(row=prod_start, column=5, value="PERINGKAT MINAT PRODUK LENSETEK (N=100)").font = Font(name="Calibri", size=12, bold=True, color="1B365D")
    for idx_off, h in enumerate(["Produk Paling Diminati", "Jumlah Investor", "Persentase (%)"]):
        ws2.cell(row=prod_start + 1, column=5 + idx_off, value=h)
    # Style subset columns 5-7
    for c_idx in range(5, 8):
        c = ws2.cell(row=prod_start + 1, column=c_idx)
        c.fill = PatternFill("solid", fgColor="1B365D")
        c.font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        c.alignment = Alignment(horizontal="center", vertical="center")

    for i, prow in df_prod.iterrows():
        er = prod_start + 2 + i
        for idx_off, v in enumerate([prow["produk"], int(prow["jumlah"]), float(prow["persen"])]):
            cell = ws2.cell(row=er, column=5 + idx_off, value=v)
            cell.border = cell_border
            cell.font = Font(name="Calibri", size=10)
            cell.alignment = Alignment(horizontal="center" if idx_off > 0 else "left", vertical="center", wrap_text=True)
            if idx_off == 2:
                cell.number_format = "0.0%"

    # --------------------------------------------------------------------------
    # SHEET 3: Pre_Mortem_&_Solusi_Plan
    # --------------------------------------------------------------------------
    ws3 = wb.create_sheet("Pre_Mortem_&_Solusi_Plan")
    cols_s3 = [
        ("id", "ID", 9),
        ("judul", "Skenario Kegagalan Pre-Mortem", 34),
        ("kategori", "Kategori", 24),
        ("tingkat_risiko", "Tingkat Risiko", 15),
        ("severity", "Severity (1-5)", 13),
        ("probability", "Probabilitas (1-5)", 15),
        ("rpn", "Skor RPN (SxP)", 14),
        ("diagnosis_akar_masalah", "Diagnosis Akar Masalah (Audit Plan & Codebase)", 50),
        ("dampak_jika_terjadi", "Dampak Bisnis & Investor Jika Gagal", 40),
        ("solusi_konkret", "Solusi Rekayasa & Komersial Konkret", 55),
    ]
    for c_idx, (_, title, width) in enumerate(cols_s3, 1):
        ws3.cell(row=1, column=c_idx, value=title)
        ws3.column_dimensions[get_column_letter(c_idx)].width = width
    style_header_row(ws3, 1, len(cols_s3))

    for idx, pm in enumerate(PRE_MORTEM_SCENARIOS):
        er = idx + 2
        ws3.row_dimensions[er].height = 95
        row_fill = zebra_fill if idx % 2 == 1 else white_fill
        for c_idx, (key, _, _) in enumerate(cols_s3, 1):
            val = pm[key]
            cell = ws3.cell(row=er, column=c_idx, value=val)
            cell.border = cell_border
            cell.fill = row_fill
            cell.font = Font(name="Calibri", size=10)
            if key in ("id", "severity", "probability", "rpn"):
                cell.alignment = Alignment(horizontal="center", vertical="center")
                cell.font = Font(name="Calibri", size=10, bold=True)
            elif key == "tingkat_risiko":
                cell.alignment = Alignment(horizontal="center", vertical="center")
                fill_r, font_r = risk_styles.get(val, (row_fill, Font("Calibri", 10, bold=True)))
                cell.fill = fill_r
                cell.font = font_r
            elif key == "judul":
                cell.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
                cell.font = Font(name="Calibri", size=10, bold=True)
            else:
                cell.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)

    ws3.freeze_panes = "C2"
    ws3.auto_filter.ref = f"A1:{get_column_letter(len(cols_s3))}{len(PRE_MORTEM_SCENARIOS) + 1}"

    # --------------------------------------------------------------------------
    # SHEET 4: Evaluasi_8_Dimensi_Plan
    # --------------------------------------------------------------------------
    ws4 = wb.create_sheet("Evaluasi_8_Dimensi_Plan")
    cols_s4 = [
        ("dimensi", "Dimensi Evaluasi Plan Edge AI Agent", 36),
        ("skor_sekarang", "Skor Saat Ini (1-5)", 18),
        ("skor_target_pasca_fix", "Target Pasca-Fix (1-5)", 20),
        ("status", "Status Kesiapan", 26),
        ("audit_fakta_codebase", "Temuan Audit Fakta (Plan & Codebase)", 55),
        ("rekomendasi_perbaikan", "Langkah Perbaikan Wajib", 55),
    ]
    for c_idx, (_, title, width) in enumerate(cols_s4, 1):
        ws4.cell(row=1, column=c_idx, value=title)
        ws4.column_dimensions[get_column_letter(c_idx)].width = width
    style_header_row(ws4, 1, len(cols_s4))

    for idx, ev in enumerate(EVALUATION_8_DIMENSIONS):
        er = idx + 2
        ws4.row_dimensions[er].height = 80
        row_fill = zebra_fill if idx % 2 == 1 else white_fill
        for c_idx, (key, _, _) in enumerate(cols_s4, 1):
            val = ev[key]
            cell = ws4.cell(row=er, column=c_idx, value=val)
            cell.border = cell_border
            cell.fill = row_fill
            cell.font = Font(name="Calibri", size=10, bold=(c_idx in (1, 4)))
            if key in ("skor_sekarang", "skor_target_pasca_fix"):
                cell.alignment = Alignment(horizontal="center", vertical="center")
                cell.number_format = "0.0"
                cell.font = Font(name="Calibri", size=11, bold=True)
            else:
                cell.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)

    # Rata-rata skor
    avg_r = len(EVALUATION_8_DIMENSIONS) + 2
    ws4.row_dimensions[avg_r].height = 28
    avg_now = round(sum(e["skor_sekarang"] for e in EVALUATION_8_DIMENSIONS) / len(EVALUATION_8_DIMENSIONS), 2)
    avg_tgt = round(sum(e["skor_target_pasca_fix"] for e in EVALUATION_8_DIMENSIONS) / len(EVALUATION_8_DIMENSIONS), 2)
    for c_idx, val in enumerate(["RATA-RATA SKOR KESIAPAN PLAN", avg_now, avg_tgt, f"Kenaikan: +{avg_tgt - avg_now:.2f} Poin", "Kesiapan sebelum fix tertahan oleh PM-01 & PM-02", "Eksekusi perbaikan 7 hari menaikkan kesiapan ke level Investment-Ready"], 1):
        cell = ws4.cell(row=avg_r, column=c_idx, value=val)
        cell.border = cell_border
        cell.fill = PatternFill("solid", fgColor="E9ECEF")
        cell.font = Font(name="Calibri", size=10, bold=True)
        cell.alignment = Alignment(horizontal="center" if c_idx in (2, 3) else "left", vertical="center", wrap_text=True)

    wb.save(EXCEL_PATH)
    print(f"[OK] Excel workbook saved: {EXCEL_PATH}")


# ==============================================================================
# WORD BUILDER (PYTHON-DOCX)
# ==============================================================================
def set_cell_shading(cell, color_hex):
    shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color_hex}"/>')
    cell._tc.get_or_add_tcPr().append(shading)


def set_cell_margins(cell, top=80, bottom=80, left=120, right=120):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement("w:tcMar")
    for m, val in [("top", top), ("bottom", bottom), ("left", left), ("right", right)]:
        node = OxmlElement(f"w:{m}")
        node.set(qn("w:w"), str(val))
        node.set(qn("w:type"), "dxa")
        tcMar.append(node)
    tcPr.append(tcMar)


def set_table_borders(table, color="D0D7DE"):
    tblPr = table._tbl.tblPr
    borders = parse_xml(
        f'<w:tblBorders {nsdecls("w")}>'
        f'<w:top w:val="single" w:sz="6" w:space="0" w:color="{color}"/>'
        f'<w:bottom w:val="single" w:sz="6" w:space="0" w:color="{color}"/>'
        f'<w:insideH w:val="single" w:sz="4" w:space="0" w:color="{color}"/>'
        f'<w:left w:val="none"/>'
        f'<w:right w:val="none"/>'
        f'<w:insideV w:val="single" w:sz="4" w:space="0" w:color="E8ECEF"/>'
        f'</w:tblBorders>'
    )
    tblPr.append(borders)


def format_row_prevent_split(row, is_header=False):
    trPr = row._tr.get_or_add_trPr()
    trPr.append(OxmlElement("w:cantSplit"))
    if is_header:
        trPr.append(OxmlElement("w:tblHeader"))


def add_callout_box(doc, title, body_lines, bg_hex="EEF4FA", border_hex="1B365D"):
    p = doc.add_paragraph()
    pPr = p._p.get_or_add_pPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{bg_hex}"/>')
    pBdr = parse_xml(
        f'<w:pBdr {nsdecls("w")}>'
        f'<w:left w:val="single" w:sz="24" w:space="12" w:color="{border_hex}"/>'
        f'<w:top w:val="single" w:sz="4" w:space="6" w:color="D0D7DE"/>'
        f'<w:bottom w:val="single" w:sz="4" w:space="6" w:color="D0D7DE"/>'
        f'<w:right w:val="single" w:sz="4" w:space="12" w:color="D0D7DE"/>'
        f'</w:pBdr>'
    )
    pPr.append(shd)
    pPr.append(pBdr)
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(10)
    p.paragraph_format.left_indent = Inches(0.15)
    p.paragraph_format.right_indent = Inches(0.15)

    r_title = p.add_run(title + "\n")
    r_title.bold = True
    r_title.font.size = Pt(10.5)
    r_title.font.color.rgb = RGBColor(0x1B, 0x36, 0x5D)

    for idx, line in enumerate(body_lines):
        r = p.add_run(line + ("\n" if idx < len(body_lines) - 1 else ""))
        r.font.size = Pt(9.8)
        r.font.color.rgb = RGBColor(0x22, 0x22, 0x22)


def add_styled_table(doc, headers, rows_data, col_widths_in=None, font_size=9):
    table = doc.add_table(rows=1 + len(rows_data), cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(table)

    # Header
    hdr_row = table.rows[0]
    format_row_prevent_split(hdr_row, is_header=True)
    for c_idx, h_text in enumerate(headers):
        cell = hdr_row.cells[c_idx]
        set_cell_shading(cell, "1B365D")
        set_cell_margins(cell, 90, 90, 100, 100)
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        p = cell.paragraphs[0]
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER if c_idx > 0 else WD_ALIGN_PARAGRAPH.LEFT
        run = p.add_run(h_text)
        run.bold = True
        run.font.size = Pt(font_size)
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        if col_widths_in:
            cell.width = Inches(col_widths_in[c_idx])

    # Rows
    for r_idx, r_data in enumerate(rows_data):
        row = table.rows[r_idx + 1]
        format_row_prevent_split(row, is_header=False)
        bg = "F7F9FC" if r_idx % 2 == 1 else "FFFFFF"
        for c_idx, val in enumerate(r_data):
            cell = row.cells[c_idx]
            set_cell_shading(cell, bg)
            set_cell_margins(cell, 70, 70, 90, 90)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.TOP
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)
            run = p.add_run(str(val))
            run.font.size = Pt(font_size - 0.5 if font_size > 8 else font_size)
            run.font.color.rgb = RGBColor(0x1F, 0x23, 0x28)
            if c_idx == 0:
                run.bold = True
            if col_widths_in:
                cell.width = Inches(col_widths_in[c_idx])
    doc.add_paragraph().paragraph_format.space_after = Pt(4)
    return table


def build_docx(df_inv, df_seg, df_dec, df_prod):
    doc = Document()

    # Margins 0.75 in for spacious tables
    for section in doc.sections:
        section.top_margin = Inches(0.75)
        section.bottom_margin = Inches(0.75)
        section.left_margin = Inches(0.75)
        section.right_margin = Inches(0.75)

    normal_style = doc.styles["Normal"]
    normal_style.font.name = "Calibri"
    normal_style.font.size = Pt(10.5)
    normal_style.font.color.rgb = RGBColor(0x1F, 0x23, 0x28)

    for level, size, color in [
        ("Heading 1", 16, RGBColor(0x1B, 0x36, 0x5D)),
        ("Heading 2", 13, RGBColor(0x2B, 0x54, 0x7E)),
        ("Heading 3", 11, RGBColor(0x0F, 0x4C, 0x81)),
    ]:
        st = doc.styles[level]
        st.font.name = "Calibri"
        st.font.size = Pt(size)
        st.font.bold = True
        st.font.color.rgb = color

    # --------------------------------------------------------------------------
    # COVER / EXECUTIVE HEADER
    # --------------------------------------------------------------------------
    title_p = doc.add_paragraph()
    title_p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    title_p.paragraph_format.space_after = Pt(4)
    r_kicker = title_p.add_run("LENSETEK EDGE AI — AUDIT INVESTOR & KETAHANAN ARSITEKTUR\n")
    r_kicker.bold = True
    r_kicker.font.size = Pt(10)
    r_kicker.font.color.rgb = RGBColor(0x0D, 0x6E, 0xFD)

    r_main = title_p.add_run(
        "LAPORAN EVALUASI RENCANA EDGE AI AGENT, ANALISIS PRE-MORTEM & SOLUSI, "
        "SERTA SIMULASI DIGITAL TWIN 100 CALON INVESTOR STARTUP"
    )
    r_main.bold = True
    r_main.font.size = Pt(18)
    r_main.font.color.rgb = RGBColor(0x1B, 0x36, 0x5D)

    meta_p = doc.add_paragraph()
    meta_p.paragraph_format.space_after = Pt(12)
    meta_run = meta_p.add_run(
        f"Tanggal Laporan: {datetime.now().strftime('%d %B %Y')}  |  "
        "Cakupan Audit: plan_edge_ai_agent.md, app.py, rag_engine.py, training/*, Model Cards HF  |  "
        "Sampel Simulasi: 100 Digital Twin Investor (VC, CVC, PE, Crowdfunding, Angel, Grant, Family Office)"
    )
    meta_run.italic = True
    meta_run.font.size = Pt(9.5)
    meta_run.font.color.rgb = RGBColor(0x55, 0x55, 0x55)

    # Ringkasan Eksekutif
    avg_now = round(sum(e["skor_sekarang"] for e in EVALUATION_8_DIMENSIONS) / len(EVALUATION_8_DIMENSIONS), 2)
    avg_tgt = round(sum(e["skor_target_pasca_fix"] for e in EVALUATION_8_DIMENSIONS) / len(EVALUATION_8_DIMENSIONS), 2)
    n_strong = int((df_inv["keputusan_investasi"] == "STRONG YES").sum())
    n_cond = int((df_inv["keputusan_investasi"] == "CONDITIONAL YES").sum())
    n_wait = int((df_inv["keputusan_investasi"] == "WAIT & SEE").sum())
    n_pass = int((df_inv["keputusan_investasi"] == "PASS").sum())
    avg_conv = round(df_inv["skor_konviksi_total"].mean(), 1)

    add_callout_box(
        doc,
        "RINGKASAN EKSEKUTIF & KESIMPULAN UTAMA",
        [
            f"1. Skor Kesiapan Plan Saat Ini: {avg_now}/5.00 (Target Pasca-Perbaikan Pre-Mortem: {avg_tgt}/5.00). Visi air-gapped Edge SLM <= 4 GB RAM dan tiga repositori Hugging Face sudah sangat solid, NAMUN ditemukan 2 cacat teknis kritis sebelum RunPod dijalankan: overfitting 17 template statis di training/dataset_generator.py (PM-01) dan ketidaksinkronan klaim arsitektur Inkling/GRPO dengan kode SFT Qwen2 standar di train_runpod.py (PM-02).",
            f"2. Hasil Simulasi 100 Digital Twin Investor (Konviksi Rata-rata: {avg_conv}/100): {n_strong} investor menyatakan STRONG YES, {n_cond} CONDITIONAL YES, {n_wait} WAIT & SEE, dan {n_pass} PASS (mayoritas PASS berasal dari Private Equity & VC Consumer karena ketidakcocokan mandat tahap awal).",
            "3. Kunci Konversi Investor: Sebagian besar 'CONDITIONAL YES' (terutama CVC Tambang, PKS Sawit, Klinik 3T, dan Global OSS VC) siap langsung masuk apabila 5 perbaikan prioritas dieksekusi: (a) Refaktor dataset parametrik + GRPO nyata, (b) Tambah flag KV cache '-ctk q4_0 -ctv q4_0' di app.py + target OS Linux Edge, (c) GBNF JSON Schema + Read-Only/HITL Safety Interlock, (d) Kamus sinonim/ONNX opsional di rag_engine.py, dan (e) Pemisahan lisensi Open-Core (COSS).",
        ],
    )

    # --------------------------------------------------------------------------
    # BAB 1: EVALUASI KOMPREHENSIF PLAN & AUDIT CODEBASE
    # --------------------------------------------------------------------------
    doc.add_heading("BAB 1. Evaluasi Komprehensif Plan Edge AI Agent & Audit Codebase", level=1)
    doc.add_paragraph(
        "Evaluasi dilakukan dengan menyilangkan dokumen perencanaan strategis (plan_edge_ai_agent.md dan Model Card Hugging Face) "
        "langsung terhadap implementasi kode aktual di repositori lokal: app.py (5.036 baris), rag_engine.py (401 baris), "
        "training/dataset_generator.py, dan training/train_runpod.py. Penilaian menggunakan skala Likert 1,0–5,0 pada 8 dimensi inti."
    )

    eval_rows = [
        [
            e["dimensi"],
            f"{e['skor_sekarang']:.1f}",
            f"{e['skor_target_pasca_fix']:.1f}",
            e["status"],
            e["audit_fakta_codebase"],
            e["rekomendasi_perbaikan"],
        ]
        for e in EVALUATION_8_DIMENSIONS
    ]
    eval_rows.append([
        "RATA-RATA SKOR KESELURUHAN",
        f"{avg_now:.2f}",
        f"{avg_tgt:.2f}",
        f"Potensi Naik +{avg_tgt - avg_now:.2f}",
        "Visi arsitektur & infrastruktur repositori kuat, namun tertahan oleh kesiapan data training & celah runtime.",
        "Selesaikan perbaikan PM-01 s/d PM-05 sebelum menyewa RunPod dan melakukan outreach investor."
    ])
    add_styled_table(
        doc,
        ["Dimensi Evaluasi", "Saat Ini", "Target", "Status", "Temuan Audit Codebase & Plan", "Rekomendasi Perbaikan"],
        eval_rows,
        col_widths_in=[1.2, 0.5, 0.5, 1.0, 2.0, 1.8],
        font_size=8.5,
    )

    # --------------------------------------------------------------------------
    # BAB 2: ANALISIS PRE-MORTEM & SOLUSI
    # --------------------------------------------------------------------------
    doc.add_heading("BAB 2. Analisis Pre-Mortem: 10 Skenario Kegagalan Fatal & Solusinya", level=1)
    doc.add_paragraph(
        "Metode Pre-Mortem mengasumsikan bahwa 12 bulan dari sekarang proyek ini gagal mencapai adopsi komersial maupun pendanaan investor, "
        "lalu menelusuri akar penyebab teknis dan bisnis dari apa yang ada hari ini. Risk Priority Number (RPN) dihitung dari Severity (1–5) x Probability (1–5)."
    )

    pm_summary_rows = [
        [pm["id"], pm["judul"], pm["kategori"], pm["tingkat_risiko"], f"{pm['severity']} x {pm['probability']} = {pm['rpn']}"]
        for pm in PRE_MORTEM_SCENARIOS
    ]
    add_styled_table(
        doc,
        ["ID", "Skenario Kegagalan Fatal", "Kategori", "Tingkat Risiko", "Skor RPN (SxP)"],
        pm_summary_rows,
        col_widths_in=[0.6, 2.8, 1.4, 1.1, 1.1],
        font_size=8.8,
    )

    for pm in PRE_MORTEM_SCENARIOS:
        doc.add_heading(f"{pm['id']} [{pm['tingkat_risiko']} | RPN {pm['rpn']}]: {pm['judul']}", level=2)
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(6)
        for lbl, txt in [
            ("Kategori Risiko: ", pm["kategori"]),
            ("\nDiagnosis Akar Masalah: ", pm["diagnosis_akar_masalah"]),
            ("\nDampak Jika Terjadi: ", pm["dampak_jika_terjadi"]),
            ("\nSolusi Konkret (Teknis & Bisnis): ", pm["solusi_konkret"]),
        ]:
            r_b = p.add_run(lbl)
            r_b.bold = True
            r_b.font.size = Pt(9.8)
            r_t = p.add_run(txt)
            r_t.font.size = Pt(9.8)

    # --------------------------------------------------------------------------
    # BAB 3: METODOLOGI & STATISTIK AGREGAT DIGITAL TWIN 100 INVESTOR
    # --------------------------------------------------------------------------
    doc.add_page_break()
    doc.add_heading("BAB 3. Simulasi Digital Twin 100 Calon Investor: Metodologi & Hasil Agregat", level=1)
    doc.add_paragraph(
        "Mengikuti standar metodologi Synthetic Data Generator (Digital Twin Simulator), sebanyak 100 persona calon investor unik (INV-001 s/d INV-100) "
        "dikonstruksi mewakili 8 segmen modal utama startup global dan Indonesia: VC Regional (20), Global Deep-Tech & AI VC (15), Corporate Venture Capital / CVC (20), "
        "Private Equity / Growth Buyout (10), Crowdfunding & Hardware Syndicates (10), Super-Angel & AI Researcher (10), Sovereign/Defense/Disaster Grants (8), "
        "serta Family Office & ESG Impact (7). Setiap persona mengevaluasi rencana produk dan codebase aktual secara kritis dan konsisten dengan mandat dananya."
    )

    doc.add_heading("3.1 Ringkasan Evaluasi per Segmen Investor", level=2)
    seg_rows = [
        [
            r["kategori_investor"],
            int(r["jumlah"]),
            f"{r['avg_konviksi']:.1f}",
            f"{r['avg_tek']:.2f}",
            f"{r['avg_moat']:.2f}",
            f"{r['avg_pasar']:.2f}",
            f"{r['avg_monet']:.2f}",
            int(r["strong_yes"]),
            int(r["cond_yes"]),
            int(r["wait_see"]),
            int(r["pass_cnt"]),
        ]
        for _, r in df_seg.iterrows()
    ]
    seg_rows.append([
        "TOTAL / RATA-RATA (N=100)",
        100,
        f"{df_inv['skor_konviksi_total'].mean():.1f}",
        f"{df_inv['skor_teknologi_edge'].mean():.2f}",
        f"{df_inv['skor_moat_ip'].mean():.2f}",
        f"{df_inv['skor_kebutuhan_pasar'].mean():.2f}",
        f"{df_inv['skor_kelayakan_monetisasi'].mean():.2f}",
        n_strong, n_cond, n_wait, n_pass
    ])
    add_styled_table(
        doc,
        ["Segmen Investor", "N", "Konviksi", "Tek", "Moat", "Pasar", "Monet", "STRONG YES", "COND. YES", "WAIT", "PASS"],
        seg_rows,
        col_widths_in=[1.85, 0.35, 0.6, 0.45, 0.45, 0.45, 0.5, 0.65, 0.65, 0.5, 0.5],
        font_size=8.2,
    )

    doc.add_heading("3.2 Distribusi Keputusan & Produk Paling Diminati", level=2)
    dec_rows = [
        [r["keputusan"], int(r["jumlah"]), f"{r['persen']*100:.1f}%"]
        for _, r in df_dec.iterrows()
    ]
    add_styled_table(doc, ["Keputusan Investasi", "Jumlah Investor", "Persentase"], dec_rows, [2.6, 1.5, 1.5], font_size=9)

    prod_rows = [
        [r["produk"], int(r["jumlah"]), f"{r['persen']*100:.1f}%"]
        for _, r in df_prod.iterrows()
    ]
    add_styled_table(doc, ["Lini Produk Lensetek yang Paling Diminati", "Jumlah Investor", "Persentase"], prod_rows, [4.0, 1.5, 1.5], font_size=9)

    add_callout_box(
        doc,
        "INSIGHT UTAMA DARI DATA AGREGAT 100 DIGITAL TWIN",
        [
            f"• Skor rata-rata tertinggi ada pada Urgensi Pasar ({df_inv['skor_kebutuhan_pasar'].mean():.2f}/5.0) dan Teknologi Edge ({df_inv['skor_teknologi_edge'].mean():.2f}/5.0), membuktikan bahwa tesis 'Air-Gapped Edge AI < 4 GB RAM' memiliki product-market problem fit yang sangat kuat.",
            f"• Skor rata-rata terendah ada pada Moat IP ({df_inv['skor_moat_ip'].mean():.2f}/5.0) dan Regulasi/Risiko ({df_inv['skor_kesiapan_regulasi_risiko'].mean():.2f}/5.0), yang dipicu langsung oleh temuan Pre-Mortem PM-01 (dataset 17 template), PM-02 (Inkling vs Qwen2), PM-06 (safety medis/PLC), dan PM-07 (lisensi open-source).",
            f"• Segmen dengan minat tertinggi ('STRONG YES' & 'CONDITIONAL YES' terbanyak) berturut-turut adalah: Crowdfunding & Hardware Pre-Order, Corporate Venture Capital (CVC Sawit/Tambang/OEM), Super-Angel Teknis, serta Hibah Sovereign/Kebencanaan.",
            "• Segmen Private Equity (PE) secara konsisten memberikan status 'PASS' untuk ekuitas langsung (karena butuh EBITDA/ARR matang), namun 4 dari 10 PE bersedia menjadi pelanggan/lokasi uji coba berbayar bagi pabrik & RS portofolio mereka.",
        ],
    )

    # --------------------------------------------------------------------------
    # BAB 4: PROFIL LENGKAP & FEEDBACK 100 DIGITAL TWIN INVESTOR
    # --------------------------------------------------------------------------
    doc.add_page_break()
    doc.add_heading("BAB 4. Katalog Lengkap 100 Profil Digital Twin Investor & Verbatim Feedback", level=1)
    doc.add_paragraph(
        "Bagian ini memuat hasil simulasi lengkap seluruh 100 responden Digital Twin (INV-001 hingga INV-100) yang dikelompokkan ke dalam "
        "8 kategori investor. Tabel detail yang dapat difilter dan diurutkan juga tersedia pada workbook Excel pendamping."
    )

    segment_order = [
        "VC Regional (ID & SEA)",
        "Global Deep-Tech & AI VC",
        "Corporate Venture Capital (CVC)",
        "Private Equity (PE) & Infra",
        "Crowdfunding & Syndicates",
        "Super-Angel & AI Researcher",
        "Sovereign, Defense & Grants",
        "Family Office & ESG Impact",
    ]

    for seg_idx, seg_name in enumerate(segment_order, 1):
        sub_df = df_inv[df_inv["kategori_investor"] == seg_name]
        doc.add_heading(f"4.{seg_idx} Segmen: {seg_name} ({len(sub_df)} Digital Twins)", level=2)

        # Tabel ringkas per segmen
        t_rows = [
            [
                r["investor_id"],
                f"{r['nama_persona']}\n({r['institusi_archetype']})",
                f"{r['lokasi_region']}\n{r['estimasi_tiket_usd']}",
                f"Tek:{r['skor_teknologi_edge']} | Moat:{r['skor_moat_ip']} | Psr:{r['skor_kebutuhan_pasar']}\nMon:{r['skor_kelayakan_monetisasi']} | Rsk:{r['skor_kesiapan_regulasi_risiko']} | Tim:{r['skor_kualitas_tim_eksekusi']}",
                f"{r['keputusan_investasi']}\n({r['skor_konviksi_total']:.0f}/100 | {r['probabilitas_investasi_pct']}%)",
            ]
            for _, r in sub_df.iterrows()
        ]
        add_styled_table(
            doc,
            ["ID", "Persona & Archetype Institusi", "Region & Tiket", "Skor 6 Dimensi (1-5)", "Keputusan & Konviksi"],
            t_rows,
            col_widths_in=[0.65, 2.25, 1.35, 1.55, 1.2],
            font_size=8.0,
        )

        # Ulasan Verbatim & Syarat Deal per persona
        for _, r in sub_df.iterrows():
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(5)
            p.paragraph_format.left_indent = Inches(0.12)

            r_head = p.add_run(f"{r['investor_id']} — {r['nama_persona']} [{r['keputusan_investasi']}] | Minat: {r['produk_paling_diminati']}\n")
            r_head.bold = True
            r_head.font.size = Pt(9.2)
            r_head.font.color.rgb = RGBColor(0x1B, 0x36, 0x5D)

            r_rf_lbl = p.add_run("Red Flag: ")
            r_rf_lbl.bold = True
            r_rf_lbl.font.size = Pt(8.8)
            r_rf_txt = p.add_run(f"{r['red_flag_utama']}  ")
            r_rf_txt.font.size = Pt(8.8)

            r_sy_lbl = p.add_run("Syarat Deal: ")
            r_sy_lbl.bold = True
            r_sy_lbl.font.size = Pt(8.8)
            r_sy_txt = p.add_run(f"{r['syarat_kunci_deal']}\n")
            r_sy_txt.font.size = Pt(8.8)

            r_fb = p.add_run(f"\"{r['verbatim_feedback_persona']}\"")
            r_fb.italic = True
            r_fb.font.size = Pt(9.0)
            r_fb.font.color.rgb = RGBColor(0x33, 0x33, 0x33)

    # --------------------------------------------------------------------------
    # BAB 5: ROADMAP PERBAIKAN & FUNDRAISING PLAYBOOK
    # --------------------------------------------------------------------------
    doc.add_page_break()
    doc.add_heading("BAB 5. Roadmap Perbaikan Pra-RunPod & Strategi Urutan Pendekatan Investor", level=1)
    doc.add_paragraph(
        "Berdasarkan sintesis temuan 10 Pre-Mortem dan suara kolektif 100 Digital Twin Investor, tim disarankan mengeksekusi "
        "perbaikan teknis berbiaya nol dalam 7 hari sebelum menjalankan training RunPod maupun mengirim pitch deck."
    )

    playbook_rows = [
        [
            "Hari 1–2 (Pra-RunPod)",
            "Refaktor training/dataset_generator.py menjadi Parametric Combinatorial Generator (hilangkan duplikasi 17 template) + ubah format tool ke tag native <tool_call> Qwen2.5 + tambah data general 30%.",
            "Menghilangkan risiko PM-01 & PM-07; mencegah pemborosan biaya RunPod."
        ],
        [
            "Hari 3–4 (Training & Eval)",
            "Tambah skrip training/train_grpo_rlvr.py dengan reward +1.0/+0.8/-2.0, eksekusi RunPod RTX 4090 (~$1-$2), ekspor imatrix GGUF Q4_K_M, lalu jalankan 500 soal uji held-out.",
            "Membuka kunci konversi Angel Teknis & Global AI VC (PM-02 & PM-04)."
        ],
        [
            "Hari 5–6 (Runtime & Safety)",
            "Patch app.py baris 256 untuk menyertakan '-ctk q4_0 -ctv q4_0 -fa on' & dukungan Linux, aktifkan GBNF JSON constraint, kamus sinonim di rag_engine.py, serta Read-Only + HITL Safety Gate.",
            "Memenuhi syarat RAM <= 4 GB Linux/Mini PC & audit keselamatan CVC (PM-03, PM-05, PM-06)."
        ],
        [
            "Hari 7 (Lisensi & Kemasan)",
            "Terapkan pemisahan Open-Core (Model/Studio Apache-2.0 vs Enterprise Connectors/Fleet Commercial License) + siapkan image SD/SSD 'Lensetek ARK Box'.",
            "Membuka jalur monetisasi cepat via Crowdfunding ARK Box & Enterprise PoC (PM-07, PM-09)."
        ],
    ]
    add_styled_table(
        doc,
        ["Tahapan", "Aksi Rekayasa & Produk Prioritas", "Dampak pada Investor"],
        playbook_rows,
        col_widths_in=[1.3, 3.7, 2.0],
        font_size=9.0,
    )

    doc.add_heading("Urutan Prioritas Pendekatan Investor (Fundraising Sequencing Playbook)", level=2)
    seq_rows = [
        ["Gelombang 1 (Minggu 1–2)", "Super-Angels Teknis & Komunitas Homelab/Hugging Face", "$50K – $150K + Validasi GGUF", "Proses cepat berbasis pembuktian kode & skor eval GGUF; membuka referensi teknis untuk VC."],
        ["Gelombang 2 (Minggu 3–6)", "Crowdfunding Hardware/OS (Lensetek ARK) & Hibah Riset/Kebencanaan (LPDP/DFI)", "$100K – $300K Non-Dilutive + Cashflow Awal", "Menciptakan traksi pengguna & pendapatan riil dalam 45 hari tanpa dilusi saham berlebih."],
        ["Gelombang 3 (Bulan 2–3)", "Strategic CVC (PKS Sawit, Alat Berat Tambang, ODM Mini-PC, RS/Klinik) & Industrial FO", "Paid PoC ($2.5K-$5K/site) + Seed ($300K-$1M)", "Mengubah PoC berbayar menjadi kontrak ARR multi-tahun & jalur distribusi pabrik/klinik."],
        ["Gelombang 4 (Bulan 4–6)", "Regional B2B VC (ID/SEA) & Global Deep-Tech / OSS VC", "Institutional Seed ($750K – $2.5M)", "Dengan bukti ARR dari Gelombang 2-3 dan flywheel data nyata, valuasi putaran Seed melonjak signifikan."],
        ["Gelombang 5 (Tahun 2+)", "Private Equity (PE) & Late Growth Equity", "Vendor Kontrak Portofolio Sekarang; Ekuitas Saat ARR > $5M", "Untuk saat ini gunakan jaringan PE hanya sebagai pintu masuk menjual software ke pabrik/RS portofolio mereka."],
    ]
    add_styled_table(
        doc,
        ["Gelombang", "Target Investor", "Target Pendanaan / Hasil", "Alasan Strategis"],
        seq_rows,
        col_widths_in=[1.2, 1.8, 1.5, 2.5],
        font_size=8.8,
    )

    doc.save(DOCX_PATH)
    print(f"[OK] Word report saved: {DOCX_PATH}")


# ==============================================================================
# MAIN PIPELINE
# ==============================================================================
def main():
    os.makedirs(REPORT_DIR, exist_ok=True)
    df_inv = pd.DataFrame(ALL_INVESTORS)

    # Save raw structured data
    df_inv.to_csv(CSV_PATH, index=False, encoding="utf-8-sig")
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(ALL_INVESTORS, f, ensure_ascii=False, indent=2)

    # Segment aggregation
    segment_order = [
        "VC Regional (ID & SEA)",
        "Global Deep-Tech & AI VC",
        "Corporate Venture Capital (CVC)",
        "Private Equity (PE) & Infra",
        "Crowdfunding & Syndicates",
        "Super-Angel & AI Researcher",
        "Sovereign, Defense & Grants",
        "Family Office & ESG Impact",
    ]

    seg_records = []
    for seg in segment_order:
        sub = df_inv[df_inv["kategori_investor"] == seg]
        seg_records.append({
            "kategori_investor": seg,
            "jumlah": len(sub),
            "avg_konviksi": round(sub["skor_konviksi_total"].mean(), 1),
            "avg_tek": round(sub["skor_teknologi_edge"].mean(), 2),
            "avg_moat": round(sub["skor_moat_ip"].mean(), 2),
            "avg_pasar": round(sub["skor_kebutuhan_pasar"].mean(), 2),
            "avg_monet": round(sub["skor_kelayakan_monetisasi"].mean(), 2),
            "avg_risiko": round(sub["skor_kesiapan_regulasi_risiko"].mean(), 2),
            "strong_yes": int((sub["keputusan_investasi"] == "STRONG YES").sum()),
            "cond_yes": int((sub["keputusan_investasi"] == "CONDITIONAL YES").sum()),
            "wait_see": int((sub["keputusan_investasi"] == "WAIT & SEE").sum()),
            "pass_cnt": int((sub["keputusan_investasi"] == "PASS").sum()),
            "top_product": sub["produk_paling_diminati"].mode()[0],
        })
    df_seg = pd.DataFrame(seg_records)

    dec_order = ["STRONG YES", "CONDITIONAL YES", "WAIT & SEE", "PASS"]
    dec_counts = Counter(df_inv["keputusan_investasi"])
    df_dec = pd.DataFrame([
        {"keputusan": d, "jumlah": dec_counts.get(d, 0), "persen": dec_counts.get(d, 0) / len(df_inv)}
        for d in dec_order
    ])

    prod_counts = Counter(df_inv["produk_paling_diminati"])
    df_prod = pd.DataFrame([
        {"produk": k, "jumlah": v, "persen": v / len(df_inv)}
        for k, v in prod_counts.most_common()
    ])

    build_excel(df_inv, df_seg, df_dec, df_prod)
    build_docx(df_inv, df_seg, df_dec, df_prod)

    print("\n=== STATISTIK SIMULASI 100 DIGITAL TWIN ===")
    print(df_dec.to_string(index=False))
    print("\n=== PER SEGMEN ===")
    print(df_seg[["kategori_investor", "jumlah", "avg_konviksi", "strong_yes", "cond_yes", "wait_see", "pass_cnt"]].to_string(index=False))


if __name__ == "__main__":
    main()
