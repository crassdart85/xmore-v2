"""
engines/etf_global_prices.py — Fetch daily prices for global Egypt-exposure ETFs.

Three-tier fallback per ticker:
  1. ETFDB detail page (parse last price from fund page)
  2. yfinance (primary reliable — already in requirements.txt)
  3. Log failure

Output: etf_price_daily (region='GLOBAL' instruments)

Run:
    python -m engines.etf_global_prices
    python -m engines.etf_global_prices --backfill   # fetch last 30 days
"""

import os
import sys
import logging
import time
import argparse
from datetime import date, timedelta

import requests
from bs4 import BeautifulSoup

from database import create_tables, get_connection, _adapt_sql

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

SOURCE_URL_TEMPLATE = 'https://etfdb.com/etf/{ticker}/'
YFINANCE_SOURCE = 'https://finance.yahoo.com/quote/{ticker}'

_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 Chrome/122.0 Safari/537.36'
    ),
    'Accept': 'text/html,*/*;q=0.8',
    'Referer': 'https://etfdb.com/',
}


def _fetch_etfdb_price(ticker: str) -> dict | None:
    """
    Try to scrape last price from ETFDB ETF detail page.
    Returns dict with price fields or None.
    """
    url = SOURCE_URL_TEMPLATE.format(ticker=ticker)
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=15)
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, 'lxml')
        # ETFDB shows price in a data attribute or span; try common selectors
        for sel in ['[data-type="price"]', '.price', '#quote-price', '.stock-price']:
            el = soup.select_one(sel)
            if el:
                text = el.get_text(strip=True).replace(',', '').replace('$', '')
                try:
                    price = float(text)
                    return {'close': price, 'source_url': url}
                except ValueError:
                    pass
    except Exception as exc:
        logger.debug('[etf_global_prices] ETFDB price fetch for %s: %s', ticker, exc)
    return None


def _fetch_yfinance_prices(tickers: list, period: str = '3d') -> dict:
    """
    Fetch prices using yfinance.
    Returns dict: {ticker: {date, open, high, low, close, volume}}
    """
    try:
        import yfinance as yf
        df = yf.download(tickers, period=period, auto_adjust=True, progress=False, group_by='ticker')
        results = {}
        if len(tickers) == 1:
            ticker = tickers[0]
            if not df.empty:
                last = df.iloc[-1]
                results[ticker] = {
                    'trade_date': df.index[-1].date().isoformat(),
                    'open':  float(last.get('Open', 0) or 0) or None,
                    'high':  float(last.get('High', 0) or 0) or None,
                    'low':   float(last.get('Low', 0) or 0) or None,
                    'close': float(last.get('Close', 0) or 0) or None,
                    'volume': float(last.get('Volume', 0) or 0) or None,
                    'source_url': YFINANCE_SOURCE.format(ticker=ticker),
                }
        else:
            for ticker in tickers:
                try:
                    sub = df[ticker] if ticker in df.columns.get_level_values(0) else df
                    if sub.empty:
                        continue
                    last = sub.iloc[-1]
                    results[ticker] = {
                        'trade_date': sub.index[-1].date().isoformat(),
                        'open':  float(last.get('Open', 0) or 0) or None,
                        'high':  float(last.get('High', 0) or 0) or None,
                        'low':   float(last.get('Low', 0) or 0) or None,
                        'close': float(last.get('Close', 0) or 0) or None,
                        'volume': float(last.get('Volume', 0) or 0) or None,
                        'source_url': YFINANCE_SOURCE.format(ticker=ticker),
                    }
                except Exception:
                    pass
        return results
    except Exception as exc:
        logger.warning('[etf_global_prices] yfinance error: %s', exc)
        return {}


def _fetch_yfinance_history(tickers: list, days: int = 30) -> dict:
    """Fetch historical prices for backfill mode."""
    try:
        import yfinance as yf
        start = (date.today() - timedelta(days=days)).isoformat()
        df = yf.download(tickers, start=start, auto_adjust=True, progress=False, group_by='ticker')
        results = {}
        if len(tickers) == 1:
            ticker = tickers[0]
            results[ticker] = []
            for idx, row in df.iterrows():
                results[ticker].append({
                    'trade_date': idx.date().isoformat(),
                    'open':  float(row.get('Open', 0) or 0) or None,
                    'high':  float(row.get('High', 0) or 0) or None,
                    'low':   float(row.get('Low', 0) or 0) or None,
                    'close': float(row.get('Close', 0) or 0) or None,
                    'volume': float(row.get('Volume', 0) or 0) or None,
                    'source_url': YFINANCE_SOURCE.format(ticker=ticker),
                })
        else:
            for ticker in tickers:
                results[ticker] = []
                try:
                    sub = df[ticker] if ticker in df.columns.get_level_values(0) else df
                    for idx, row in sub.iterrows():
                        results[ticker].append({
                            'trade_date': idx.date().isoformat(),
                            'open':  float(row.get('Open', 0) or 0) or None,
                            'high':  float(row.get('High', 0) or 0) or None,
                            'low':   float(row.get('Low', 0) or 0) or None,
                            'close': float(row.get('Close', 0) or 0) or None,
                            'volume': float(row.get('Volume', 0) or 0) or None,
                            'source_url': YFINANCE_SOURCE.format(ticker=ticker),
                        })
                except Exception:
                    pass
        return results
    except Exception as exc:
        logger.warning('[etf_global_prices] yfinance history error: %s', exc)
        return {}


