"""
engines/etf_egx_mubasher.py — Scrape EGX investment fund data from Mubasher.

Source: https://www.mubasher.info/countries/eg/funds-statistics
The page embeds fund arrays as server-side JavaScript variables (midata.xxx),
so plain requests.get() returns all data — no JS rendering needed.

Output: instrument (region='LOCAL_EGX') seeded with fund names + symbols.
        etf_nav updated with latest NAV price (if price > 0).

Run:
    python -m engines.etf_egx_mubasher
"""

import ast
import json
import logging
import os
import re
import sys
import time
from datetime import date

import requests

from database import create_tables, get_connection, _adapt_sql
from engines.etf_shared import get_or_create_instrument

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

STATS_URL = 'https://www.mubasher.info/countries/eg/funds-statistics'

_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml;q=0.9,*/*;q=0.8',
    'Referer': 'https://www.mubasher.info/',
}

# midata variables that contain fund arrays on the statistics page
_VARS = ['threeMonthGainers', 'threeMonthLosers', 'yearGainers', 'yearLosers']

# Map Mubasher Arabic classification to our ETF type
_CLASS_MAP = {
    '\u0633\u0644\u0639':            'COMMODITY',  # سلع (commodities)
    '\u0623\u0633\u0647\u0645':      'EQUITY',     # أسهم (equities)
    '\u0645\u062a\u0646\u0648\u0639': 'BALANCED',  # متنوع (diversified/balanced)
    '\u0627\u0644\u062f\u062e\u0644 \u0627\u0644\u062b\u0627\u0628\u062a': 'FIXED_INCOME',  # الدخل الثابت
}


def _fetch_html() -> str | None:
    try:
        resp = requests.get(STATS_URL, headers=_HEADERS, timeout=20)
        if resp.status_code != 200:
            logger.warning('[etf_egx_mubasher] HTTP %s from %s', resp.status_code, STATS_URL)
            return None
        return resp.text
    except Exception as exc:
        logger.warning('[etf_egx_mubasher] Fetch error: %s', exc)
        return None


def _extract_funds(html: str) -> dict:
    """
    Extract all fund objects from midata.xxx = [...] assignments in the HTML.
    Returns dict keyed by fundId (deduped across all four arrays).
    """
    funds = {}
    for var in _VARS:
        # Match: midata.threeMonthGainers = [...];
        pattern = rf"midata\.{var}\s*=\s*(\[.*?\]);"
        m = re.search(pattern, html, re.DOTALL)
        if not m:
            continue
        raw = m.group(1)
        # The embedded data uses Python-style single-quoted strings; convert to JSON
        try:
            # Replace Python None/True/False with JSON equivalents
            raw_json = (
                raw
                .replace("'", '"')
                .replace(': None', ': null')
                .replace(':None', ':null')
                .replace(': True', ': true')
                .replace(':True', ':true')
                .replace(': False', ': false')
                .replace(':False', ':false')
            )
            items = json.loads(raw_json)
        except Exception:
            try:
                items = ast.literal_eval(raw)
            except Exception as exc:
                logger.warning('[etf_egx_mubasher] Could not parse %s: %s', var, exc)
                continue
        for item in items:
            fid = item.get('fundId')
            if fid and fid not in funds:
                funds[fid] = item
    return funds


def _parse_pct(s: str | None) -> float | None:
    """Parse '29.76%' → 29.76, '-2.81%' → -2.81, None → None."""
    if not s:
        return None
    try:
        return float(s.replace('%', '').strip())
    except (ValueError, AttributeError):
        return None


def _parse_date(arabic_date: str | None) -> str | None:
    """
    Parse Mubasher Arabic date like '04 مارس 2026' → '2026-03-04'.
    Falls back to today if parsing fails.
    """
    if not arabic_date:
        return date.today().isoformat()
    _months = {
        'يناير': 1, 'فبراير': 2, 'مارس': 3, 'أبريل': 4, 'مايو': 5, 'يونيو': 6,
        'يوليو': 7, 'أغسطس': 8, 'سبتمبر': 9, 'أكتوبر': 10, 'نوفمبر': 11, 'ديسمبر': 12,
    }
    parts = arabic_date.strip().split()
    try:
        day = int(parts[0])
        month = _months.get(parts[1], 0)
        year = int(parts[2])
        if month and year > 2000:
            return f'{year:04d}-{month:02d}-{day:02d}'
    except Exception:
        pass
    return date.today().isoformat()


def run() -> int:
    html = _fetch_html()
    if not html:
        return 0

    funds = _extract_funds(html)
    if not funds:
        logger.warning('[etf_egx_mubasher] No fund data extracted from %s', STATS_URL)
        return 0

    logger.info('[etf_egx_mubasher] Extracted %d unique funds', len(funds))

    is_pg = bool(os.getenv('DATABASE_URL'))
    ph = '%s' if is_pg else '?'
    upserted = 0

    with get_connection() as conn:
        for fid, fund in funds.items():
            symbol = fund.get('symbol', '').strip()
            if not symbol:
                logger.debug('[etf_egx_mubasher] Skipping fundId %s — no symbol', fid)
                continue

            name = fund.get('name', symbol)
            cls  = fund.get('classification', '')

            inst_id = get_or_create_instrument(conn, symbol, 'EGX', {
                'name':     name,
                'type':     'ETF',
                'region':   'LOCAL_EGX',
                'currency': 'EGP',
                'country':  'Egypt',
                'issuer':   _CLASS_MAP.get(cls, cls),
            })
            if inst_id is None:
                logger.warning('[etf_egx_mubasher] Could not upsert instrument for %s', symbol)
                continue

            # Store performance data as a price row (close_price=null, pct_change=3-month return)
            pct_3m  = _parse_pct(fund.get('profitThreeMonth'))
            pct_1y  = _parse_pct(fund.get('profitLastYear'))
            nav_price = float(fund.get('price') or 0) or None
            trade_date = _parse_date(fund.get('date'))

            # Only insert if price > 0 OR we have pct data worth storing
            if nav_price or pct_3m is not None or pct_1y is not None:
                nav_conflict = (
                    'ON CONFLICT (instrument_id, nav_date) DO UPDATE SET nav_value=EXCLUDED.nav_value'
                ) if is_pg else (
                    'ON CONFLICT(instrument_id, nav_date) DO UPDATE SET nav_value=excluded.nav_value'
                )
                price_conflict = (
                    'ON CONFLICT (instrument_id, trade_date) DO UPDATE SET '
                    'close_price=EXCLUDED.close_price, last_price=EXCLUDED.last_price, '
                    'pct_change=EXCLUDED.pct_change, source_url=EXCLUDED.source_url'
                ) if is_pg else (
                    'ON CONFLICT(instrument_id, trade_date) DO UPDATE SET '
                    'close_price=excluded.close_price, last_price=excluded.last_price, '
                    'pct_change=excluded.pct_change, source_url=excluded.source_url'
                )

                try:
                    cur = conn.cursor()
                    # NAV table: store price if available
                    if nav_price:
                        sql_nav = _adapt_sql(f"""
                            INSERT INTO etf_nav (instrument_id, nav_date, nav_value, last_update_raw)
                            VALUES ({ph},{ph},{ph},{ph})
                            {nav_conflict}
                        """)
                        cur.execute(sql_nav, (inst_id, trade_date, nav_price, fund.get('date')))

                    # Price table: store price as close_price/last_price + pct_change
                    sql_price = _adapt_sql(f"""
                        INSERT INTO etf_price_daily
                          (instrument_id, trade_date, close_price, last_price, pct_change, source_url)
                        VALUES ({ph},{ph},{ph},{ph},{ph},{ph})
                        {price_conflict}
                    """)
                    cur.execute(sql_price, (inst_id, trade_date, nav_price, nav_price, pct_3m, STATS_URL))
                    upserted += 1
                except Exception as exc:
                    logger.error('[etf_egx_mubasher] DB insert for %s: %s', symbol, exc)

            logger.info('[etf_egx_mubasher] %s — 3m: %s%%, 1y: %s%%',
                        symbol, pct_3m, pct_1y)

    logger.info('[etf_egx_mubasher] Done — %d fund rows upserted', upserted)
    return upserted


if __name__ == '__main__':
    start = time.time()
    try:
        create_tables()
        count = run()
        from database import log_system_run
        log_system_run('etf_egx_mubasher', 'success', f'{count} funds', time.time() - start)
    except Exception as exc:
        logger.exception('[etf_egx_mubasher] Fatal: %s', exc)
        try:
            from database import log_system_run
            log_system_run('etf_egx_mubasher', 'failure', str(exc), time.time() - start)
        except Exception:
            pass
        sys.exit(1)
