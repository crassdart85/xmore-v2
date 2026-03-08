"""
engines/etf_shared.py — Shared helpers for all ETF ingestion engines.

Provides:
  - EgxScraper      : requests-based scraper with retry + graceful 403 handling
  - _parse_egx_table: BeautifulSoup HTML table → list[dict]
  - get_or_create_instrument: upsert into `instrument` table, return id
  - _clean_num      : strip commas/spaces from EGX number strings → float or None
"""

import time
import logging
import re
from datetime import date
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ── EGX scraper ───────────────────────────────────────────────────────────────

_EGX_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/122.0.0.0 Safari/537.36'
    ),
    'Accept':          'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Referer':         'https://www.egx.com.eg/',
    'Connection':      'keep-alive',
}


class EgxScraper:
    """GET/POST to EGX pages with retry + graceful failure."""

    BASE = 'https://www.egx.com.eg/en/'
    TIMEOUT = 30

    def get(self, path: str, retries: int = 3, backoff: float = 2.0) -> Optional[str]:
        """
        Fetch an EGX page.  Returns HTML string on success, None on failure.
        Handles "Request Rejected", 403, 429, and connection errors gracefully.
        """
        url = path if path.startswith('http') else self.BASE + path
        for attempt in range(retries):
            try:
                resp = requests.get(url, headers=_EGX_HEADERS, timeout=self.TIMEOUT)
                if resp.status_code in (403, 429):
                    logger.warning('[EgxScraper] %s — HTTP %s (blocked/rate-limited)', url, resp.status_code)
                    return None
                if resp.status_code != 200:
                    logger.warning('[EgxScraper] %s — HTTP %s', url, resp.status_code)
                    if attempt < retries - 1:
                        time.sleep(backoff)
                        continue
                    return None
                html = resp.text
                if 'Request Rejected' in html:
                    logger.warning('[EgxScraper] %s — "Request Rejected" in response', url)
                    return None
                return html
            except requests.RequestException as exc:
                logger.warning('[EgxScraper] %s — attempt %d/%d: %s', url, attempt + 1, retries, exc)
                if attempt < retries - 1:
                    time.sleep(backoff)
        return None


# ── HTML table parser ─────────────────────────────────────────────────────────

def _clean_num(s: Optional[str]) -> Optional[float]:
    """Strip commas/whitespace from EGX number strings; return float or None."""
    if s is None:
        return None
    s = s.strip().replace(',', '').replace(' ', '')
    if s in ('', '-', '--', 'N/A', 'n/a'):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _parse_egx_table(html: str, table_index: int = 0) -> list:
    """
    Parse an HTML table from EGX pages into a list of dicts.
    Tries `table_index` first; if empty, tries other tables.
    Returns [] if no usable table found.
    """
    soup = BeautifulSoup(html, 'lxml')
    tables = soup.find_all('table')
    if not tables:
        logger.debug('[_parse_egx_table] No <table> elements found')
        return []

    # Try the requested index first, then all others
    indices = [table_index] + [i for i in range(len(tables)) if i != table_index]
    for idx in indices:
        if idx >= len(tables):
            continue
        tbl = tables[idx]
        headers = [th.get_text(strip=True) for th in tbl.find_all('th')]
        rows = []
        for tr in tbl.find_all('tr'):
            cells = [td.get_text(strip=True) for td in tr.find_all('td')]
            if not cells:
                continue
            if headers and len(cells) == len(headers):
                rows.append(dict(zip(headers, cells)))
            elif cells:
                rows.append({str(i): v for i, v in enumerate(cells)})
        if rows:
            return rows

    logger.debug('[_parse_egx_table] No non-empty table found')
    return []


# ── Instrument upsert ─────────────────────────────────────────────────────────

def get_or_create_instrument(conn, symbol: str, exchange: str, defaults: Optional[dict] = None) -> Optional[int]:
    """
    Upsert a row into `instrument` and return its id (INTEGER for SQLite, BIGINT for PG).
    `defaults` is merged into the INSERT but ignored on conflict.

    Works with both SQLite (? placeholders) and PostgreSQL (%s placeholders).
    """
    import os
    is_pg = bool(os.getenv('DATABASE_URL'))
    ph = '%s' if is_pg else '?'

    defaults = defaults or {}
    name     = defaults.get('name', symbol)
    type_    = defaults.get('type', 'ETF')
    region   = defaults.get('region', None)
    currency = defaults.get('currency', None)
    country  = defaults.get('country', None)
    issuer   = defaults.get('issuer', None)
    isin     = defaults.get('isin', None)
    underlying_index = defaults.get('underlying_index', None)

    cur = conn.cursor()
    today = date.today().isoformat()

    if is_pg:
        cur.execute(f"""
            INSERT INTO instrument
              (type, region, symbol, isin, name, exchange, currency, country, issuer, underlying_index, updated_at)
            VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})
            ON CONFLICT (exchange, symbol) DO UPDATE
              SET name       = COALESCE(EXCLUDED.name, instrument.name),
                  updated_at = EXCLUDED.updated_at
            RETURNING instrument_id
        """, (type_, region, symbol, isin, name, exchange, currency, country, issuer, underlying_index, today))
        row = cur.fetchone()
        return row['instrument_id'] if row else None
    else:
        cur.execute(f"""
            INSERT OR IGNORE INTO instrument
              (type, region, symbol, isin, name, exchange, currency, country, issuer, underlying_index, updated_at)
            VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})
        """, (type_, region, symbol, isin, name, exchange, currency, country, issuer, underlying_index, today))
        cur.execute(f"SELECT id FROM instrument WHERE exchange = {ph} AND symbol = {ph}", (exchange, symbol))
        row = cur.fetchone()
        return row[0] if row else None