def _upsert_price(conn, is_pg: bool, inst_id: int, rec: dict):
    ph = '%s' if is_pg else '?'
    conflict = (
        'ON CONFLICT (instrument_id, trade_date) DO UPDATE SET '
        'open_price=EXCLUDED.open_price, high_price=EXCLUDED.high_price, '
        'low_price=EXCLUDED.low_price, close_price=EXCLUDED.close_price, '
        'volume=EXCLUDED.volume, source_url=EXCLUDED.source_url'
    ) if is_pg else (
        'ON CONFLICT(instrument_id, trade_date) DO UPDATE SET '
        'open_price=excluded.open_price, high_price=excluded.high_price, '
        'low_price=excluded.low_price, close_price=excluded.close_price, '
        'volume=excluded.volume, source_url=excluded.source_url'
    )
    sql = _adapt_sql(f"""
        INSERT INTO etf_price_daily
          (instrument_id, trade_date, open_price, high_price, low_price,
           close_price, last_price, volume, source_url)
        VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})
        {conflict}
    """)
    cur = conn.cursor()
    cur.execute(sql, (
        inst_id, rec['trade_date'],
        rec.get('open'), rec.get('high'), rec.get('low'),
        rec.get('close'), rec.get('close'),  # last_price = close for EOD
        rec.get('volume'), rec.get('source_url', ''),
    ))


def run(backfill: bool = False):
    is_pg = bool(os.getenv('DATABASE_URL'))
    ph = '%s' if is_pg else '?'

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(_adapt_sql(
            f"SELECT id, symbol, exchange FROM instrument WHERE region = {ph} AND is_active = 1"
            if not is_pg else
            f"SELECT instrument_id AS id, symbol, exchange FROM instrument WHERE region = {ph} AND is_active = TRUE"
        ), ('GLOBAL',))
        rows = cur.fetchall()

    if not rows:
        logger.info('[etf_global_prices] No global instruments in DB — run etf_global_universe first')
        return 0

    instruments = {}
    for row in rows:
        if hasattr(row, 'keys'):
            instruments[row['symbol']] = {'id': row['id'], 'exchange': row.get('exchange', '')}
        else:
            instruments[row[1]] = {'id': row[0], 'exchange': row[2]}

    tickers = list(instruments.keys())
    logger.info('[etf_global_prices] Fetching prices for: %s (backfill=%s)', tickers, backfill)

    upserted = 0

    if backfill:
        price_data = _fetch_yfinance_history(tickers, days=30)
        with get_connection() as conn:
            for ticker, daily_rows in price_data.items():
                inst_id = instruments.get(ticker, {}).get('id')
                if not inst_id:
                    continue
                for rec in daily_rows:
                    if rec.get('close'):
                        try:
                            _upsert_price(conn, is_pg, inst_id, rec)
                            upserted += 1
                        except Exception as exc:
                            logger.warning('[etf_global_prices] backfill %s %s: %s', ticker, rec.get('trade_date'), exc)
    else:
        # Single-day: try ETFDB first, fall back to yfinance
        price_data = {}
        for ticker in tickers:
            etfdb_price = _fetch_etfdb_price(ticker)
            if etfdb_price and etfdb_price.get('close'):
                price_data[ticker] = {
                    'trade_date': date.today().isoformat(),
                    'close': etfdb_price['close'],
                    'source_url': etfdb_price['source_url'],
                }
                logger.debug('[etf_global_prices] ETFDB price for %s: %s', ticker, etfdb_price['close'])

        missing = [t for t in tickers if t not in price_data]
        if missing:
            yf_data = _fetch_yfinance_prices(missing)
            price_data.update(yf_data)

        with get_connection() as conn:
            for ticker, rec in price_data.items():
                inst_id = instruments.get(ticker, {}).get('id')
                if not inst_id or not rec.get('close'):
                    continue
                try:
                    _upsert_price(conn, is_pg, inst_id, rec)
                    upserted += 1
                    logger.info('[etf_global_prices] %s: close=%s (%s)', ticker, rec['close'], rec.get('trade_date'))
                except Exception as exc:
                    logger.error('[etf_global_prices] %s: %s', ticker, exc)

    logger.info('[etf_global_prices] Done — %d price rows upserted', upserted)
    return upserted


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Fetch global ETF prices')
    parser.add_argument('--backfill', action='store_true', help='Fetch last 30 days of history')
    args = parser.parse_args()

    start = time.time()
    try:
        create_tables()
        count = run(backfill=args.backfill)
        from database import log_system_run
        log_system_run('etf_global_prices', 'success', f'{count} rows', time.time() - start)
    except Exception as exc:
        logger.exception('[etf_global_prices] Fatal: %s', exc)
        try:
            from database import log_system_run
            log_system_run('etf_global_prices', 'failure', str(exc), time.time() - start)
        except Exception:
            pass
        sys.exit(1)
