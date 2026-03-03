"""
engines/etf_global_holdings.py — Fetch holdings for global Egypt-exposure ETFs.

Source: Yahoo Finance holdings pages (e.g. https://finance.yahoo.com/quote/EGPT/holdings/)
Output: etf_holdings_snapshot + etf_holding_line (source='YAHOO')

Run:
    python -m engines.etf_global_holdings
"""

import os
import sys
import logging
import time
from datetime import date

import requests
from bs4 import BeautifulSoup

from database import create_tables, get_connection, _adapt_sql
from engines.etf_shared import _clean_num

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

YAHOO_HOLDINGS_URL = 'https://finance.yahoo.com/quote/{ticker}/holdings/'

_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 Chrome/122.0 Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}


def _fetch_yahoo_holdings(ticker: str) -> list:
    """
    Scrape Yahoo Finance holdings page.
    Returns list of {name, weight_pct} or empty list.
    """
    url = YAHOO_HOLDINGS_URL.format(ticker=ticker)
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=20)
        if resp.status_code != 200:
            logger.warning('[etf_global_holdings] Yahoo %s returned HTTP %s', ticker, resp.status_code)
            return []
        soup = BeautifulSoup(resp.text, 'lxml')
        holdings = []
        # Try multiple table selectors
        for table in soup.find_all('table'):
            headers = [th.get_text(strip=True) for th in table.find_all('th')]
            for tr in table.find_all('tr'):
                cells = [td.get_text(strip=True) for td in tr.find_all('td')]
                if not cells:
                    continue
                row = dict(zip(headers, cells)) if headers else {str(i): v for i, v in enumerate(cells)}
                name = (row.get('Name') or row.get('Holding') or row.get('Company') or
                        row.get('0') or '').strip()
                weight_raw = (row.get('% Assets') or row.get('Weight') or row.get('1') or '').strip()
                weight = _clean_num(weight_raw.replace('%', ''))
                if name and weight is not None and len(name) > 1:
                    holdings.append({'name': name, 'weight_pct': weight})
        return holdings
    except Exception as exc:
        logger.warning('[etf_global_holdings] Yahoo fetch for %s: %s', ticker, exc)
        return []


def run():
    is_pg = bool(os.getenv('DATABASE_URL'))
    ph = '%s' if is_pg else '?'

    with get_connection() as conn:
        cur = conn.cursor()
        if is_pg:
            cur.execute("SELECT instrument_id AS id, symbol FROM instrument WHERE region = 'GLOBAL' AND is_active = TRUE")
        else:
            cur.execute("SELECT id, symbol FROM instrument WHERE region = 'GLOBAL' AND is_active = 1")
        instruments = [(row['id'] if hasattr(row, 'keys') else row[0],
                        row['symbol'] if hasattr(row, 'keys') else row[1])
                       for row in cur.fetchall()]

    if not instruments:
        logger.info('[etf_global_holdings] No global instruments in DB')
        return 0

    today = date.today().isoformat()
    snapshots = 0

    for inst_id, ticker in instruments:
        logger.info('[etf_global_holdings] Fetching Yahoo holdings for %s…', ticker)
        holdings = _fetch_yahoo_holdings(ticker)

        if not holdings:
            logger.info('[etf_global_holdings] No holdings found for %s', ticker)
            time.sleep(2)
            continue

        with get_connection() as conn:
            cur = conn.cursor()
            # Check if snapshot already exists
            snap_pk = 'snapshot_id' if is_pg else 'id'
            cur.execute(_adapt_sql(
                f"SELECT {snap_pk} FROM etf_holdings_snapshot "
                f"WHERE instrument_id={ph} AND snapshot_date={ph} AND source={ph}"
            ), (inst_id, today, 'YAHOO'))
            if cur.fetchone():
                logger.debug('[etf_global_holdings] Snapshot exists for %s %s', ticker, today)
                time.sleep(2)
                continue

            total_w = sum(h['weight_pct'] for h in holdings)
            cur.execute(_adapt_sql(f"""
                INSERT INTO etf_holdings_snapshot
                  (instrument_id, snapshot_date, source, source_url, currency, total_weight)
                VALUES ({ph},{ph},{ph},{ph},{ph},{ph})
            """), (inst_id, today, 'YAHOO', YAHOO_HOLDINGS_URL.format(ticker=ticker), 'USD', total_w))

            if is_pg:
                cur.execute("SELECT lastval()")
                snap_id = cur.fetchone()[0]
            else:
                snap_id = cur.lastrowid

            for line_no, h in enumerate(holdings, start=1):
                try:
                    cur.execute(_adapt_sql(
                        f"INSERT INTO etf_holding_line "
                        f"  (snapshot_id, line_no, holding_name, weight_pct, country) "
                        f"VALUES ({ph},{ph},{ph},{ph},{ph}) "
                        + ('ON CONFLICT(snapshot_id, line_no) DO NOTHING' if is_pg
                           else 'ON CONFLICT(snapshot_id, line_no) DO NOTHING')
                    ), (snap_id, line_no, h['name'], h['weight_pct'], None))
                except Exception as exc:
                    logger.warning('[etf_global_holdings] line %d for %s: %s', line_no, ticker, exc)

        logger.info('[etf_global_holdings] %s — %d holdings stored', ticker, len(holdings))
        snapshots += 1
        time.sleep(2)  # Rate limit between requests

    logger.info('[etf_global_holdings] Done — %d snapshots stored', snapshots)
    return snapshots


if __name__ == '__main__':
    start = time.time()
    try:
        create_tables()
        count = run()
        from database import log_system_run
        log_system_run('etf_global_holdings', 'success', f'{count} snapshots', time.time() - start)
    except Exception as exc:
        logger.exception('[etf_global_holdings] Fatal: %s', exc)
        try:
            from database import log_system_run
            log_system_run('etf_global_holdings', 'failure', str(exc), time.time() - start)
        except Exception:
            pass
        sys.exit(1)
