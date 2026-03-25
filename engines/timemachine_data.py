"""
Time Machine Data Fetcher — KSA/Tadawul
Fetches historical OHLCV for all KSA (.SR) stocks using a multi-source strategy:

  1. PostgreSQL prices table (primary — data pre-loaded by backfill_history.py)
  2. EODHD API per-symbol (fallback for symbols missing from DB)
  3. yfinance (last-resort; limited .SR coverage)
  4. TASI equal-weight proxy for benchmark (from component stocks in DB)

All data stays in-memory — nothing is written to the database.
Tadawul stocks use .SR suffix (e.g. 2222.SR, 1180.SR).
"""

import logging
import os
import sqlite3
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

# KSA Tadawul constituents — the main stocks Xmore tracks
EGX30_SYMBOLS = [   # name kept for import compat; these are .SR KSA symbols
    '2222.SR', '1180.SR', '1170.SR', '7010.SR', '2010.SR',
    '2020.SR', '1150.SR', '1060.SR', '4190.SR', '1050.SR',
    '4061.SR', '7020.SR', '2030.SR', '4031.SR', '8010.SR',
    '1140.SR', '1010.SR', '1020.SR', '1030.SR', '1080.SR',
    '1160.SR', '2100.SR', '2060.SR', '2080.SR', '2090.SR',
    '7030.SR', '4003.SR', '4050.SR', '4001.SR', '4240.SR',
    '4321.SR', '4020.SR', '4040.SR', '4100.SR', '4150.SR',
    '2120.SR', '2130.SR', '3002.SR', '4002.SR', '8020.SR',
    '4030.SR',
]

# Human-readable stock names for the frontend
STOCK_NAMES = {
    '2222.SR': ('Saudi Aramco',               'أرامكو السعودية'),
    '1180.SR': ('Al Rajhi Bank',              'مصرف الراجحي'),
    '1170.SR': ('Saudi National Bank',        'البنك الأهلي السعودي'),
    '7010.SR': ('Saudi Telecom Company',      'الاتصالات السعودية'),
    '2010.SR': ('SABIC',                      'سابك'),
    '2020.SR': ('Saudi Industrial Investment','الاستثمار الصناعي السعودي'),
    '1150.SR': ('Alinma Bank',                'مصرف الإنماء'),
    '1060.SR': ('Saudi Arabian British Bank', 'البنك السعودي البريطاني'),
    '4190.SR': ('Jarir Marketing',            'مكتبة جرير'),
    '1050.SR': ('Banque Saudi Fransi',        'بنك ساب السعودي الفرنسي'),
    '4061.SR': ('Almarai',                    'المراعي'),
    '7020.SR': ('Etihad Etisalat (Mobily)',   'اتحاد اتصالات (موبايلي)'),
    '2030.SR': ('SAFCO',                      'سافكو'),
    '4031.SR': ('Bahri (National Shipping)',  'البحري'),
    '8010.SR': ('Tawuniya',                   'التعاونية'),
    '1140.SR': ('Al Bilad Bank',              'بنك البلاد'),
    '1010.SR': ('Riyad Bank',                 'بنك الرياض'),
    '1020.SR': ('Bank AlJazira',              'بنك الجزيرة'),
    '1030.SR': ('Saudi Investment Bank',      'البنك السعودي للاستثمار'),
    '1080.SR': ('Arab National Bank',         'البنك العربي الوطني'),
    '1160.SR': ('Al-Rajhi Takaful',           'الراجحي للتكافل'),
    '2100.SR': ('Gulf International Services','الخليج الدولية للخدمات'),
    '2060.SR': ('Yanbu National Petrochemicals','ينساب'),
    '2080.SR': ('National Industrialization', 'التصنيع الوطنية'),
    '2090.SR': ('National Petrochemical',     'الوطنية للبتروكيماويات'),
    '7030.SR': ('Zain KSA',                   'زين السعودية'),
    '4003.SR': ('Extra (United Electronics)', 'إكسترا'),
    '4050.SR': ('Savola Group',               'مجموعة صافولا'),
    '4001.SR': ('Aldrees Petroleum',          'الدريس للبترول'),
    '4240.SR': ('Fawaz Alhokair',             'فواز الحكير'),
    '4321.SR': ('Abdullah Al Othaim Markets', 'أسواق عبدالله العثيم'),
    '4020.SR': ('Dar Al Arkan Real Estate',   'دار الأركان'),
    '4040.SR': ('Saudi Real Estate',          'شركة العقارية'),
    '4100.SR': ('Emaar The Economic City',    'إعمار المدينة الاقتصادية'),
    '4150.SR': ('Taiba Investments',          'طيبة للاستثمار'),
    '2120.SR': ('Astra Industrial Group',     'مجموعة أسترا الصناعية'),
    '2130.SR': ('Saudi Ceramics',             'السيراميك السعودي'),
    '3002.SR': ('Saudi Cement',               'الإسمنت السعودية'),
    '4002.SR': ('Dallah Healthcare',          'دله الصحية'),
    '8020.SR': ('BUPA Arabia',                'بوبا العربية'),
    '4030.SR': ('Saudi Airlines Catering',    'الخطوط الجوية للتموين'),
}

