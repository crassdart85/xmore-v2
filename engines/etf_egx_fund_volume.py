"""
engines/etf_egx_fund_volume.py — Scrape EGX ETF fund volume (AUM proxy).

Source: https://www.egx.com.eg/en/EtfFundVolume.aspx
Output: etf_fund_volume

Run:
    python -m engines.etf_egx_fund_volume
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

SOURCE_URL = 'https://www.egx.com.eg/en/EtfFundVolume.aspx'

_HEADER_MAP = {
    'ETF Name': 'name', 'Fund Name': 'name', 'Name': 'name',
    'Fund Size':   'fund_size',  'Size':       'fund_size',
    'Net Subs':    'net_subs',   'Net Subscriptions': 'net_subs',
    'No Units':    'no_units',   'No. Units':  'no_units',  'Units': 'no_units',
    'Last Update': 'last_update', 'Update Date': 'last_update', 'Date': 'last_update',
}


def run():
    scraper = EgxScraper()
    html = scraper.get(SOURCE_URL)
    if not html:
        logger.warning('[etf_egx_fund_volume] Could not fetch %s — skipping', SOURCE_URL)
        return 0

    rows = _parse_egx_table(html, table_index=0)
    if not rows:
        logger.warning('[etf_egx_fund_volume] No table rows parsed')
        return 0

    today = date.today().isoformat()
    upserted = 0
    is_pg = bool(os.getenv('DATABASE_URL'))

    with get_connection() as conn:
        for raw in rows:
            rec = {_HEADER_MAP.get(k, k): v for k, v in raw.items()}
            name = rec.get('name', '').strip()
            if not name or name.lower() in ('name', 'etf name', 'fund name'):
                continue

            fund_size = _clean_num(rec.get('fund_size'))
            net_subs  = _clean_num(rec.get('net_subs'))
            no_units  = _clean_num(rec.get('no_units'))
            if all(x is None for x in (fund_size, net_subs, no_units)):
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
                'ON CONFLICT (instrument_id, asof_date) DO UPDATE SET '
                'fund_size=EXCLUDED.fund_size, net_subs=EXCLUDED.net_subs, '
                'no_units=EXCLUDED.no_units, last_update_raw=EXCLUDED.last_update_raw'
            ) if is_pg else (
                'ON CONFLICT(instrument_id, asof_date) DO UPDATE SET '
                'fund_size=excluded.fund_size, net_subs=excluded.net_subs, '
                'no_units=excluded.no_units, last_update_raw=excluded.last_update_raw'
            )

            sql = _adapt_sql(f"""
                INSERT INTO etf_fund_volume
                  (instrument_id, asof_date, fund_size, net_subs, no_units, last_update_raw, source_url)
                VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph})
                {conflict}
            """)
            try:
                cur = conn.cursor()
                cur.execute(sql, (inst_id, today, fund_size, net_subs, no_units,
                                  rec.get('last_update', ''), SOURCE_URL))
                upserted += 1
            except Exception as exc:
                logger.error('[etf_egx_fund_volume] Insert failed for "%s": %s', name, exc)

    logger.info('[etf_egx_fund_volume] Done — %d rows upserted for %s', upserted, today)
    return upserted


if __name__ == '__main__':
    start = time.time()
    try:
        create_tables()
        count = run()
        from database import log_system_run
        log_system_run('etf_egx_fund_volume', 'success', f'{count} rows', time.time() - start)
    except Exception as exc:
        logger.exception('[etf_egx_fund_volume] Fatal: %s', exc)
        try:
            from database import log_system_run
            log_system_run('etf_egx_fund_volume', 'failure', str(exc), time.time() - start)
        except Exception:
            pass
        sys.exit(1)
