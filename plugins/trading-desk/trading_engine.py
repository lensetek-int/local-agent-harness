"""
Real Market Data, Technical Indicator & SQLite Trade Journal Engine
for Lensetek Trading Desk Plugin. Zero dummy/mock prices.
"""

from __future__ import annotations

import json
import math
import sqlite3
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional


USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) LensetekTradingDesk/1.0"


def get_db_path(workspace_root: Path) -> Path:
    d = Path(workspace_root).resolve() / ".lensetek-trading"
    d.mkdir(parents=True, exist_ok=True)
    return d / "trading.db"


def get_conn(workspace_root: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(get_db_path(workspace_root)))
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS watchlist (
            symbol TEXT PRIMARY KEY,
            label TEXT DEFAULT '',
            added_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL CHECK(side IN ('BUY','SELL')),
            entry_price REAL NOT NULL,
            qty REAL NOT NULL,
            stop_loss REAL DEFAULT 0,
            take_profit REAL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'OPEN' CHECK(status IN ('OPEN','CLOSED')),
            exit_price REAL DEFAULT 0,
            notes TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            closed_at TEXT DEFAULT ''
        );
        """
    )
    conn.commit()
    return conn


def _is_crypto_pair(symbol: str) -> bool:
    s = symbol.strip().upper()
    return s.endswith(("USDT", "USDC", "BUSD", "BTC", "ETH")) and "." not in s and "=" not in s and "-" not in s


def _fetch_binance_klines(symbol: str, interval: str = "1d", limit: int = 120) -> Dict[str, Any]:
    s = symbol.strip().upper()
    iv_map = {"5m": "5m", "15m": "15m", "1h": "1h", "4h": "4h", "1d": "1d", "1wk": "1w"}
    b_iv = iv_map.get(interval, "1d")
    url = f"https://api.binance.com/api/v3/klines?symbol={urllib.parse.quote(s)}&interval={b_iv}&limit={limit}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=12) as resp:
        raw = json.loads(resp.read().decode("utf-8"))

    candles = []
    for row in raw:
        ts_sec = int(row[0] // 1000)
        candles.append({
            "time": time.strftime("%Y-%m-%d %H:%M" if b_iv in ("5m", "15m", "1h", "4h") else "%Y-%m-%d", time.localtime(ts_sec)),
            "open": float(row[1]),
            "high": float(row[2]),
            "low": float(row[3]),
            "close": float(row[4]),
            "volume": float(row[5]),
        })

    orderbook = {"bids": [], "asks": []}
    try:
        ob_url = f"https://api.binance.com/api/v3/depth?symbol={urllib.parse.quote(s)}&limit=8"
        ob_req = urllib.request.Request(ob_url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(ob_req, timeout=6) as ob_resp:
            ob_raw = json.loads(ob_resp.read().decode("utf-8"))
            orderbook["bids"] = [[float(p), float(q)] for p, q in ob_raw.get("bids", [])[:8]]
            orderbook["asks"] = [[float(p), float(q)] for p, q in ob_raw.get("asks", [])[:8]]
    except Exception:
        pass

    return {"symbol": s, "source": "Binance Spot", "currency": "USDT", "candles": candles, "orderbook": orderbook}


def _fetch_yahoo_chart(symbol: str, interval: str = "1d", range_str: str = "3mo") -> Dict[str, Any]:
    s = symbol.strip().upper()
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(s)}?interval={urllib.parse.quote(interval)}&range={urllib.parse.quote(range_str)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=12) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    chart = data.get("chart", {})
    if chart.get("error"):
        raise ValueError(chart["error"].get("description", "Yahoo Finance error"))
    res_list = chart.get("result") or []
    if not res_list:
        raise ValueError(f"No market data found for '{s}'.")

    res = res_list[0]
    meta = res.get("meta", {})
    timestamps = res.get("timestamp") or []
    quote = (res.get("indicators", {}).get("quote") or [{}])[0]
    opens = quote.get("open") or []
    highs = quote.get("high") or []
    lows = quote.get("low") or []
    closes = quote.get("close") or []
    vols = quote.get("volume") or []

    candles = []
    is_intra = interval in ("5m", "15m", "30m", "1h")
    for i, ts in enumerate(timestamps):
        o, h, l, c = opens[i], highs[i], lows[i], closes[i]
        if o is None or h is None or l is None or c is None:
            continue
        candles.append({
            "time": time.strftime("%Y-%m-%d %H:%M" if is_intra else "%Y-%m-%d", time.localtime(int(ts))),
            "open": round(float(o), 4),
            "high": round(float(h), 4),
            "low": round(float(l), 4),
            "close": round(float(c), 4),
            "volume": float(vols[i] or 0) if i < len(vols) else 0.0,
        })

    return {
        "symbol": meta.get("symbol", s),
        "source": "Yahoo Finance",
        "currency": meta.get("currency", ""),
        "candles": candles,
        "orderbook": None,
    }


def _calc_ema(values: List[float], period: int) -> List[Optional[float]]:
    if not values:
        return []
    k = 2.0 / (period + 1)
    out: List[Optional[float]] = []
    ema_val: Optional[float] = None
    for i, v in enumerate(values):
        if i + 1 < period:
            out.append(None)
        elif i + 1 == period:
            ema_val = sum(values[:period]) / period
            out.append(round(ema_val, 4))
        else:
            ema_val = v * k + (ema_val or v) * (1.0 - k)
            out.append(round(ema_val, 4))
    return out


def _calc_rsi(closes: List[float], period: int = 14) -> List[Optional[float]]:
    if len(closes) <= period:
        return [None] * len(closes)
    out: List[Optional[float]] = [None] * period
    gains, losses = [], []
    for i in range(1, period + 1):
        diff = closes[i] - closes[i - 1]
        gains.append(max(0.0, diff))
        losses.append(max(0.0, -diff))
    avg_g = sum(gains) / period
    avg_l = sum(losses) / period
    rs = (avg_g / avg_l) if avg_l > 0 else 100.0
    out.append(round(100.0 - (100.0 / (1.0 + rs)), 2) if avg_l > 0 else 100.0)

    for i in range(period + 1, len(closes)):
        diff = closes[i] - closes[i - 1]
        g = max(0.0, diff)
        l = max(0.0, -diff)
        avg_g = (avg_g * (period - 1) + g) / period
        avg_l = (avg_l * (period - 1) + l) / period
        if avg_l == 0:
            out.append(100.0)
        else:
            rs = avg_g / avg_l
            out.append(round(100.0 - (100.0 / (1.0 + rs)), 2))
    return out


def compute_indicators(candles: List[Dict[str, Any]]) -> Dict[str, Any]:
    closes = [float(c["close"]) for c in candles]
    highs = [float(c["high"]) for c in candles]
    lows = [float(c["low"]) for c in candles]
    if not closes:
        return {}

    ema20 = _calc_ema(closes, 20)
    ema50 = _calc_ema(closes, 50)
    rsi14 = _calc_rsi(closes, 14)

    # MACD (12, 26, 9)
    ema12 = _calc_ema(closes, 12)
    ema26 = _calc_ema(closes, 26)
    macd_line = [
        round(a - b, 4) if (a is not None and b is not None) else None
        for a, b in zip(ema12, ema26)
    ]
    valid_macd = [m for m in macd_line if m is not None]
    sig_raw = _calc_ema(valid_macd, 9) if len(valid_macd) >= 9 else []

    # Bollinger Bands (20, 2)
    bb_upper: List[Optional[float]] = []
    bb_lower: List[Optional[float]] = []
    for i in range(len(closes)):
        if i + 1 < 20:
            bb_upper.append(None)
            bb_lower.append(None)
        else:
            win = closes[i - 19 : i + 1]
            mean = sum(win) / 20.0
            std = math.sqrt(sum((x - mean) ** 2 for x in win) / 20.0)
            bb_upper.append(round(mean + 2 * std, 4))
            bb_lower.append(round(mean - 2 * std, 4))

    last_close = closes[-1]
    prev_close = closes[-2] if len(closes) >= 2 else last_close
    chg_pct = round(((last_close - prev_close) / prev_close) * 100, 2) if prev_close else 0.0
    last_ema20 = ema20[-1]
    last_ema50 = ema50[-1]
    last_rsi = rsi14[-1]

    signal = "NEUTRAL"
    if last_ema20 is not None and last_ema50 is not None:
        if last_close > last_ema20 > last_ema50:
            signal = "BULLISH"
        elif last_close < last_ema20 < last_ema50:
            signal = "BEARISH"

    recent_high = max(highs[-20:]) if len(highs) >= 20 else max(highs)
    recent_low = min(lows[-20:]) if len(lows) >= 20 else min(lows)

    return {
        "last_price": last_close,
        "change_pct": chg_pct,
        "ema20": ema20,
        "ema50": ema50,
        "bb_upper": bb_upper,
        "bb_lower": bb_lower,
        "last_ema20": last_ema20,
        "last_ema50": last_ema50,
        "last_rsi14": last_rsi,
        "last_macd": valid_macd[-1] if valid_macd else None,
        "last_macd_signal": sig_raw[-1] if sig_raw else None,
        "resistance_20": round(recent_high, 4),
        "support_20": round(recent_low, 4),
        "trend_signal": signal,
    }


def fetch_market_analysis(symbol: str, interval: str = "1d", range_str: str = "3mo") -> Dict[str, Any]:
    if _is_crypto_pair(symbol):
        res = _fetch_binance_klines(symbol, interval=interval, limit=120)
    else:
        res = _fetch_yahoo_chart(symbol, interval=interval, range_str=range_str)
    if not res["candles"]:
        raise ValueError(f"No candle data returned for {symbol}.")
    res["indicators"] = compute_indicators(res["candles"])
    return res


# Watchlist & SQLite Trade Journal
def list_watchlist(workspace_root: Path) -> List[Dict[str, Any]]:
    conn = get_conn(workspace_root)
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM watchlist ORDER BY added_at DESC").fetchall()]
    finally:
        conn.close()


def add_watchlist(workspace_root: Path, symbol: str, label: str = "") -> List[Dict[str, Any]]:
    s = symbol.strip().upper()
    if not s:
        raise ValueError("Symbol required")
    conn = get_conn(workspace_root)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO watchlist (symbol, label, added_at) VALUES (?, ?, ?)",
            (s, label.strip() or s, time.strftime("%Y-%m-%dT%H:%M:%S")),
        )
        conn.commit()
    finally:
        conn.close()
    return list_watchlist(workspace_root)


def remove_watchlist(workspace_root: Path, symbol: str) -> List[Dict[str, Any]]:
    conn = get_conn(workspace_root)
    try:
        conn.execute("DELETE FROM watchlist WHERE symbol = ?", (symbol.strip().upper(),))
        conn.commit()
    finally:
        conn.close()
    return list_watchlist(workspace_root)


def list_trades(workspace_root: Path) -> List[Dict[str, Any]]:
    conn = get_conn(workspace_root)
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM trades ORDER BY id DESC").fetchall()]
    finally:
        conn.close()


def add_trade(
    workspace_root: Path,
    symbol: str,
    side: str,
    entry_price: float,
    qty: float,
    stop_loss: float = 0.0,
    take_profit: float = 0.0,
    notes: str = "",
) -> Dict[str, Any]:
    s = symbol.strip().upper()
    sd = side.strip().upper()
    if sd not in ("BUY", "SELL"):
        raise ValueError("Side must be BUY or SELL")
    if entry_price <= 0 or qty <= 0:
        raise ValueError("Entry price and quantity must be > 0")
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%S")
    conn = get_conn(workspace_root)
    try:
        cur = conn.execute(
            "INSERT INTO trades (symbol, side, entry_price, qty, stop_loss, take_profit, status, notes, created_at) VALUES (?, ?, ?, ?, ?, ?, 'OPEN', ?, ?)",
            (s, sd, float(entry_price), float(qty), float(stop_loss), float(take_profit), notes.strip(), now_iso),
        )
        conn.commit()
        return {"id": cur.lastrowid, "symbol": s, "side": sd, "entry_price": entry_price}
    finally:
        conn.close()


def close_trade(workspace_root: Path, trade_id: int, exit_price: float) -> bool:
    conn = get_conn(workspace_root)
    try:
        cur = conn.execute(
            "UPDATE trades SET status = 'CLOSED', exit_price = ?, closed_at = ? WHERE id = ?",
            (float(exit_price), time.strftime("%Y-%m-%dT%H:%M:%S"), trade_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def delete_trade(workspace_root: Path, trade_id: int) -> bool:
    conn = get_conn(workspace_root)
    try:
        cur = conn.execute("DELETE FROM trades WHERE id = ?", (trade_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()
