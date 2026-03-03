"""
engines/etf_egx_holdings.py — Scrape EGX ETF fund constituents/holdings.

Source: https://www.egx.com.eg/en/FundConstituents.aspx
Output: etf_holdings_snapshot + etf_holding_line

Run:
    python -m engines.etf_egx_holdings
"""

import os
import sys
import logging
import time
from datetime import date

from bs4 import BeautifulSoup

from database import create_tables, get_connection, _adapt_sql
from engines.etf_shared import EgxScraper, _clean_num, get_or_create_instrument

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

SOURCE_URL = 'https://www.egx.com.eg/en/FundConstituents.aspx'


def _parse_holdings_page(html: str) -> list:
    """
    Parse the FundConstituents page.
    Returns list of dicts: {fund_name, last_update, constituents: [{name, weight, ...}]}
    EGX typically shows one table per fund; we try to detect fund sections.
    """
    soup = BeautifulSoup(html, 'lxml')
    results = []
    current_fund = None

    # Try to detect fund name from headings + tables
    for elem in soup.find_all(['h2', 'h3', 'h4', 'table', 'div']):
        tag = elem.name
        text = elem.get_text(strip=True)

        if tag in ('h2', 'h3', 'h4') and text and len(text) < 120:
            # New fund section heading
            current_fund = {'fund_name': text, 'last_update': date.today().isoformat(), 'constituents': []}
            results.append(current_fund)

        elif tag == 'table' and current_fund is not None:
            headers = [th.get_text(strip=True) for th in elem.find_all('th')]
            for tr in elem.find_all('tr'):
                cells = [td.get_text(strip=True) for td in tr.find_all('td')]
                if not cells:
                    continue
                row = dict(zip(headers, cells)) if headers else {str(i): v for i, v in enumerate(cells)}
                # Try to extract holding name + weight
                holding_name = (row.get('Security') or row.get('Stock') or row.get('Name') or
                                row.get('Constituent') or row.get('0') or '').strip()
                weight_raw = (row.get('Weight %') or row.get('Weight') or row.get('Wgt%') or
                              row.get('1') or '').strip()
                weight = _clean_num(weight_raw)
                if holding_name and weight is not None:
                    current_fund['constituents'].append({
                        'name':   holding_name,
                        'symbol': (row.get('Symbol') or row.get('Ticker') or '').strip() or None,
                        'isin':   (row.get('ISIN') or '').strip() or None,
                        'weight': weight,
                        'sector': (row.get('Sector') or '').strip() or None,
                    })

    # Fallback: if no fund sections detected, treat entire page as one fund
    if not results:
        tables = soup.find_all('table')
        for tbl in tables:
            headers = [th.get_text(strip=True) for th in tbl.find_all('th')]
            rows = []
            for tr in tbl.find_all('tr'):
                cells = [td.get_text(strip=True) for td in tr.find_all('td')]
                if cells:
                    row = dict(zip(headers, cells)) if headers else {str(i): v for i, v in enumerate(cells)}
                    rows.append(row)
            if rows:
                results.append({'fund_name': 'Unknown ETF', 'last_update': date.today().isoformat(),
                                 'constituents': rows})

    return results


def run():
    scraper = EgxScraper()
    html = scraper.get(SOURCE_URL)
    if not html:
        logger.warning('[etf_egx_holdings] Could not fetch %s — skipping', SOURCE_URL)
        return 0

    funds = _parse_holdings_page(html)
    if not funds:
        logger.warning('[etf_egx_holdings] No fund sections parsed')
        return 0

    today = date.today().isoformat()
    snapshots = 0
    is_pg = bool(os.getenv('DATABASE_URL'))

    with get_connection() as conn:
        for fund in funds:
            name = fund['fund_name'].strip()
            if not name:
                continue
            symbol = name.upper().replace(' ', '_')[:30]
            inst_id = get_or_create_instrument(conn, symbol, 'EGX', {
                'name': name, 'type': 'ETF', 'region': 'LOCAL_EGX',
                'currency': 'EGP', 'country': 'Egypt',
            })
            if inst_id is None:
                continue

            ph = '%s' if is_pg else '?'

            # Check if snapshot already exists for today
            snap_pk = 'snapshot_id' if is_pg else 'id'
            cur = conn.cursor()
            cur.execute(_adapt_sql(
                f"SELECT {snap_pk} FROM etf_holdings_snapshot WHERE instrument_id={ph} AND snapshot_date={ph} AND source={ph}"
            ), (inst_id, today, 'EGX'))
            existing = cur.fetchone()
            if existing:
                logger.debug('[etf_egx_holdings] Snapshot already exists for %s %s — skipping', name, today)
                continue

            # Insert snapshot header
            constituents = fund.get('constituents', [])
            total_w = sum(c.get('weight', 0) or 0 for c in constituents) if constituents else None

            cur.execute(_adapt_sql(f"""
                INSERT INTO etf_holdings_snapshot
                  (instrument_id, snapshot_date, source, source_url, currency, total_weight)
                VALUES ({ph},{ph},{ph},{ph},{ph},{ph})
            """), (inst_id, today, 'EGX', SOURCE_URL, 'EGP', total_w))

            if is_pg:
                cur.execute("SELECT lastval()")
                snap_id = cur.fetchone()[0]
            else:
                snap_id = cur.lastrowid

            # Insert holding lines
            for line_no, c in enumerate(constituents, start=1):
                h_name = (c.get('name') or c.get('holding_name') or str(c)).strip()
                if not h_name:
                    continue
                weight = _clean_num(str(c.get('weight', '') or c.get('1', '')))
                if weight is None:
                    continue
                try:
                    cur.execute(_adapt_sql(f"""
                        INSERT INTO etf_holding_line
                          (snapshot_id, line_no, holding_symbol, holding_name, holding_isin,
                           weight_pct, country, sector)
                        VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})
                        ON CONFLICT(snapshot_id, line_no) DO NOTHING
                    """ if is_pg else f"""
                        INSERT OR IGNORE INTO etf_holding_line
                          (snapshot_id, line_no, holding_symbol, holding_name, holding_isin,
                           weight_pct, country, sector)
                        VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})
                    """), (
                        snap_id, line_no,
                        c.get('symbol') or None, h_name, c.get('isin') or None,
                        weight, 'Egypt', c.get('sector') or None,
                    ))
                except Exception as exc:
                    logger.warning('[etf_egx_holdings] line_no %d for %s: %s', line_no, name, exc)

            snapshots += 1
            logger.info('[etf_egx_holdings] %s — %d constituent(s) stored', name, len(constituents))

    logger.info('[etf_egx_holdings] Done — %d fund snapshots stored', snapshots)
    return snapshots


if __name__ == '__main__':
    start = time.time()
    try:
        create_tables()
        count = run()
        from database import log_system_run
        log_system_run('etf_egx_holdings', 'success', f'{count} snapshots', time.time() - start)
    except Exception as exc:
        logger.exception('[etf_egx_holdings] Fatal: %s', exc)
        try:
            from database import log_system_run
            log_system_run('etf_egx_holdings', 'failure', str(exc), time.time() - start)
        except Exception:
            pass
        sys.exit(1)
