"""
WebUI HTTP API Router for Lensetek Accounting & Ledger Plugin (/api/plugin/accounting-ledger/*).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Tuple

import ledger_db


def handle_request(
    method: str,
    sub_path: str,
    query: Dict[str, Any],
    body: Dict[str, Any],
    state: Any,
) -> Tuple[int, Dict[str, Any]]:
    ws = Path(state.workspace_root).resolve()
    sub = sub_path.strip("/").lower()

    if method == "GET":
        if sub in ("", "summary"):
            return 200, {
                "accounts": ledger_db.list_accounts(ws),
                "journals": ledger_db.list_journals(ws),
                "reports": ledger_db.get_financial_statements(ws),
            }

        if sub == "accounts":
            return 200, {"accounts": ledger_db.list_accounts(ws)}

        if sub == "journals":
            j_type = (query.get("type") or [""])[0].strip()
            return 200, {"journals": ledger_db.list_journals(ws, journal_type=j_type)}

        if sub == "ledger":
            code = (query.get("code") or [""])[0].strip()
            if not code:
                return 400, {"error": "Missing account code"}
            try:
                return 200, ledger_db.get_general_ledger(ws, code)
            except Exception as exc:
                return 404, {"error": str(exc)}

        if sub == "reports":
            return 200, {"reports": ledger_db.get_financial_statements(ws)}

        return 404, {"error": f"Unknown GET endpoint: {sub}"}

    if method == "POST":
        if sub == "accounts/add":
            try:
                acc = ledger_db.add_account(
                    ws,
                    code=str(body.get("code", "")),
                    name=str(body.get("name", "")),
                    acc_type=str(body.get("type", "")),
                )
                return 200, {"ok": True, "account": acc}
            except Exception as exc:
                return 400, {"error": str(exc)}

        if sub == "journals/add":
            try:
                entry = ledger_db.create_journal_entry(
                    ws,
                    entry_date=str(body.get("entry_date", "")),
                    description=str(body.get("description", "")),
                    lines=body.get("lines", []),
                    journal_type=str(body.get("journal_type", "general")),
                    ref_no=str(body.get("ref_no", "")),
                )
                return 200, {"ok": True, "entry": entry}
            except Exception as exc:
                return 400, {"error": str(exc)}

        if sub == "journals/delete":
            eid = int(body.get("entry_id", 0) or 0)
            ok = ledger_db.delete_journal_entry(ws, eid)
            return 200, {"ok": ok}

    return 404, {"error": f"Unknown endpoint: {method} {sub}"}
