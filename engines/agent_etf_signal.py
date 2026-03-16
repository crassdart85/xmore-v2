"""
engines/agent_etf_signal.py — ETF/ETP Technical Signal Generator
================================================================
Generates BUY/HOLD/SELL signals for EGX ETFs and ETPs using:
  - MA crossover (adaptive periods based on vol regime)
  - RSI (adaptive period based on vol regime)
  - NAV premium/discount signal (ETF-specific)
  - Momentum (5-day price change)

Signals are stored in `etf_signals` table and consumed by:
  - /api/etf/signals (Node.js route)
  - Pro page ETF signals panel
  - Track record ETF section
  - RAG assistant ETF context
"""

import logging
from datetime import date, datetime
from typing import Optional

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# ── Vol regime (same thresholds as stock agents) ─────────────────────────────

def _vol_regime(closes: pd.Series) -> str:
    if len(closes) < 20:
        return "normal"
    returns = closes.pct_change().replace([np.inf, -np.inf], np.nan).fillna(0)
    ewma_vol = returns.ewm(span=32, min_periods=10).std().iloc[-1]
    if ewma_vol < 0.015:
        return "low"
    if ewma_vol > 0.030:
        return "high"
    return "normal"

_MA_PERIODS  = {"low": (8, 20),  "normal": (10, 30), "high": (15, 40)}
_RSI_PERIODS = {"low": 10,       "normal": 14,        "high": 20}

# ── Indicators ────────────────────────────────────────────────────────────────

def _rsi(closes: pd.Series, period: int) -> float:
    if len(closes) < period + 1:
        return 50.0
    delta = closes.diff().dropna()
    gain  = delta.clip(lower=0).rolling(period).mean()
    loss  = (-delta.clip(upper=0)).rolling(period).mean()
    rs    = gain / loss.replace(0, np.nan)
    rsi   = (100 - 100 / (1 + rs)).iloc[-1]
    return float(rsi) if not np.isnan(rsi) else 50.0

def _ma_signal(closes: pd.Series, short_w: int, long_w: int) -> str:
    if len(closes) < long_w:
        return "HOLD"
    short_ma = closes.rolling(short_w).mean().iloc[-1]
    long_ma  = closes.rolling(long_w).mean().iloc[-1]
    if short_ma > long_ma * 1.005:
        return "UP"
    if short_ma < long_ma * 0.995:
        return "DOWN"
    return "HOLD"

def _rsi_signal(rsi_val: float) -> str:
    if rsi_val < 35:
        return "UP"    # oversold
    if rsi_val > 65:
        return "DOWN"  # overbought
    return "HOLD"

def _nav_signal(price: float, nav: float) -> str:
    """Negative premium (discount) -> UP; large premium -> DOWN."""
    if nav is None or nav <= 0:
        return "HOLD"
    premium_pct = (price - nav) / nav * 100
    if premium_pct < -2.0:
        return "UP"    # trading at >2% discount to NAV
    if premium_pct > 3.0:
        return "DOWN"  # trading at >3% premium to NAV
    return "HOLD"

def _momentum_signal(closes: pd.Series, days: int = 5) -> str:
    if len(closes) < days + 1:
        return "HOLD"
    change = (closes.iloc[-1] - closes.iloc[-days - 1]) / closes.iloc[-days - 1]
    if change > 0.015:
        return "UP"
    if change < -0.015:
        return "DOWN"
    return "HOLD"

# ── Consensus from sub-signals ────────────────────────────────────────────────

_SIGNAL_SCORE = {"UP": 1, "HOLD": 0, "DOWN": -1}

def _combine(signals: list, weights: list) -> tuple:
    """Weighted vote -> (signal, confidence 0-1)."""
    score = sum(_SIGNAL_SCORE[s] * w for s, w in zip(signals, weights))
    total_weight = sum(weights)
    norm  = score / total_weight
    confidence = abs(norm)
    if norm > 0.15:
        return "UP",   round(min(confidence, 1.0), 3)
    if norm < -0.15:
        return "DOWN", round(min(confidence, 1.0), 3)
    return "HOLD", round(confidence, 3)

# ── DB helpers ────────────────────────────────────────────────────────────────

def _is_postgres(conn) -> bool:
    module = getattr(type(conn), '__module__', '') or ''
    return 'psycopg2' in module

def _ph(n: int, pg: bool) -> str:
    return f'${n}' if pg else '?'