# Shared session headers — mimic a real browser to avoid 429 blocks
_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/121.0.0.0 Safari/537.36'
    ),
    'Accept': 'application/json',
}

# Local fallback DB path (read-only usage; no writes from this module)
_LOCAL_PRICE_DB = Path(__file__).resolve().parents[1] / 'stocks.db'


# ─── Source 2: Direct Yahoo Finance v8/chart API ──────────────────────────────

def _fetch_yahoo_direct(symbol: str, buffer_start: str, end_date: str) -> list:
    """
    Fallback for symbols that yfinance batch returns 0 rows (e.g. ESRS.CA).
    Calls query1.finance.yahoo.com/v8/finance/chart/ directly with requests.

    Returns list of row dicts (same format as yfinance parser), or [] on failure.
    """
    try:
        p1 = int(datetime.strptime(buffer_start, '%Y-%m-%d').timestamp())
        p2 = int(datetime.strptime(end_date, '%Y-%m-%d').timestamp()) + 86400  # inclusive
        url = (
            f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}'
            f'?period1={p1}&period2={p2}&interval=1d&events=history'
        )
        payload = _http_get_json(url, timeout=15)
        if not payload:
            return []
        chart = payload.get('chart', {})
        if chart.get('error'):
            logger.debug(f"  {symbol} direct API error: {chart['error']}")
            return []

        result_arr = chart.get('result', [])
        if not result_arr:
            return []

        item = result_arr[0]
        timestamps = item.get('timestamp', [])
        indicators = item.get('indicators', {})
        quotes = indicators.get('quote', [{}])[0]
        adj = indicators.get('adjclose', [{}])
        adj_close = adj[0].get('adjclose', []) if adj else []

        opens = quotes.get('open', [])
        highs = quotes.get('high', [])
        lows = quotes.get('low', [])
        closes = quotes.get('close', [])
        volumes = quotes.get('volume', [])

        rows = []
        for i, ts in enumerate(timestamps):
            # Skip rows where close is None (market holidays / missing data)
            close_val = (adj_close[i] if adj_close and i < len(adj_close) else None) or (closes[i] if i < len(closes) else None)
            if close_val is None:
                continue
            date_str = datetime.utcfromtimestamp(ts).strftime('%Y-%m-%d')
            rows.append({
                'date': date_str,
                'open': round(float(opens[i]) if i < len(opens) and opens[i] else close_val, 2),
                'high': round(float(highs[i]) if i < len(highs) and highs[i] else close_val, 2),
                'low': round(float(lows[i]) if i < len(lows) and lows[i] else close_val, 2),
                'close': round(float(close_val), 2),
                'volume': int(volumes[i]) if i < len(volumes) and volumes[i] else 0,
            })
        return rows

    except Exception as e:
        logger.debug(f"  {symbol} direct API exception: {e}")
        return []


