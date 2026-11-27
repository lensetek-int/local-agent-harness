"""Validator ketat lintas 4 Expert, anti-kebocoran data klien, deduplikasi, dan merger JSONL."""

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from training.schemas import TOOL_DEFINITIONS

VALID_EXPERTS = {
    "expert_1_accounting",
    "expert_2_audit",
    "expert_3_tax_id",
    "expert_4_agentic",
}
VALID_TOOL_NAMES = {t["name"] for t in TOOL_DEFINITIONS}
FORBIDDEN_CLIENT_TOKENS = ("seruyan", "perumdam seruyan")


def validate_record(expert_name: str, record: dict[str, Any]) -> tuple[bool, str]:
    """Memvalidasi 1 baris ChatML JSONL sesuai kontrak ketat masing-masing expert."""
    raw_dump = json.dumps(record, ensure_ascii=False).lower()
    for token in FORBIDDEN_CLIENT_TOKENS:
        if token in raw_dump:
            return False, f"Terdeteksi potensi kebocoran nama klien asli ('{token}')"

    msgs = record.get("messages")
    if not isinstance(msgs, list) or len(msgs) < 3:
        return False, "Struktur messages tidak lengkap"

    roles = [m.get("role") for m in msgs]
    if roles[-2:] != ["user", "assistant"]:
        return False, "Urutan role harus diakhiri user -> assistant"

    user_content = msgs[-2].get("content", "")
    assistant_raw = msgs[-1].get("content", "")
    if not isinstance(user_content, str) or not user_content.strip():
        return False, "Prompt user kosong"

    try:
        parsed = json.loads(assistant_raw)
    except Exception as exc:
        return False, f"Assistant bukan JSON valid: {exc}"

    if not isinstance(parsed, dict):
        return False, "JSON assistant harus berupa object"

    if expert_name == "expert_1_accounting":
        lines = parsed.get("lines")
        if not isinstance(lines, list) or len(lines) < 2:
            return False, "Field 'lines' minimal 2 baris"
        try:
            d = sum(int(line.get("debit", 0)) for line in lines)
            c = sum(int(line.get("credit", 0)) for line in lines)
        except (TypeError, ValueError):
            return False, "Nominal debit/credit harus integer"
        if d != c or d <= 0:
            return False, f"Jurnal tidak seimbang: debit={d}, credit={c}"

    elif expert_name == "expert_2_audit":
        if "metrik" not in parsed:
            return False, "Expert 2 wajib memiliki field 'metrik'"
        if not any(isinstance(v, (int, float)) for v in parsed.values()):
            return False, "Expert 2 wajib memuat angka hasil perhitungan"

    elif expert_name == "expert_3_tax_id":
        if "jenis_pajak" not in parsed and "laba_fiskal" not in parsed and "jenis_analisis" not in parsed:
            return False, "Expert 3 wajib memuat klasifikasi pajak / rekonsiliasi fiskal / ekualisasi"
        for k in ("ppn_terutang", "pajak_terutang", "pph21_terutang", "pph_badan_terutang"):
            if k in parsed and (not isinstance(parsed[k], int) or parsed[k] < 0):
                return False, f"Nilai {k} harus integer >= 0"

    elif expert_name == "expert_4_agentic":
        calls = parsed.get("tool_calls")
        if not isinstance(calls, list) or not calls:
            return False, "Field 'tool_calls' tidak valid"
        for tc in calls:
            name = tc.get("name")
            if name not in VALID_TOOL_NAMES:
                return False, f"Nama tool tidak dikenal: {name}"
            args = tc.get("arguments")
            if not isinstance(args, dict):
                return False, f"Arguments tool '{name}' harus object"
            if name == "write_excel_preserving_template":
                if args.get("template_path") == args.get("output_path"):
                    return False, "output_path tidak boleh menimpa template_path"
            if name == "run_sqlite_query":
                sql_upper = str(args.get("sql", "")).strip().upper()
                if not sql_upper.startswith("SELECT "):
                    return False, "run_sqlite_query hanya boleh SELECT read-only"

    return True, "ok"


def validate_and_merge(
    expert_name: str,
    input_files: list[Path],
    output_file: Path,
) -> dict[str, int]:
    """Memvalidasi, mendeduplikasi, dan menggabungkan file JSONL ke output_file."""
    if expert_name not in VALID_EXPERTS:
        raise ValueError(f"Expert tidak dikenal: {expert_name}")

    seen_prompts: set[str] = set()
    accepted: list[str] = []
    stats = {"total_lines": 0, "valid": 0, "rejected": 0, "duplicates_skipped": 0}

    for path in input_files:
        if not path.exists():
            raise FileNotFoundError(f"File input tidak ditemukan: {path}")
        for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = raw.strip()
            if not stripped:
                continue
            stats["total_lines"] += 1
            try:
                obj = json.loads(stripped)
            except Exception as exc:
                stats["rejected"] += 1
                print(f"[REJECT] {path.name}:{line_no} JSON parse error: {exc}")
                continue

            ok, reason = validate_record(expert_name, obj)
            if not ok:
                stats["rejected"] += 1
                print(f"[REJECT] {path.name}:{line_no} {reason}")
                continue

            prompt_key = obj["messages"][-2]["content"].strip()
            if prompt_key in seen_prompts:
                stats["duplicates_skipped"] += 1
                continue
            seen_prompts.add(prompt_key)
            accepted.append(json.dumps(obj, ensure_ascii=False))
            stats["valid"] += 1

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text("\n".join(accepted) + ("\n" if accepted else ""), encoding="utf-8")
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Validator & Merger JSONL hasil Teacher Model")
    parser.add_argument("--expert", required=True, choices=sorted(VALID_EXPERTS))
    parser.add_argument("--inputs", nargs="+", required=True, help="Daftar file JSONL input")
    parser.add_argument("--output", required=True, help="Path file JSONL output gabungan")
    args = parser.parse_args()

    stats = validate_and_merge(
        expert_name=args.expert,
        input_files=[Path(p) for p in args.inputs],
        output_file=Path(args.output),
    )
    print("SUMMARY:", json.dumps(stats))


if __name__ == "__main__":
    main()
