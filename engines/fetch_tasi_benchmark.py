"""
TASI Benchmark Fetcher
======================
Fetches Tadawul All Share Index (TASI) daily prices from EODHD and
upserts them into the prices table as symbol='TASI.INDX', market_id='KSA'.

Strategy (in order):
  1. EODHD  — TASI.INDX  (primary: EODHD index exchange)
  2. EODHD  — TASI.SR    (fallback: Saudi exchange code)
  3. Proxy  — equal-weight average of existing .SR prices already in DB
              (always succeeds once the KSA pipeline has run)

Run daily after prices update, before evaluate_performance.py.
"""

import os
import sys
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv('DATABASE_URL')
EODHD_KEY    = os.getenv('EODHD_API_KEY', '')

# Candidates in preference order — first that returns data wins
EODHD_TASI_CANDIDATES = ['TASI.INDX', 'TASI.SR']

# TASI base value used for the equal-weight proxy (approximate index level)
TASI_BASE = 12_000

# Minimum component stocks required to build a proxy
MIN_PROXY_COMPONENTS = 5

# KSA component symbols (subset of Tadawul universe — liquid names)
TASI_PROXY_SYMBOLS = [
    '2222.SR', '1180.SR', '1170.SR', '7010.SR', '2010.SR',
    '2020.SR', '1150.SR', '1060.SR', '4190.SR', '1050.SR',
    '4061.SR', '7020.SR', '2030.SR', '4031.SR', '8010.SR',
]


# ─── DB helpers ───────────────────────────────────────────────────────────────

