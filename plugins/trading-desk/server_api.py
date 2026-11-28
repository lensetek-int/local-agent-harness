"""
WebUI HTTP API Router for Lensetek Trading Desk Plugin (/api/plugin/trading-desk/*).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Tuple

import trading_engine


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
        if sub in ("", "status"):
            return 200, {
                "watchlist": trading_engine.list_watchlist(ws),
                "trades": trading_engine.list_trades(ws),
            }

        if sub == "quote":
            sym = (query.get("symbol") or [""])[0].strip()
            iv = (query.get("interval") or ["1d"])[0].strip()
            rng = (query.get("range") or ["3mo"])[0].strip()
            if not sym:
                return 400, {"error": "Missing symbol"}
            try:
                data = trading_engine.fetch_market_analysis(sym, interval=iv, range_str=rng)
                return 200, {"ok": True, "market": data}
            except Exception as exc:
                return 400, {"ok": False, "error": str(exc)}

        return 404, {"error": f"Unknown GET endpoint: {sub}"}

    if method == "POST":
        if sub == "watchlist/add":
            try:
                wl = trading_engine.add_watchlist(ws, str(body.get("symbol", "")), str(body.get("label", "")))
                return 200, {"ok": True, "watchlist": wl}
            except Exception as exc:
                return 400, {"error": str(exc)}

        if sub == "watchlist/remove":
            wl = trading_engine.remove_watchlist(ws, str(body.get("symbol", "")))
            return 200, {"ok": True, "watchlist": wl}

        if sub == "trades/add":
            try:
                tr = trading_engine.add_trade(
                    ws,
                    symbol=str(body.get("symbol", "")),
                    side=str(body.get("side", "BUY")),
                    entry_price=float(body.get("entry_price", 0) or 0),
                    qty=float(body.get("qty", 0) or 0),
                    stop_loss=float(body.get("stop_loss", 0) or 0),
                    take_profit=float(body.get("take_profit", 0) or 0),
                    notes=str(body.get("notes", "")),
                )
                return 200, {"ok": True, "trade": tr, "trades": trading_engine.list_trades(ws)}
            except Exception as exc:
                return 400, {"error": str(exc)}

        if sub == "trades/close":
            tid = int(body.get("trade_id", 0) or 0)
            ex_p = float(body.get("exit_price", 0) or 0)
            ok = trading_engine.close_trade(ws, tid, ex_p)
            return 200, {"ok": ok, "trades": trading_engine.list_trades(ws)}

        if sub == "trades/delete":
            tid = int(body.get("trade_id", 0) or 0)
            ok = trading_engine.delete_trade(ws, tid)
            return 200, {"ok": ok, "trades": trading_engine.list_trades(ws)}

    return 404, {"error": f"Unknown endpoint: {method} {sub}"}