def _http_get_json(url: str, timeout: int = 15) -> dict:
    """
    Fetch JSON using requests when available, otherwise urllib (stdlib only).
    This keeps Time Machine working in Node-only deployments without Python deps.
    """
    try:
        import requests

        resp = requests.get(url, headers=_HEADERS, timeout=timeout)
        if resp.status_code != 200:
            logger.debug(f"Direct API HTTP {resp.status_code} for {url[:120]}")
            return {}
        return resp.json() if resp.content else {}
    except ImportError:
        pass
    except Exception as e:
        logger.debug(f"requests fetch failed: {e}")

    try:
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            if not raw:
                return {}
            import json

            return json.loads(raw.decode('utf-8'))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        logger.debug(f"urllib fetch failed: {e}")
        return {}
    except Exception as e:
        logger.debug(f"urllib unexpected failure: {e}")
        return {}


# ─── Source 4: TASI equal-weight proxy ────────────────────────────────────────

def _compute_tasi_proxy(price_data: dict, buffer_start: str) -> list:
    """
    Build an equal-weight TASI proxy from available KSA component stocks.
    Each stock is normalised to 1.0 at the earliest shared date, then averaged.
    Scaled to TASI_BASE (≈ 12000) to produce a realistic index level.

    Returns list of {date, open, high, low, close, volume} dicts stored under
    the key '^TASI' in the caller's result dict.
    """
    TASI_BASE = 12_000
    # Collect all dates from component stocks (exclude the proxy key itself)
    component_data = {
        sym: price_data[sym]
        for sym in EGX30_SYMBOLS
        if sym in price_data and price_data[sym]
    }

    if not component_data:
        return []

    # Build date → {symbol: close} map
    date_map: dict = {}
    for sym, rows in component_data.items():
        for row in rows:
            date_map.setdefault(row['date'], {})[sym] = row['close']

    if not date_map:
        return []

    sorted_dates = sorted(date_map.keys())

    # Find base date: earliest date where ≥ 50% of component stocks have data
    min_stocks = max(3, len(component_data) // 2)
    base_date = None
    base_prices: dict = {}
    for d in sorted_dates:
        present = {sym: date_map[d][sym] for sym in date_map[d]}
        if len(present) >= min_stocks:
            base_date = d
            base_prices = present
            break

    if not base_date:
        return []

    # Compute proxy value for each date
    proxy_rows = []
    for d in sorted_dates:
        day_prices = date_map[d]
        # Only use stocks that have both a base price and today's price
        ratios = []
        for sym, base_px in base_prices.items():
            if sym in day_prices and base_px > 0:
                ratios.append(day_prices[sym] / base_px)

        if not ratios:
            continue

        avg = sum(ratios) / len(ratios)
        # Scale to TASI_BASE (~12000) for a realistic index level
        index_val = round(avg * TASI_BASE, 2)
        proxy_rows.append({
            'date': d,
            'open': index_val,
            'high': index_val,
            'low': index_val,
            'close': index_val,
            'volume': 0,
        })

    logger.info(f"  TASI proxy: {len(proxy_rows)} days from {len(base_prices)} stocks")
    return proxy_rows


def _fetch_from_local_db(symbol: str, buffer_start: str, end_date: str) -> list:
    """
    Read historical OHLCV from local stocks.db as a resilience fallback.
    This is read-only and keeps Time Machine fully ephemeral.
    """
    if not _LOCAL_PRICE_DB.exists():
        return []

    clean = symbol.replace('.SR', '').replace('.CA', '')
    rows_out: list = []
    conn = sqlite3.connect(_LOCAL_PRICE_DB)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT date, open, high, low, close, volume
            FROM prices
            WHERE (
                UPPER(symbol) = UPPER(?)
                OR UPPER(symbol) = UPPER(?)
                OR UPPER(REPLACE(REPLACE(symbol, '.SR', ''), '.CA', '')) = UPPER(?)
            )
              AND DATE(SUBSTR(CAST(date AS TEXT), 1, 10)) >= DATE(?)
              AND DATE(SUBSTR(CAST(date AS TEXT), 1, 10)) <= DATE(?)
            ORDER BY DATE(SUBSTR(CAST(date AS TEXT), 1, 10)) ASC
            """,
            (clean, symbol, clean, buffer_start, end_date),
        ).fetchall()
    except Exception as e:
        logger.debug(f"  [localdb] {symbol}: query failed ({e})")
        conn.close()
        return []
    finally:
        conn.close()

    for r in rows:
        try:
            close_val = float(r['close'])
            rows_out.append({
                'date': str(r['date']),
                'open': round(float(r['open']) if r['open'] is not None else close_val, 2),
                'high': round(float(r['high']) if r['high'] is not None else close_val, 2),
                'low': round(float(r['low']) if r['low'] is not None else close_val, 2),
                'close': round(close_val, 2),
                'volume': int(r['volume']) if r['volume'] is not None else 0,
            })
        except Exception:
            continue
    return rows_out


def _fetch_from_postgres_db(symbol: str, buffer_start: str, end_date: str) -> list:
    """
    Read historical OHLCV from PostgreSQL prices table (Render/prod fallback).
    """
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        return []

    try:
        import psycopg2
    except ImportError:
        return []

    clean = symbol.replace('.SR', '').replace('.CA', '')
    conn = None
    rows_out: list = []
    try:
        conn = psycopg2.connect(database_url)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT date, open, high, low, close, volume
            FROM prices
            WHERE (
                UPPER(symbol) = UPPER(%s)
                OR UPPER(symbol) = UPPER(%s)
                OR UPPER(REPLACE(REPLACE(symbol, '.SR', ''), '.CA', '')) = UPPER(%s)
            )
              AND CAST(date AS DATE) >= CAST(%s AS DATE)
              AND CAST(date AS DATE) <= CAST(%s AS DATE)
            ORDER BY CAST(date AS DATE) ASC
            """,
            (clean, symbol, clean, buffer_start, end_date),
        )
        rows = cur.fetchall()
        for r in rows:
            try:
                close_val = float(r[4])
                rows_out.append({
                    'date': str(r[0]),
                    'open': round(float(r[1]) if r[1] is not None else close_val, 2),
                    'high': round(float(r[2]) if r[2] is not None else close_val, 2),
                    'low': round(float(r[3]) if r[3] is not None else close_val, 2),
                    'close': round(close_val, 2),
                    'volume': int(r[5]) if r[5] is not None else 0,
                })
            except Exception:
                continue
    except Exception as e:
        logger.debug(f"  [pgdb] {symbol}: query failed ({e})")
        return []
    finally:
        if conn is not None:
            conn.close()

    return rows_out