def _get_db_conn():
    if DATABASE_URL:
        import psycopg2
        return psycopg2.connect(DATABASE_URL), True
    import sqlite3
    db_path = os.path.join(os.path.dirname(__file__), '..', 'xmore.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn, False


def _upsert_prices(rows: list[dict]) -> int:
    """Upsert TASI rows into the prices table. Returns count inserted/updated."""
    if not rows:
        return 0

    conn, is_pg = _get_db_conn()
    count = 0
    try:
        cur = conn.cursor()
        for row in rows:
            if is_pg:
                cur.execute("""
                    INSERT INTO prices (symbol, date, open, high, low, close, volume, market_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'KSA')
                    ON CONFLICT (symbol, date) DO UPDATE SET
                        open   = EXCLUDED.open,
                        high   = EXCLUDED.high,
                        low    = EXCLUDED.low,
                        close  = EXCLUDED.close,
                        volume = EXCLUDED.volume
                """, (
                    row['symbol'], row['date'],
                    row['open'], row['high'], row['low'], row['close'], row['volume'],
                ))
            else:
                cur.execute("""
                    INSERT OR REPLACE INTO prices (symbol, date, open, high, low, close, volume, market_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'KSA')
                """, (
                    row['symbol'], row['date'],
                    row['open'], row['high'], row['low'], row['close'], row['volume'],
                ))
            count += 1
        conn.commit()
    finally:
        conn.close()
    return count


def _fetch_existing_prices(symbols: list[str], start_date: str, end_date: str) -> dict:
    """Return {symbol: [{date, close}, ...]} from the prices table."""
    conn, is_pg = _get_db_conn()
    result: dict = {}
    try:
        cur = conn.cursor()
        ph = '%s' if is_pg else '?'
        placeholders = ', '.join([ph] * len(symbols))
        cur.execute(f"""
            SELECT symbol, date, close
            FROM prices
            WHERE symbol IN ({placeholders})
              AND market_id = 'KSA'
              AND CAST(date AS DATE) >= CAST({ph} AS DATE)
              AND CAST(date AS DATE) <= CAST({ph} AS DATE)
            ORDER BY symbol, CAST(date AS DATE) ASC
        """, (*symbols, start_date, end_date))
        for row in cur.fetchall():
            sym  = row[0] if is_pg else row['symbol']
            dt   = str(row[1] if is_pg else row['date'])[:10]
            cls  = float(row[2] if is_pg else row['close'])
            result.setdefault(sym, []).append({'date': dt, 'close': cls})
    finally:
        conn.close()
    return result


# ─── Source 1 & 2: EODHD ──────────────────────────────────────────────────────

def _fetch_from_eodhd(eodhd_symbol: str, start_date: str, end_date: str) -> list[dict]:
    """
    Fetch daily OHLCV from EODHD for a given symbol (e.g. 'TASI.INDX').
    Returns [] on any failure.
    """
    if not EODHD_KEY:
        return []
    import requests
    url = f'https://eodhd.com/api/eod/{eodhd_symbol}'
    params = {
        'api_token': EODHD_KEY,
        'from': start_date,
        'to': end_date,
        'period': 'd',
        'fmt': 'json',
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if not data or not isinstance(data, list):
            return []
        rows = []
        for r in data:
            if not r.get('date') or not r.get('close'):
                continue
            close = float(r['close'])
            rows.append({
                'symbol': 'TASI.INDX',
                'date':   r['date'][:10],
                'open':   float(r.get('open') or close),
                'high':   float(r.get('high') or close),
                'low':    float(r.get('low') or close),
                'close':  close,
                'volume': int(r.get('volume') or 0),
            })
        logger.info('[TASI] EODHD %s → %d rows', eodhd_symbol, len(rows))
        return rows
    except Exception as e:
        logger.warning('[TASI] EODHD %s failed: %s', eodhd_symbol, e)
        return []


# ─── Source 3: equal-weight proxy ─────────────────────────────────────────────

def _compute_tasi_proxy(start_date: str, end_date: str) -> list[dict]:
    """
    Build an equal-weight TASI proxy from TASI_PROXY_SYMBOLS already in prices.
    Normalises each component to 1.0 at the base date, then scales to TASI_BASE.
    Returns rows tagged as symbol='TASI.INDX'.
    """
    price_map = _fetch_existing_prices(TASI_PROXY_SYMBOLS, start_date, end_date)
    if len(price_map) < MIN_PROXY_COMPONENTS:
        logger.warning('[TASI] Proxy: only %d component(s) in DB, need ≥ %d',
                       len(price_map), MIN_PROXY_COMPONENTS)
        return []

    # Build date → {symbol: close}
    date_map: dict = {}
    for sym, rows in price_map.items():
        for row in rows:
            date_map.setdefault(row['date'], {})[sym] = row['close']

    if not date_map:
        return []

    sorted_dates = sorted(date_map.keys())

    # Base date: earliest date with ≥ MIN_PROXY_COMPONENTS stocks
    base_prices: dict = {}
    for d in sorted_dates:
        present = date_map[d]
        if len(present) >= MIN_PROXY_COMPONENTS:
            base_prices = present
            break

    if not base_prices:
        return []

    proxy_rows = []
    for d in sorted_dates:
        day_prices = date_map[d]
        ratios = [
            day_prices[sym] / base_px
            for sym, base_px in base_prices.items()
            if sym in day_prices and base_px > 0
        ]
        if not ratios:
            continue
        idx_val = round((sum(ratios) / len(ratios)) * TASI_BASE, 2)
        proxy_rows.append({
            'symbol': 'TASI.INDX',
            'date':   d,
            'open':   idx_val,
            'high':   idx_val,
            'low':    idx_val,
            'close':  idx_val,
            'volume': 0,
        })

    logger.info('[TASI] Proxy: %d days from %d components', len(proxy_rows), len(base_prices))
    return proxy_rows


# ─── Public entry point ────────────────────────────────────────────────────────

def fetch_and_store_tasi(days_back: int = 365) -> int:
    """
    Fetch TASI data and upsert into prices table.

    Returns the number of rows upserted.
    """
    end_date   = datetime.utcnow().strftime('%Y-%m-%d')
    start_date = (datetime.utcnow() - timedelta(days=days_back)).strftime('%Y-%m-%d')

    logger.info('[TASI] Fetching benchmark %s → %s', start_date, end_date)

    rows: list[dict] = []

    # Strategy 1 & 2: EODHD
    for candidate in EODHD_TASI_CANDIDATES:
        rows = _fetch_from_eodhd(candidate, start_date, end_date)
        if rows:
            logger.info('[TASI] Using EODHD candidate: %s', candidate)
            break

    # Strategy 3: equal-weight proxy
    if not rows:
        logger.info('[TASI] EODHD unavailable — building equal-weight proxy')
        rows = _compute_tasi_proxy(start_date, end_date)

    if not rows:
        logger.error('[TASI] All strategies failed — no benchmark data available')
        return 0

    n = _upsert_prices(rows)
    logger.info('[TASI] Upserted %d rows as TASI.INDX', n)
    return n


# ─── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import argparse
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S',
    )
    parser = argparse.ArgumentParser(description='Fetch and store TASI benchmark prices')
    parser.add_argument('--days', type=int, default=365,
                        help='Days of history to fetch (default 365)')
    args = parser.parse_args()

    n = fetch_and_store_tasi(days_back=args.days)
    if n == 0:
        print('[TASI] ERROR: No data stored — check EODHD_API_KEY and DB connection')
        sys.exit(1)
    print(f'[TASI] Done — {n} rows stored as TASI.INDX')
