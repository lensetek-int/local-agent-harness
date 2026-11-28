"""
Entry point for Lensetek Double-Entry Accounting & Ledger Plugin.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

_PLUGIN_DIR = Path(__file__).resolve().parent
if str(_PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_DIR))

import ledger_db

_CTX: Dict[str, Any] = {}


def on_load(context: Dict[str, Any]):
    global _CTX
    _CTX = context or {}


def _get_ws() -> Path:
    ws = _CTX.get("workspace")
    return Path(ws).resolve() if ws else Path.cwd().resolve()


def _tool_list_accounts(_args: Dict[str, Any]) -> str:
    return json.dumps(ledger_db.list_accounts(_get_ws()), indent=2, ensure_ascii=False)


def _tool_add_journal(args: Dict[str, Any]) -> str:
    try:
        res = ledger_db.create_journal_entry(
            _get_ws(),
            entry_date=str(args.get("entry_date", "")),
            description=str(args.get("description", "")),
            lines=args.get("lines", []),
            journal_type=str(args.get("journal_type", "general")),
            ref_no=str(args.get("ref_no", "")),
        )
        return json.dumps({"ok": True, "entry": res}, indent=2)
    except Exception as exc:
        return f"Error posting journal: {exc}"


def _tool_get_reports(_args: Dict[str, Any]) -> str:
    return json.dumps(ledger_db.get_financial_statements(_get_ws()), indent=2, ensure_ascii=False)


def register_tools() -> List[Dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "accounting_list_accounts",
                "description": "List Chart of Accounts (CoA) from the local SQLite accounting ledger.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
            "handler": _tool_list_accounts,
        },
        {
            "type": "function",
            "function": {
                "name": "accounting_add_journal",
                "description": "Post a balanced double-entry journal (Debit == Credit) to SQLite ledger.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "entry_date": {"type": "string", "description": "YYYY-MM-DD"},
                        "journal_type": {"type": "string", "description": "general, sales, purchase, cash_in, cash_out, adjusting"},
                        "ref_no": {"type": "string"},
                        "description": {"type": "string"},
                        "lines": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "account_code": {"type": "string"},
                                    "debit": {"type": "number"},
                                    "credit": {"type": "number"},
                                    "memo": {"type": "string"},
                                },
                                "required": ["account_code"],
                            },
                        },
                    },
                    "required": ["description", "lines"],
                },
            },
            "handler": _tool_add_journal,
        },
        {
            "type": "function",
            "function": {
                "name": "accounting_get_reports",
                "description": "Get real-time Trial Balance, Income Statement, and Balance Sheet from SQLite ledger.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
            "handler": _tool_get_reports,
        },
    ]
