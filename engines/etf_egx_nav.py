"""
engines/etf_egx_nav.py — Scrape EGX ETF NAV (Net Asset Value) per unit.

Source: https://www.egx.com.eg/en/NavUnit.aspx
Output: etf_nav

Run:
    python -m engines.etf_egx_nav
"""

import os
import sys
import logging
import time
from datetime import date

from database import create_tables, get_connection, _adapt_sql
from engines.etf_shared import EgxScraper, _parse_egx_table, _clean_num, get_or_create_instrument

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

SOURCE_URL = 'https://www.egx.com.eg/en/NavUnit.aspx'

_HEADER_MAP = {
    'ETF Name': 'name', 'Fund Name': 'name', 'Name': 'name',
    'NAV': 'nav', 'NAV/Unit': 'nav', 'Net Asset Value': 'nav',
    'Last Update': 'last_update', 'Update Date': 'last_update', 'Date': 'last_update',
}


def _normalise_row(raw: dict) -> dict:
    out = {}
    for k, v in raw.items():
        mapped = _HEADER_MAP.get(k)
        if mapped:
            out[mapped] = v
    return out


def run():
    scraper = EgxScraper()
    html = scraper.get(SOURCE_URL)
    if not html:
        logger.warning('[etf_egx_nav] Could not fetch %s — skipping', SOURCE_URL)
        return 0

    rows = _parse_egx_table(html, table_index=0)
    if not rows:
        logger.warning('[etf_egx_nav] No table rows parsed')
        return 0

    today = date.today().isoformat()
    upserted = 0
    is_pg = bool(os.getenv('DATABASE_URL'))

    with get_connection() as conn:
        for raw in rows:
            rec = _normalise_row(raw)
            name = rec.get('name', '').strip()
            if not name or name.lower() in ('name', 'etf name', 'fund name'):
                continue

            nav_val = _clean_num(rec.get('nav'))
            if nav_val is None:
                continue

            symbol = name.upper().replace(' ', '_')[:30]
            inst_id = get_or_create_instrument(conn, symbol, 'EGX', {
                'name': name, 'type': 'ETF', 'region': 'LOCAL_EGX',
                'currency': 'EGP', 'country': 'Egypt',
            })
            if inst_id is None:
                continue

            ph = '%s' if is_pg else '?'
            conflict = (
                'ON CONFLICT (instrument_id, nav_date) DO UPDATE SET '
                'nav_value=EXCLUDED.nav_value, last_update_raw=EXCLUDED.last_update_raw'
            ) if is_pg else (
                'ON CONFLICT(instrument_id, nav_date) DO UPDATE SET '
                'nav_value=excluded.nav_value, last_update_raw=excluded.last_update_raw'
            )

            sql = _adapt_sql(f"""
                INSERT INTO etf_nav (instrument_id, nav_date, nav_value, last_update_raw, source_url)
                VALUES ({ph},{ph},{ph},{ph},{ph})
                {conflict}
            """)
            try:
                cur = conn.cursor()
                cur.execute(sql, (inst_id, today, nav_val, rec.get('last_update', ''), SOURCE_URL))
                upserted += 1
            except Exception as exc:
                logger.error('[etf_egx_nav] Insert failed for "%s": %s', name, exc)

    logger.info('[etf_egx_nav] Done — %d NAV rows upserted for %s', upserted, today)
    return upserted


if __name__ == '__main__':
    start = time.time()
    try:
        create_tables()
        count = run()
        from database import log_system_run
        log_system_run('etf_egx_nav', 'success', f'{count} rows upserted', time.time() - start)
    except Exception as exc:
        logger.exception('[etf_egx_nav] Fatal: %s', exc)
        try:
            from database import log_system_run
            log_system_run('etf_egx_nav', 'failure', str(exc), time.time() - start)
        except Exception:
            pass
        sys.exit(1)