def _fetch_etf_prices(conn, instrument_id: int, pg: bool, limit: int = 80) -> pd.Series:
    """Return close prices for an ETF from etf_price_daily."""
    ph = _ph
    sql = (
        f"SELECT close_price FROM etf_price_daily "
        f"WHERE instrument_id = {ph(1, pg)} AND close_price IS NOT NULL "
        f"ORDER BY trade_date DESC LIMIT {ph(2, pg)}"
    )
    cur = conn.cursor()
    cur.execute(sql, (instrument_id, limit))
    rows = cur.fetchall()
    prices = [float(r[0]) for r in rows if r[0] is not None]
    prices.reverse()  # oldest first
    return pd.Series(prices, dtype=float)

def _fetch_latest_nav(conn, instrument_id: int, pg: bool) -> Optional[float]:
    ph = _ph
    sql = (
        f"SELECT nav_unit FROM etf_nav "
        f"WHERE instrument_id = {ph(1, pg)} AND nav_unit IS NOT NULL "
        f"ORDER BY nav_date DESC LIMIT 1"
    )
    cur = conn.cursor()
    try:
        cur.execute(sql, (instrument_id,))
        row = cur.fetchone()
        return float(row[0]) if row and row[0] else None
    except Exception:
        return None

def _ensure_table(conn, pg: bool):
    """Create etf_signals table if not exists."""
    cur = conn.cursor()
    if pg:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS etf_signals (
                id              BIGSERIAL PRIMARY KEY,
                instrument_id   BIGINT NOT NULL,
                symbol          TEXT   NOT NULL,
                signal_date     DATE   NOT NULL DEFAULT CURRENT_DATE,
                signal          TEXT   NOT NULL DEFAULT 'HOLD',
                confidence      NUMERIC(5,3) DEFAULT 0,
                ma_signal       TEXT,
                rsi_signal      TEXT,
                nav_signal      TEXT,
                momentum_signal TEXT,
                rsi_value       NUMERIC(6,2),
                nav_premium_pct NUMERIC(7,3),
                close_price     NUMERIC(14,4),
                notes           TEXT,
                created_at      TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE (instrument_id, signal_date)
            )
        """)
    else:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS etf_signals (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                instrument_id   INTEGER NOT NULL,
                symbol          TEXT    NOT NULL,
                signal_date     TEXT    NOT NULL,
                signal          TEXT    NOT NULL DEFAULT 'HOLD',
                confidence      REAL    DEFAULT 0,
                ma_signal       TEXT,
                rsi_signal      TEXT,
                nav_signal      TEXT,
                momentum_signal TEXT,
                rsi_value       REAL,
                nav_premium_pct REAL,
                close_price     REAL,
                notes           TEXT,
                created_at      TEXT    DEFAULT (datetime('now')),
                UNIQUE (instrument_id, signal_date)
            )
        """)
    conn.commit()

def _upsert_signal(conn, pg: bool, row: dict):
    ph = _ph
    today = date.today().isoformat()
    if pg:
        sql = f"""
            INSERT INTO etf_signals
                (instrument_id, symbol, signal_date, signal, confidence,
                 ma_signal, rsi_signal, nav_signal, momentum_signal,
                 rsi_value, nav_premium_pct, close_price, notes)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
            ON CONFLICT (instrument_id, signal_date)
            DO UPDATE SET
                signal=EXCLUDED.signal, confidence=EXCLUDED.confidence,
                ma_signal=EXCLUDED.ma_signal, rsi_signal=EXCLUDED.rsi_signal,
                nav_signal=EXCLUDED.nav_signal, momentum_signal=EXCLUDED.momentum_signal,
                rsi_value=EXCLUDED.rsi_value, nav_premium_pct=EXCLUDED.nav_premium_pct,
                close_price=EXCLUDED.close_price, notes=EXCLUDED.notes
        """
    else:
        sql = """
            INSERT OR REPLACE INTO etf_signals
                (instrument_id, symbol, signal_date, signal, confidence,
                 ma_signal, rsi_signal, nav_signal, momentum_signal,
                 rsi_value, nav_premium_pct, close_price, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """
    cur = conn.cursor()
    cur.execute(sql, (
        row['instrument_id'], row['symbol'], today,
        row['signal'], row['confidence'],
        row['ma_signal'], row['rsi_signal'], row['nav_signal'], row['momentum_signal'],
        row['rsi_value'], row['nav_premium_pct'], row['close_price'], row['notes']
    ))
    conn.commit()

# ── Main entry point ──────────────────────────────────────────────────────────

