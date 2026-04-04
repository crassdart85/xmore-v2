"""
EGX Scraper — async version of the TradingView + backup scraper.

Primary source: TradingView Scanner API (JSON, 250+ stocks, 15-min delayed)
Backup source: EGX_PRIMARY_URL env var (default: http://41.33.162.236/egs4/)

Configurable via environment variable:
    EGX_PRIMARY_URL — override the backup HTML source URL
"""

import os
import logging
import re
from datetime import datetime, date
from typing import List, Optional, Dict, Any

import aiohttp

logger = logging.getLogger(__name__)

TV_SCAN_URL = 'https://scanner.tradingview.com/egypt/scan'
TV_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json',
    'Origin': 'https://www.tradingview.com',
    'Referer': 'https://www.tradingview.com/',
    'Content-Type': 'application/json',
}
TV_COLUMNS = ['name', 'close', 'open', 'high', 'low', 'volume', 'change', 'description']

EGX_PRIMARY_URL = os.getenv('EGX_PRIMARY_URL', 'http://41.33.162.236/egs4/')

# Source tracking counter
_source_counter: Dict[str, int] = {'tradingview': 0, 'egx_backup': 0, 'yfinance': 0}


def get_source_stats() -> Dict[str, int]:
    """Return fetch source usage counts for monitoring."""
    return dict(_source_counter)


async def fetch_egx_tradingview(timeout: float = 5.0) -> Optional[List[Dict[str, Any]]]:
    """
    Fetch EGX stock data from TradingView Scanner API (async).

    Returns list of dicts with keys: symbol, date, open, high, low, close, volume, change_pct, name_en
    Returns None on failure.
    """
    payload = {
        'filter': [{'left': 'exchange', 'operation': 'equal', 'right': 'EGX'}],
        'columns': TV_COLUMNS,
        'sort': {'sortBy': 'volume', 'sortOrder': 'desc'},
        'range': [0, 500],
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                TV_SCAN_URL,
                headers=TV_HEADERS,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                resp.raise_for_status()
                body = await resp.json()
                data = body.get('data', [])

                if not data:
                    logger.warning('[egx_scraper] Empty response from TradingView')
                    return None

                today = datetime.now().strftime('%Y-%m-%d')
                rows = []
                for item in data:
                    d = item.get('d', [])
                    if len(d) < 6:
                        continue
                    ticker = d[0]
                    close = d[1]
                    if close is None or close == 0:
                        continue
                    rows.append({
                        'symbol': f"{ticker}.CA" if not str(ticker).endswith('.CA') else ticker,
                        'date': today,
                        'open': float(d[2]) if d[2] else float(close),
                        'high': float(d[3]) if d[3] else float(close),
                        'low': float(d[4]) if d[4] else float(close),
                        'close': float(close),
                        'volume': int(d[5]) if d[5] else 0,
                        'change_pct': float(d[6]) if len(d) > 6 and d[6] is not None else 0.0,
                        'name_en': str(d[7]) if len(d) > 7 else '',
                    })

                if rows:
                    _source_counter['tradingview'] += 1
                    logger.info('[egx_scraper] Fetched %d EGX stocks from TradingView', len(rows))
                return rows if rows else None

    except Exception as exc:
        logger.warning('[egx_scraper] TradingView failed: %s', exc)
        return None


async def fetch_egx_live(timeout: float = 5.0) -> Optional[List[Dict[str, Any]]]:
    """
    Fetch EGX data: TradingView primary, EGX backup fallback.
    Returns list of OHLCV dicts or None.
    """
    # Primary: TradingView
    data = await fetch_egx_tradingview(timeout=timeout)
    if data:
        return data

    # Backup: HTML scraper (sync, wrapped in executor if needed)
    logger.warning('[egx_scraper] TradingView failed, trying backup %s', EGX_PRIMARY_URL)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                EGX_PRIMARY_URL,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                    'Accept': 'text/html',
                    'Accept-Language': 'ar,en;q=0.9',
                },
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                if resp.status != 200:
                    logger.warning('[egx_scraper] Backup returned %d', resp.status)
                    return None
                # Backup parsing is complex (Arabic HTML) — defer to sync scraper
                _source_counter['egx_backup'] += 1
                logger.info('[egx_scraper] Backup source responded (parsing delegated)')
                return None  # Caller should use yfinance fallback

    except Exception as exc:
        logger.warning('[egx_scraper] Backup source failed: %s', exc)
        return None
