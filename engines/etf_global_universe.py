"""
engines/etf_global_universe.py — Discover global ETFs with Egypt exposure.

Strategy 1: Scrape https://etfdb.com/country/egypt/
Strategy 2 (fallback if ETFDB blocks): Use hardcoded seed list.

Output: instrument (region='GLOBAL') + etf_country_exposure (country='Egypt')

Run:
    python -m engines.etf_global_universe
"""

import os
import sys
import logging
import time
from datetime import date

import requests
from bs4 import BeautifulSoup

from database import create_tables, get_connection, _adapt_sql
from engines.etf_shared import get_or_create_instrument, _clean_num

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

ETFDB_URL = 'https://etfdb.com/country/egypt/'

# Hardcoded seed list (fallback + bootstrap — update as new ETFs are discovered)
KNOWN_EGYPT_ETFS = {
    'EGPT': {
        'name':    'VanEck Egypt ETF',
        'exchange': 'NYSE',
        'issuer':  'VanEck',
        'currency': 'USD',
        'country': 'US',
        'underlying_index': 'MVIS Egypt Index',
        'egypt_weight': 99.0,   # ~100% Egypt
    },
    'FM': {
        'name':    'iShares MSCI Frontier and Select EM ETF',
        'exchange': 'NASDAQ',
        'issuer':  'iShares',
        'currency': 'USD',
        'country': 'US',
        'underlying_index': 'MSCI Frontier Markets Select Index',
        'egypt_weight': None,  # ~5–8%; will be updated by ETFDB scrape
    },
    'FRDM': {
        'name':    'Freedom 100 Emerging Markets ETF',
        'exchange': 'NYSE',
        'issuer':  'Alpha Architect',
        'currency': 'USD',
        'country': 'US',
        'egypt_weight': None,
    },
    'EEMX': {
        'name':    'SPDR MSCI Emerging Markets Fossil Fuel Reserves Free ETF',
        'exchange': 'NYSE',
        'issuer':  'SPDR / State Street',
        'currency': 'USD',
        'country': 'US',
        'egypt_weight': None,
    },
}

_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml;q=0.9,*/*;q=0.8',
    'Referer': 'https://etfdb.com/',
}


def _scrape_etfdb() -> dict:
    """
    Scrape ETFDB Egypt page.
    Returns dict: {ticker: {name, egypt_weight, ...}} or empty dict on failure.
    """
    try:
        resp = requests.get(ETFDB_URL, headers=_HEADERS, timeout=20)
        if resp.status_code in (403, 429):
            logger.warning('[etf_global_universe] ETFDB returned %s — using seed list', resp.status_code)
            return {}
        if resp.status_code != 200:
            logger.warning('[etf_global_universe] ETFDB HTTP %s', resp.status_code)
            return {}
        soup = BeautifulSoup(resp.text, 'lxml')
        results = {}
        for table in soup.find_all('table'):
            headers = [th.get_text(strip=True) for th in table.find_all('th')]
            for tr in table.find_all('tr'):
                cells = [td.get_text(strip=True) for td in tr.find_all('td')]
                if not cells:
                    continue
                row = dict(zip(headers, cells)) if headers else {str(i): v for i, v in enumerate(cells)}
                ticker = (row.get('Ticker') or row.get('Symbol') or row.get('0') or '').strip().upper()
                if not ticker or len(ticker) > 10:
                    continue
                name_val = (row.get('ETF Name') or row.get('Fund') or row.get('Name') or row.get('1') or '').strip()
                weight_raw = (row.get('Egypt Weight') or row.get('Weight') or row.get('Allocation') or row.get('2') or '').strip()
                results[ticker] = {
                    'name':          name_val or ticker,
                    'egypt_weight':  _clean_num(weight_raw.replace('%', '')) if weight_raw else None,
                }
        logger.info('[etf_global_universe] ETFDB scraped: %d tickers', len(results))
        return results
    except Exception as exc:
        logger.warning('[etf_global_universe] ETFDB scrape error: %s', exc)
        return {}


def run():
    # Step 1: Try ETFDB scrape
    etfdb_data = _scrape_etfdb()

    # Step 2: Merge with seed list (seed is authoritative for known ETFs)
    merged = {}
    for ticker, seed in KNOWN_EGYPT_ETFS.items():
        merged[ticker] = dict(seed)
        if ticker in etfdb_data:
            # Update weight from ETFDB if available
            if etfdb_data[ticker].get('egypt_weight') is not None:
                merged[ticker]['egypt_weight'] = etfdb_data[ticker]['egypt_weight']
            if etfdb_data[ticker].get('name') and not merged[ticker].get('name'):
                merged[ticker]['name'] = etfdb_data[ticker]['name']

    # Add any new tickers found by ETFDB that aren't in the seed
    for ticker, data in etfdb_data.items():
        if ticker not in merged:
            merged[ticker] = data

    if not merged:
        logger.warning('[etf_global_universe] No ETFs found — nothing to upsert')
        return 0

    today = date.today().isoformat()
    upserted = 0
    is_pg = bool(os.getenv('DATABASE_URL'))

    with get_connection() as conn:
        for ticker, data in merged.items():
            exchange = data.get('exchange', 'OTHER')
            inst_id = get_or_create_instrument(conn, ticker, exchange, {
                'name':             data.get('name', ticker),
                'type':             'ETF',
                'region':           'GLOBAL',
                'currency':         data.get('currency', 'USD'),
                'country':          data.get('country', 'US'),
                'issuer':           data.get('issuer'),
                'underlying_index': data.get('underlying_index'),
            })
            if inst_id is None:
                logger.warning('[etf_global_universe] Could not upsert instrument for %s', ticker)
                continue

            egypt_weight = data.get('egypt_weight')
            if egypt_weight is not None:
                ph = '%s' if is_pg else '?'
                conflict = (
                    'ON CONFLICT (instrument_id, asof_date, country) DO UPDATE SET weight_pct=EXCLUDED.weight_pct'
                ) if is_pg else (
                    'ON CONFLICT(instrument_id, asof_date, country) DO UPDATE SET weight_pct=excluded.weight_pct'
                )
                sql = _adapt_sql(f"""
                    INSERT INTO etf_country_exposure (instrument_id, asof_date, country, weight_pct, source_url)
                    VALUES ({ph},{ph},{ph},{ph},{ph})
                    {conflict}
                """)
                try:
                    cur = conn.cursor()
                    cur.execute(sql, (inst_id, today, 'Egypt', egypt_weight, ETFDB_URL))
                except Exception as exc:
                    logger.warning('[etf_global_universe] country_exposure upsert for %s: %s', ticker, exc)

            upserted += 1
            logger.info('[etf_global_universe] %s (%s) — Egypt weight: %s%%',
                        ticker, data.get('name', ''), egypt_weight)

    logger.info('[etf_global_universe] Done — %d global ETFs in instrument table', upserted)
    return upserted


if __name__ == '__main__':
    start = time.time()
    try:
        create_tables()
        count = run()
        from database import log_system_run
        log_system_run('etf_global_universe', 'success', f'{count} ETFs', time.time() - start)
    except Exception as exc:
        logger.exception('[etf_global_universe] Fatal: %s', exc)
        try:
            from database import log_system_run
            log_system_run('etf_global_universe', 'failure', str(exc), time.time() - start)
        except Exception:
            pass
        sys.exit(1)
