"""
engines/etf_egx_tape.py — Scrape EGX ETF daily trading tape.

Source: https://www.egx.com.eg/en/ETFSPr.aspx
Output: etf_price_daily

Run:
    python -m engines.etf_egx_tape
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

SOURCE_URL = 'https://www.egx.com.eg/en/ETFSPr.aspx'

# Column name mappings from EGX table headers to our schema
# EGX headers vary between EN/AR versions — normalise by position fallback
_HEADER_MAP = {
    'ETF Name': 'name', 'Fund Name': 'name', 'Name': 'name',
    'Open':  'open', 'High':  'high', 'Low': 'low',
    'Close': 'close', 'Last':  'last', 'Last Price': 'last',
    'Change %': 'pct_change', '% Change': 'pct_change', 'Chg %': 'pct_change',
    'Value':   'value_traded', 'Value (LE)': 'value_traded',
    'Volume':  'volume',
    'Trades':  'trades', 'No. Trades': 'trades',
    'Market Cap': 'market_cap_mn', 'Mkt Cap': 'market_cap_mn',
}


def _normalise_row(raw: dict) -> dict:
    """Map raw EGX table row to our column names."""
    out = {}
    for k, v in raw.items():
        mapped = _HEADER_MAP.get(k)
        if mapped:
            out[mapped] = v
        elif not out.get('name') and k == '0':
            out['name'] = v
    return out


def run():
    scraper = EgxScraper()
    html = scraper.get(SOURCE_URL)
    if not html:
        logger.warning('[etf_egx_tape] Could not fetch %s — skipping', SOURCE_URL)
        return 0

    rows = _parse_egx_table(html, table_index=0)
    if not rows:
        logger.warning('[etf_egx_tape] No table rows parsed from %s', SOURCE_URL)
        return 0

    today = date.today().isoformat()
    upserted = 0
    is_pg = bool(os.getenv('DATABASE_URL'))

    with get_connection() as conn:
        for raw in rows:
            rec = _normalise_row(raw)
            name = rec.get('name', '').strip()
            if not name or name.lower() in ('name', 'etf name', 'fund name'):
                continue  # skip header rows

            # Derive a symbol from the name (uppercase, remove spaces)
            symbol = name.upper().replace(' ', '_')[:30]

            inst_id = get_or_create_instrument(conn, symbol, 'EGX', {
                'name':   name,
                'type':   'ETF',
                'region': 'LOCAL_EGX',
                'currency': 'EGP',
                'country':  'Egypt',
            })
            if inst_id is None:
                logger.warning('[etf_egx_tape] Could not get instrument_id for "%s"', name)
                continue

            ph = '%s' if is_pg else '?'
            conflict = (
                'ON CONFLICT (instrument_id, trade_date) DO UPDATE SET '
                'open_price=EXCLUDED.open_price, high_price=EXCLUDED.high_price, '
                'low_price=EXCLUDED.low_price, close_price=EXCLUDED.close_price, '
                'last_price=EXCLUDED.last_price, pct_change=EXCLUDED.pct_change, '
                'value_traded=EXCLUDED.value_traded, volume=EXCLUDED.volume, '
                'trades=EXCLUDED.trades, market_cap_mn=EXCLUDED.market_cap_mn, '
                'ingested_at=now()'
            ) if is_pg else (
                'ON CONFLICT(instrument_id, trade_date) DO UPDATE SET '
                'open_price=excluded.open_price, high_price=excluded.high_price, '
                'low_price=excluded.low_price, close_price=excluded.close_price, '
                'last_price=excluded.last_price, pct_change=excluded.pct_change, '
                'value_traded=excluded.value_traded, volume=excluded.volume, '
                'trades=excluded.trades, market_cap_mn=excluded.market_cap_mn'
            )

            sql = _adapt_sql(f"""
                INSERT INTO etf_price_daily
                  (instrument_id, trade_date, open_price, high_price, low_price,
                   close_price, last_price, pct_change, value_traded, volume,
                   trades, market_cap_mn, source_url)
                VALUES ({','.join([ph]*13)})
                {conflict}
            """)

            try:
                cur = conn.cursor()
                cur.execute(sql, (
                    inst_id, today,
                    _clean_num(rec.get('open')),
                    _clean_num(rec.get('high')),
                    _clean_num(rec.get('low')),
                    _clean_num(rec.get('close')),
                    _clean_num(rec.get('last')),
                    _clean_num(rec.get('pct_change')),
                    _clean_num(rec.get('value_traded')),
                    _clean_num(rec.get('volume')),
                    int(_clean_num(rec.get('trades')) or 0) or None,
                    _clean_num(rec.get('market_cap_mn')),
                    SOURCE_URL,
                ))
                upserted += 1
            except Exception as exc:
                logger.error('[etf_egx_tape] Insert failed for "%s": %s', name, exc)

    logger.info('[etf_egx_tape] Done — %d ETF price rows upserted for %s', upserted, today)
    return upserted


if __name__ == '__main__':
    start = time.time()
    try:
        create_tables()
        count = run()
        from database import log_system_run
        log_system_run('etf_egx_tape', 'success', f'{count} rows upserted', time.time() - start)
    except Exception as exc:
        logger.exception('[etf_egx_tape] Fatal error: %s', exc)
        try:
            from database import log_system_run
            log_system_run('etf_egx_tape', 'failure', str(exc), time.time() - start)
        except Exception:
            pass
        sys.exit(1)