def run_etf_signals(conn) -> int:
    """
    Generate and store ETF signals for all active LOCAL_EGX instruments.
    Returns the number of signals generated.
    Call from run_agents.py after stock agents complete.
    """
    pg = _is_postgres(conn)
    _ensure_table(conn, pg)

    # Fetch all active instruments (LOCAL_EGX priority + GLOBAL)
    ph = _ph
    cur = conn.cursor()
    try:
        cur.execute(
            f"SELECT {ph(1, pg)} AS col",
            (1,)
        )
        # Just testing connectivity
    except Exception:
        pass

    try:
        if pg:
            cur.execute(
                "SELECT instrument_id, symbol, region FROM instrument "
                "WHERE is_active = TRUE ORDER BY region, symbol"
            )
        else:
            cur.execute(
                "SELECT id AS instrument_id, symbol, region FROM instrument "
                "WHERE is_active = 1 ORDER BY region, symbol"
            )
        instruments = cur.fetchall()
    except Exception as e:
        logger.error(f"[ETF signal] Could not fetch instruments: {e}")
        return 0

    if not instruments:
        logger.info("[ETF signal] No active instruments found -- skipping")
        return 0

    count = 0
    for row in instruments:
        instr_id = row[0]
        symbol   = row[1]
        region   = row[2] if len(row) > 2 else 'LOCAL_EGX'

        try:
            closes = _fetch_etf_prices(conn, instr_id, pg, limit=80)
            if len(closes) < 15:
                logger.info(f"[ETF signal] {symbol}: insufficient price history ({len(closes)} rows) -- HOLD")
                _upsert_signal(conn, pg, {
                    'instrument_id': instr_id, 'symbol': symbol,
                    'signal': 'HOLD', 'confidence': 0,
                    'ma_signal': 'HOLD', 'rsi_signal': 'HOLD',
                    'nav_signal': 'HOLD', 'momentum_signal': 'HOLD',
                    'rsi_value': 50.0, 'nav_premium_pct': None,
                    'close_price': float(closes.iloc[-1]) if len(closes) else None,
                    'notes': f'Insufficient data ({len(closes)} rows)'
                })
                count += 1
                continue

            regime   = _vol_regime(closes)
            short_w, long_w = _MA_PERIODS[regime]
            rsi_per  = _RSI_PERIODS[regime]

            ma_sig   = _ma_signal(closes, short_w, long_w)
            rsi_val  = _rsi(closes, rsi_per)
            rsi_sig  = _rsi_signal(rsi_val)
            mom_sig  = _momentum_signal(closes, days=5)

            latest_nav = _fetch_latest_nav(conn, instr_id, pg)
            latest_close = float(closes.iloc[-1])
            nav_premium = None
            if latest_nav and latest_nav > 0:
                nav_premium = round((latest_close - latest_nav) / latest_nav * 100, 3)
            nav_sig = _nav_signal(latest_close, latest_nav)

            # Weights: MA=3, RSI=2, NAV=3 (ETF-specific), Momentum=1
            nav_w = 3 if region == 'LOCAL_EGX' else 1  # NAV signal only reliable for local ETFs
            signal, conf = _combine(
                [ma_sig, rsi_sig, nav_sig, mom_sig],
                [3,      2,       nav_w,   1]
            )

            notes = f"Regime:{regime} MA({short_w}/{long_w}):{ma_sig} RSI({rsi_per}):{rsi_sig} NAV:{nav_sig} Mom:{mom_sig}"
            _upsert_signal(conn, pg, {
                'instrument_id': instr_id, 'symbol': symbol,
                'signal': signal, 'confidence': conf,
                'ma_signal': ma_sig, 'rsi_signal': rsi_sig,
                'nav_signal': nav_sig, 'momentum_signal': mom_sig,
                'rsi_value': round(rsi_val, 2), 'nav_premium_pct': nav_premium,
                'close_price': latest_close, 'notes': notes
            })
            count += 1
            logger.info(f"[ETF signal] {symbol}: {signal} (conf={conf:.2f}) {notes}")

        except Exception as e:
            logger.warning(f"[ETF signal] {symbol}: error -- {e}")
            continue

    logger.info(f"[ETF signal] Done -- {count} signals generated")
    return count


if __name__ == '__main__':
    import sqlite3, sys
    db_path = sys.argv[1] if len(sys.argv) > 1 else 'stocks.db'
    conn = sqlite3.connect(db_path)
    n = run_etf_signals(conn)
    print(f"Generated {n} ETF signals")
    conn.close()
