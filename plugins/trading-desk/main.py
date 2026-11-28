"""
Entry point for Lensetek Trading Desk Plugin.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

_PLUGIN_DIR = Path(__file__).resolve().parent
if str(_PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_DIR))

import trading_engine

_CTX: Dict[str, Any] = {}


def on_load(context: Dict[str, Any]):
    global _CTX
    _CTX = context or {}


def _get_ws() -> Path:
    ws = _CTX.get("workspace")
    return Path(ws).resolve() if ws else Path.cwd().resolve()


def _tool_get_analysis(args: Dict[str, Any]) -> str:
    sym = str(args.get("symbol", "")).strip()
    iv = str(args.get("interval", "1d")).strip()
    if not sym:
        return "Error: symbol is required."
    try:
        res = trading_engine.fetch_market_analysis(sym, interval=iv)
        ind = res["indicators"]
        summary = {
            "symbol": res["symbol"],
            "source": res["source"],
            "currency": res["currency"],
            "last_price": ind["last_price"],
            "change_pct": ind["change_pct"],
            "ema20": ind["last_ema20"],
            "ema50": ind["last_ema50"],
            "rsi14": ind["last_rsi14"],
            "macd": ind["last_macd"],
            "macd_signal": ind["last_macd_signal"],
            "support_20": ind["support_20"],
            "resistance_20": ind["resistance_20"],
            "trend_signal": ind["trend_signal"],
        }
        return json.dumps(summary, indent=2)
    except Exception as exc:
        return f"Error fetching market data: {exc}"


def _tool_list_journal(_args: Dict[str, Any]) -> str:
    return json.dumps(trading_engine.list_trades(_get_ws()), indent=2)


def register_tools() -> List[Dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "trading_get_analysis",
                "description": "Fetch live OHLCV market data and compute real EMA20/50, RSI14, MACD, Support/Resistance for Stocks (BBCA.JK, AAPL), Crypto (BTCUSDT), Forex (EURUSD=X), or Commodities (GC=F).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "description": "Ticker symbol e.g. BTCUSDT, BBCA.JK, AAPL, GC=F"},
                        "interval": {"type": "string", "description": "15m, 1h, 1d, 1wk"},
                    },
                    "required": ["symbol"],
                },
            },
            "handler": _tool_get_analysis,
        },
        {
            "type": "function",
            "function": {
                "name": "trading_list_journal",
                "description": "List recorded trades from the local SQLite trade journal.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
            "handler": _tool_list_journal,
        },
    ]