def _fetch_from_db_fallback(symbol: str, buffer_start: str, end_date: str) -> list:
    """
    Prefer PostgreSQL (prod) then SQLite (local) as resilient fallback.
    """
    rows = _fetch_from_postgres_db(symbol, buffer_start, end_date)
    if rows:
        return rows
    return _fetch_from_local_db(symbol, buffer_start, end_date)


# ─── Public API ───────────────────────────────────────────────────────────────

def fetch_historical_prices(start_date: str, end_date: str) -> dict:
    """
    Fetch OHLCV data for all KSA (.SR) stocks + TASI benchmark.

    Strategy (KSA-optimised):
      1. PostgreSQL/SQLite prices table (primary — populated by backfill_history.py)
      2. EODHD API per-symbol (fallback for symbols not yet in DB)
      3. yfinance (last-resort; coverage varies for .SR)
      4. TASI equal-weight proxy benchmark (from fetched component data)
         Also tries TASI.INDX from DB (written by fetch_tasi_benchmark.py)

    Args:
        start_date: "YYYY-MM-DD"
        end_date: "YYYY-MM-DD"

    Returns:
        {
          "2222.SR": [{"date": "2025-06-15", "open": 31.2, "high": 31.8,
                       "low": 30.9, "close": 31.5, "volume": 12000000}, ...],
          "^TASI":   [{"date": "2025-06-15", "close": 12543.0, ...}, ...],
          ...
        }
    """
    # Add a generous warmup buffer for SMA/RSI warmup
    buffer_start = (
        datetime.strptime(start_date, '%Y-%m-%d') - timedelta(days=180)
    ).strftime('%Y-%m-%d')

    logger.info(
        f"Fetching {len(EGX30_SYMBOLS)} KSA stocks from {buffer_start} to {end_date}"
    )

    result: dict = {}

    # ── Step 1: PostgreSQL / SQLite prices table (primary) ───────────────────
    logger.info("Step 1: Fetching from prices table (DB primary)...")
    for symbol in EGX30_SYMBOLS:
        rows = _fetch_from_db_fallback(symbol, buffer_start, end_date)
        if rows:
            result[symbol] = rows
            logger.info(f"  [db] {symbol}: {len(rows)} days")

    # ── Step 2: EODHD for symbols not in DB ──────────────────────────────────
    missing = [s for s in EGX30_SYMBOLS if s not in result]
    if missing and os.getenv('EODHD_API_KEY'):
        logger.info(f"Step 2: EODHD fallback for {len(missing)} symbols")
        try:
            from fetch_tasi_benchmark import _fetch_from_eodhd as _eodhd_fetch
        except ImportError:
            _eodhd_fetch = None

        if _eodhd_fetch:
            for symbol in missing:
                rows_raw = _eodhd_fetch(symbol, buffer_start, end_date)
                if rows_raw:
                    # Strip the symbol override — _eodhd_fetch tags as TASI.INDX
                    rows = [{**r, 'symbol': symbol} for r in rows_raw]
                    result[symbol] = [
                        {'date': r['date'], 'open': r['open'], 'high': r['high'],
                         'low': r['low'], 'close': r['close'], 'volume': r['volume']}
                        for r in rows
                    ]
                    logger.info(f"  [eodhd] {symbol}: {len(rows)} days")
                time.sleep(0.2)

    # ── Step 3: yfinance last-resort for still-missing symbols ───────────────
    still_missing = [s for s in EGX30_SYMBOLS if s not in result]
    if still_missing:
        yf = None
        try:
            import yfinance as yf  # type: ignore[assignment]
        except ImportError:
            pass

        if yf is not None:
            logger.info(f"Step 3: yfinance last-resort for {len(still_missing)} symbols")
            for symbol in still_missing:
                try:
                    df = yf.download(symbol, start=buffer_start, end=end_date,
                                     interval='1d', auto_adjust=True, progress=False)
                    if df is not None and not df.empty:
                        df.dropna(subset=['Close'], inplace=True)
                        rows = []
                        for idx, row in df.iterrows():
                            rows.append({
                                'date':   idx.strftime('%Y-%m-%d'),
                                'open':   round(float(row['Open']), 2),
                                'high':   round(float(row['High']), 2),
                                'low':    round(float(row['Low']), 2),
                                'close':  round(float(row['Close']), 2),
                                'volume': int(row['Volume']) if row['Volume'] > 0 else 0,
                            })
                        if rows:
                            result[symbol] = rows
                            logger.info(f"  [yf] {symbol}: {len(rows)} days")
                except Exception as e:
                    logger.debug(f"  [yf] {symbol}: failed ({e})")
                time.sleep(0.3)

    # ── Step 4: TASI benchmark ────────────────────────────────────────────────
    # Try TASI.INDX from DB first (written by fetch_tasi_benchmark.py)
    logger.info("Step 4: Fetching TASI benchmark...")
    tasi_db = _fetch_from_db_fallback('TASI.INDX', buffer_start, end_date)
    if tasi_db:
        result['^TASI'] = tasi_db
        logger.info(f"  TASI.INDX from DB: {len(tasi_db)} days")
    else:
        # Build equal-weight proxy from component stocks fetched in steps 1-3
        proxy = _compute_tasi_proxy(result, buffer_start)
        if proxy:
            result['^TASI'] = proxy
        else:
            logger.warning("Could not build TASI benchmark (not enough component data)")

    logger.info(
        f"Data fetch complete: {len([k for k in result if k != '^TASI'])} stocks + "
        f"{'^TASI (' + str(len(result['^TASI'])) + ' days)' if '^TASI' in result else 'no benchmark'}"
    )
    return result


def get_stock_name(symbol: str, lang: str = 'en') -> str:
    """Get human-readable stock name."""
    names = STOCK_NAMES.get(symbol)
    if not names:
        return symbol.replace('.CA', '')
    return names[1] if lang == 'ar' else names[0]
